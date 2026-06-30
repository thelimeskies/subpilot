"""Email-token issuance and consumption.

Tokens use the same prefix the FE expects (``verify_*``, ``reset_*``).
"""
from __future__ import annotations

from typing import Any

from django.db import transaction

from apps.common import time as t
from apps.common.crypto import generate_token

from ..models import EmailVerificationToken, PasswordResetToken, User

VERIFY_TTL_HOURS = 24
RESET_TTL_HOURS = 2


def issue_verification_token(
    *, email: str, pending_payload: dict[str, Any] | None = None, user: User | None = None
) -> EmailVerificationToken:
    return EmailVerificationToken.objects.create(
        user=user,
        email=email.lower(),
        token=generate_token("verify"),
        pending_payload=pending_payload or {},
        expires_at=t.in_hours(VERIFY_TTL_HOURS),
    )


def consume_verification_token(token: str) -> EmailVerificationToken | None:
    """Atomically mark a verification token as used. Returns the row, or None."""
    with transaction.atomic():
        try:
            tok = EmailVerificationToken.objects.select_for_update().get(token=token)
        except EmailVerificationToken.DoesNotExist:
            return None
        if tok.used_at is not None:
            return None
        if t.is_expired(tok.expires_at):
            return None
        tok.used_at = t.utcnow()
        tok.save(update_fields=["used_at", "updated_at"])
        return tok


def issue_password_reset_token(*, user: User) -> PasswordResetToken:
    return PasswordResetToken.objects.create(
        user=user,
        token=generate_token("reset"),
        expires_at=t.in_hours(RESET_TTL_HOURS),
    )


def consume_password_reset_token(token: str) -> PasswordResetToken | None:
    with transaction.atomic():
        try:
            tok = PasswordResetToken.objects.select_for_update().select_related("user").get(token=token)
        except PasswordResetToken.DoesNotExist:
            return None
        if tok.used_at is not None or t.is_expired(tok.expires_at):
            return None
        tok.used_at = t.utcnow()
        tok.save(update_fields=["used_at", "updated_at"])
        return tok
