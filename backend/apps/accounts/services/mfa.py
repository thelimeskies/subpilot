"""MFA service (TOTP via pyotp + demo bypass).

Per the plan:

- Each user has a Fernet-encrypted ``mfa_secret`` (base32). Demo accounts get a
  freshly-generated secret at seed-time so a real authenticator app *also*
  works alongside the bypass code.
- The bypass code (default ``"123456"``) is unconditionally accepted by demo
  flows so the FE story stays exercisable without a real device. The
  responsibility for enabling/disabling this knob lives in
  ``settings.DEMO_MFA_BYPASS_CODE`` and is documented in the plan.
"""
from __future__ import annotations

import pyotp
from django.conf import settings
from django.db import transaction

from apps.common import time as t
from apps.common.crypto import generate_token

from ..models import MfaChallenge, User

CHALLENGE_TTL_MINUTES = 10


def ensure_mfa_secret(user: User) -> str:
    """Return the user's TOTP secret, creating one if missing."""
    if user.mfa_secret:
        return user.mfa_secret
    secret = pyotp.random_base32()
    user.mfa_secret = secret  # encrypts via property
    user.save(update_fields=["mfa_secret_encrypted", "updated_at"])
    return secret


def start_challenge(user: User) -> MfaChallenge:
    """Begin an MFA challenge for ``user``. Returns the saved row."""
    return MfaChallenge.objects.create(
        user=user,
        challenge_id=generate_token("mfa", n_bytes=12),
        expires_at=t.in_minutes(CHALLENGE_TTL_MINUTES),
    )


def verify_code(user: User, code: str) -> bool:
    """Return True if ``code`` is valid for the user's MFA secret OR matches the demo bypass."""
    code = (code or "").strip()
    if not code.isdigit() or len(code) != 6:
        return False

    bypass = getattr(settings, "DEMO_MFA_BYPASS_CODE", "")
    if bypass and code == bypass:
        return True

    secret = user.mfa_secret
    if not secret:
        return False
    return pyotp.TOTP(secret).verify(code, valid_window=1)


def consume_challenge(challenge_id: str, code: str) -> User | None:
    """Resolve a challenge id + code to the underlying ``User``. Atomic.

    Returns ``None`` if the challenge is unknown, expired, already consumed, or
    the code is invalid.
    """
    with transaction.atomic():
        try:
            ch = MfaChallenge.objects.select_for_update().select_related("user").get(
                challenge_id=challenge_id
            )
        except MfaChallenge.DoesNotExist:
            return None
        if ch.consumed_at is not None or t.is_expired(ch.expires_at):
            return None
        if not verify_code(ch.user, code):
            return None
        ch.consumed_at = t.utcnow()
        ch.save(update_fields=["consumed_at", "updated_at"])
        return ch.user
