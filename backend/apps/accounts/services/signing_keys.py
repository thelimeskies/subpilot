"""Environment-level signing key helpers."""
from __future__ import annotations

from datetime import timedelta

from django.utils import timezone

from apps.audit.services.log_event import log_event
from apps.common.crypto import decrypt, encrypt, generate_token


def _new_signing_secret() -> str:
    return generate_token("whsec", 32)


def _mode_doc(merchant, mode: str) -> dict:
    metadata = dict(merchant.metadata or {})
    signing = metadata.get("signing_keys")
    if not isinstance(signing, dict):
        signing = {}
    doc = signing.get(mode)
    return doc if isinstance(doc, dict) else {}


def _save_mode_doc(merchant, mode: str, doc: dict) -> None:
    metadata = dict(merchant.metadata or {})
    signing = metadata.get("signing_keys")
    if not isinstance(signing, dict):
        signing = {}
    signing[mode] = doc
    metadata["signing_keys"] = signing
    merchant.metadata = metadata
    merchant.save(update_fields=["metadata", "updated_at"])


def _masked(secret: str) -> str:
    if not secret:
        return ""
    if len(secret) <= 16:
        return secret
    return f"{secret[:12]}...{secret[-6:]}"


def ensure_signing_key(environment) -> str:
    current = environment.webhook_secret
    if current:
        return current
    current = _new_signing_secret()
    environment.webhook_secret = current
    environment.save(update_fields=["webhook_secret_encrypted", "updated_at"])
    return current


def signing_key_payload(environment) -> dict:
    primary = ensure_signing_key(environment)
    doc = _mode_doc(environment.merchant, environment.mode)
    previous = decrypt(doc.get("previous_encrypted", ""))
    return {
        "mode": environment.mode,
        "primary": primary,
        "primary_masked": _masked(primary),
        "previous": previous,
        "previous_masked": _masked(previous),
        "rotated_at": doc.get("rotated_at"),
        "previous_expires_at": doc.get("previous_expires_at"),
        "grace_hours": int(doc.get("grace_hours") or 0),
    }


def rotate_signing_key(*, environment, grace_hours: int, actor_user=None, request=None) -> dict:
    previous = ensure_signing_key(environment)
    primary = _new_signing_secret()
    now = timezone.now()
    environment.webhook_secret = primary
    environment.save(update_fields=["webhook_secret_encrypted", "updated_at"])
    _save_mode_doc(
        environment.merchant,
        environment.mode,
        {
            "previous_encrypted": encrypt(previous),
            "rotated_at": now.isoformat(),
            "previous_expires_at": (now + timedelta(hours=grace_hours)).isoformat(),
            "grace_hours": grace_hours,
        },
    )
    log_event(
        action="accounts.signing_key_rotated",
        actor_user=actor_user,
        merchant=environment.merchant,
        environment=environment,
        target_type="Environment",
        target_id=str(environment.id),
        metadata={"mode": environment.mode, "grace_hours": grace_hours},
        request=request,
    )
    return signing_key_payload(environment)
