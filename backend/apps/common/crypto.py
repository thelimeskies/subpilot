"""Symmetric encryption helpers (Fernet).

Used to encrypt secrets-at-rest:
- ``user.mfa_secret``
- ``environment.nomba_client_secret``
- ``environment.webhook_secret``
- ``payment_method.token`` (Nomba processor token)

The Fernet key comes from ``settings.FIELD_ENCRYPTION_KEY``. Generate one with::

    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""
from __future__ import annotations

import secrets
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings


@lru_cache(maxsize=1)
def _fernet() -> Fernet:
    key = getattr(settings, "FIELD_ENCRYPTION_KEY", "") or ""
    if not key:
        raise RuntimeError(
            "FIELD_ENCRYPTION_KEY is not configured. Generate one with "
            "`python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"`"
        )
    return Fernet(key.encode("utf-8") if isinstance(key, str) else key)


def encrypt(plaintext: str) -> str:
    """Encrypt a string and return the Fernet token (base64)."""
    if plaintext is None:
        return ""
    return _fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt(token: str) -> str:
    """Decrypt a Fernet token. Returns ``""`` if the token is empty or invalid."""
    if not token:
        return ""
    try:
        return _fernet().decrypt(token.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        return ""


def hash_secret(secret: str) -> str:
    """SHA-256 hex digest. Used for API key hashing."""
    import hashlib

    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def generate_token(prefix: str, n_bytes: int = 24) -> str:
    """Generate a URL-safe random token like ``verify_<hex>`` for email links."""
    return f"{prefix}_{secrets.token_urlsafe(n_bytes)}"


def generate_api_key_secret(n_bytes: int = 32) -> str:
    """Random API key secret portion (URL-safe)."""
    return secrets.token_urlsafe(n_bytes)
