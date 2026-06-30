"""High-level authentication services.

These service functions are the *only* place that mutates auth state. Views
just translate request payloads into service calls and serialize the result.

Per the plan, the FE contract is non-negotiable:

* Errors flow back as a ``reason`` string the FE can render verbatim.
* Successful sign-in returns ``MerchantUser``; MFA-required returns a
  ``challengeId``; sign-up returns the bare ``verifyToken``.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from django.contrib.auth import authenticate
from django.contrib.auth.hashers import make_password
from django.db import IntegrityError, transaction
from django.utils.text import slugify

from apps.audit.services.log_event import log_event

from ..models import (
    Environment,
    MfaChallenge,
    Merchant,
    Role,
    TeamMember,
    User,
)
from . import email_tokens, mfa


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SignUpResult:
    ok: bool
    verify_token: str = ""
    reason: str = ""


@dataclass(frozen=True)
class SignInResult:
    ok: bool
    user: User | None = None
    requires_mfa: bool = False
    challenge_id: str = ""
    reason: str = ""


@dataclass(frozen=True)
class VerifyEmailResult:
    ok: bool
    user: User | None = None
    reason: str = ""


# ---------------------------------------------------------------------------
# Validation helpers (FE-equivalent rules)
# ---------------------------------------------------------------------------

_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def _password_ok(password: str) -> bool:
    if len(password) < 8:
        return False
    return all(
        [
            re.search(r"[A-Z]", password) is not None,
            re.search(r"\d", password) is not None,
            re.search(r"[^A-Za-z0-9]", password) is not None,
        ]
    )


# ---------------------------------------------------------------------------
# Sign-up  (defers User creation until verify_email_and_create_account)
# ---------------------------------------------------------------------------


def signup_merchant(*, full_name: str, email: str, password: str, org_name: str) -> SignUpResult:
    if len(full_name.strip()) < 2:
        return SignUpResult(ok=False, reason="Please enter your full name.")
    if not _EMAIL_RE.match(email.strip()):
        return SignUpResult(ok=False, reason="Enter a valid work email.")
    if len(org_name.strip()) < 2:
        return SignUpResult(ok=False, reason="Workspace name is required.")
    if not _password_ok(password):
        return SignUpResult(ok=False, reason="Password does not meet the strength requirements.")

    normalized = email.strip().lower()
    if User.objects.filter(email=normalized).exists():
        return SignUpResult(
            ok=False,
            reason="An account already exists for this email. Try signing in instead.",
        )

    payload = {
        "fullName": full_name.strip(),
        "orgName": org_name.strip(),
        "passwordHash": make_password(password),  # Argon2 by settings
    }
    token = email_tokens.issue_verification_token(email=normalized, pending_payload=payload)

    # Audit: sign-up initiated.
    log_event(
        action="auth.signup_initiated",
        actor_label=normalized,
        target_type="email",
        target_id=normalized,
    )

    # Email is sent by the view layer (so it can use ``request.scheme`` for the link).
    return SignUpResult(ok=True, verify_token=token.token)


# ---------------------------------------------------------------------------
# Verify email  (creates User + Merchant + Environment(test/live) + TeamMember)
# ---------------------------------------------------------------------------


@transaction.atomic
def verify_email_and_create_account(token: str) -> VerifyEmailResult:
    record = email_tokens.consume_verification_token(token)
    if record is None:
        return VerifyEmailResult(ok=False, reason="This verification link is invalid or has expired.")

    # Pre-existing user being verified (rare, e.g. resend after admin invite).
    if record.user_id is not None:
        user = record.user
        user.email_verified = True
        user.save(update_fields=["email_verified", "updated_at"])
        return VerifyEmailResult(ok=True, user=user)

    payload: dict[str, Any] = record.pending_payload or {}
    email = record.email
    full_name = payload.get("fullName", "")
    org_name = payload.get("orgName", "")
    password_hash = payload.get("passwordHash", "")

    # Final guard: someone else may have signed up with this email between
    # ``signup_merchant`` and the verification click.
    if User.objects.filter(email=email).exists():
        return VerifyEmailResult(ok=False, reason="An account already exists for this email.")

    user = User.objects.create(
        email=email,
        username=email,
        display_name=full_name,
        password=password_hash,  # already-hashed; bypass set_password
        email_verified=True,
        is_active=True,
    )

    merchant = _create_merchant_with_unique_slug(name=org_name)
    Environment.objects.create(merchant=merchant, mode=Environment.Mode.TEST)
    Environment.objects.create(merchant=merchant, mode=Environment.Mode.LIVE)
    TeamMember.objects.create(
        merchant=merchant,
        user=user,
        role=Role.OWNER,
        status=TeamMember.Status.ACTIVE,
    )

    log_event(
        action="auth.email_verified_account_created",
        actor_user=user,
        actor_label=user.email,
        actor_role=Role.OWNER,
        merchant=merchant,
        target_type="user",
        target_id=str(user.id),
    )
    return VerifyEmailResult(ok=True, user=user)


def _create_merchant_with_unique_slug(*, name: str) -> Merchant:
    """Create a merchant, falling back to slug suffixes if the base slug collides."""
    base_slug = slugify(name) or "workspace"
    slug = base_slug
    n = 0
    while True:
        try:
            with transaction.atomic():
                return Merchant.objects.create(name=name, slug=slug)
        except IntegrityError:
            n += 1
            slug = f"{base_slug}-{n}"
            if n > 50:
                raise


# ---------------------------------------------------------------------------
# Sign-in  (returns MFA challenge for users with mfa_enabled=True)
# ---------------------------------------------------------------------------


def sign_in(*, email: str, password: str, request=None) -> SignInResult:
    normalized = email.strip().lower()
    user = authenticate(request=request, username=normalized, password=password)
    if user is None:
        log_event(
            action="auth.signin_failed",
            actor_label=normalized,
            target_type="email",
            target_id=normalized,
            request=request,
        )
        return SignInResult(
            ok=False,
            reason="Email or password did not match a SubPilot merchant account.",
        )

    if not user.is_active:
        return SignInResult(ok=False, reason="This account is not active.")
    if not user.email_verified:
        return SignInResult(
            ok=False,
            reason="Please verify your email before signing in. Check your inbox for the verification link.",
        )

    if user.mfa_enabled:
        challenge: MfaChallenge = mfa.start_challenge(user)
        log_event(
            action="auth.signin_mfa_challenge",
            actor_user=user,
            actor_label=user.email,
            target_type="user",
            target_id=str(user.id),
            request=request,
        )
        return SignInResult(ok=True, requires_mfa=True, challenge_id=challenge.challenge_id)

    log_event(
        action="auth.signin_success",
        actor_user=user,
        actor_label=user.email,
        target_type="user",
        target_id=str(user.id),
        request=request,
    )
    return SignInResult(ok=True, user=user)


# ---------------------------------------------------------------------------
# Password reset
# ---------------------------------------------------------------------------


def request_password_reset(*, email: str) -> tuple[bool, str, str]:
    """Returns (ok, reason, token). Reason is empty on success."""
    normalized = email.strip().lower()
    user = User.objects.filter(email=normalized).first()
    if user is None:
        # Plan & FE expect us to *not* enumerate, but the demo FE shows the
        # token only when the email matches a real account. We mirror that:
        # reveal "no account" since the FE relies on it for demo flow.
        return False, "No SubPilot account uses that email.", ""

    token = email_tokens.issue_password_reset_token(user=user)
    log_event(
        action="auth.password_reset_requested",
        actor_user=user,
        actor_label=user.email,
        target_type="user",
        target_id=str(user.id),
    )
    return True, "", token.token


def reset_password(*, token: str, new_password: str) -> tuple[bool, str]:
    if not _password_ok(new_password):
        return False, "Password does not meet the strength requirements."

    record = email_tokens.consume_password_reset_token(token)
    if record is None:
        return False, "This reset link is invalid or has expired."

    user = record.user
    user.set_password(new_password)
    user.save(update_fields=["password", "updated_at"])
    log_event(
        action="auth.password_reset_completed",
        actor_user=user,
        actor_label=user.email,
        target_type="user",
        target_id=str(user.id),
    )
    return True, ""
