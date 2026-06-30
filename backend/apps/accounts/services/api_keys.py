"""API-key creation and revocation."""
from __future__ import annotations

import secrets
from dataclasses import dataclass

from django.db import transaction

from apps.common import time as t
from apps.common.crypto import generate_api_key_secret, hash_secret

from ..models import ApiKey, Environment, Merchant, User


@dataclass(frozen=True)
class IssuedApiKey:
    api_key: ApiKey
    plaintext: str  # Returned ONCE; never stored.


@transaction.atomic
def create_api_key(
    *,
    merchant: Merchant,
    environment: Environment,
    name: str,
    scopes: list[str] | None = None,
    created_by: User | None = None,
) -> IssuedApiKey:
    """Create a new API key. The plaintext value is returned exactly once."""
    if environment.merchant_id != merchant.id:
        raise ValueError("Environment does not belong to merchant")

    secret = generate_api_key_secret()
    short = secrets.token_hex(2)  # 4-char tag inside the prefix
    prefix = f"nse_{environment.mode}_{short}"
    plaintext = f"{prefix}_{secret}"

    api_key = ApiKey.objects.create(
        merchant=merchant,
        environment=environment,
        name=name,
        key_prefix=prefix,
        key_hash=hash_secret(secret),
        scopes=scopes or [],
        created_by=created_by,
    )
    return IssuedApiKey(api_key=api_key, plaintext=plaintext)


def generate_publishable_key(mode: str) -> str:
    """Create a browser-safe public environment identifier."""
    env = "live" if mode == Environment.Mode.LIVE else "test"
    return f"pk_{env}_{secrets.token_urlsafe(24)}"


def ensure_publishable_key(environment: Environment) -> str:
    if environment.publishable_key:
        return environment.publishable_key
    environment.publishable_key = generate_publishable_key(environment.mode)
    environment.save(update_fields=["publishable_key", "updated_at"])
    return environment.publishable_key


def rotate_publishable_key(environment: Environment) -> str:
    environment.publishable_key = generate_publishable_key(environment.mode)
    environment.save(update_fields=["publishable_key", "updated_at"])
    return environment.publishable_key


def revoke_api_key(api_key: ApiKey) -> ApiKey:
    if api_key.status == ApiKey.Status.REVOKED:
        return api_key
    api_key.status = ApiKey.Status.REVOKED
    api_key.revoked_at = t.utcnow()
    api_key.save(update_fields=["status", "revoked_at", "updated_at"])
    return api_key
