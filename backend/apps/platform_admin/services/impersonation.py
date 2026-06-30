"""Issue and consume short-lived impersonation tokens for the
"Open as merchant" flow on the platform-admin merchant detail page.

A platform Owner clicks **Open as merchant** in the admin console;
the FE calls :func:`issue_impersonation_token` which returns a
backend-side URL of the form::

    {BACKEND}/api/v1/auth/impersonate?token=<signed>

The FE opens that URL in a new tab; the consume view (in
``apps.accounts.views``) verifies the signature, signs the chosen
``User`` in via Django session auth, preserves the platform admin's
own session key so the admin tab remains authenticated, and HTTP
redirects to the merchant dashboard root.

Tokens carry ``user_id:admin_id`` and are signed with
``django.core.signing.TimestampSigner``. They expire after
``IMPERSONATION_TTL_SECONDS`` (5 minutes).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from django.conf import settings
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from django.http import HttpRequest

from apps.accounts.models import Role, TeamMember, User
from apps.audit.services.log_event import log_event

from ..models import PlatformAdmin

IMPERSONATION_SALT = "platform-admin.impersonate.v1"
IMPERSONATION_TTL_SECONDS = 5 * 60  # 5 minutes


class ImpersonationError(Exception):
    """Generic failure during impersonation issuance/consumption."""


class MerchantNotImpersonableError(ImpersonationError):
    """Raised when no active user can be located for the merchant."""


@dataclass(frozen=True)
class ImpersonationTokenResult:
    token: str
    redirect_url: str
    user_id: str
    user_email: str
    user_name: str


def _signer() -> TimestampSigner:
    return TimestampSigner(salt=IMPERSONATION_SALT)


def _backend_base_url(request: HttpRequest | None) -> str:
    """Resolve the backend base URL used to construct the consume URL."""
    explicit = getattr(settings, "BACKEND_BASE_URL", None)
    if explicit:
        return str(explicit).rstrip("/")
    if request is not None:
        try:
            scheme = "https" if request.is_secure() else "http"
            host = request.get_host()
            return f"{scheme}://{host}".rstrip("/")
        except Exception:
            pass
    return "http://localhost:8000"


def _merchant_dashboard_url() -> str:
    urls = getattr(settings, "SUBPILOT_FRONTEND_URLS", {}) or {}
    return str(urls.get("merchant") or "http://localhost:5173").rstrip("/")


def _resolve_impersonation_target(merchant_id: str) -> User:
    """Pick the best user to impersonate for ``merchant_id``.

    Preference order:
      1. An active Owner team member.
      2. Any active team member, oldest-first.
    """
    owner = (
        TeamMember.objects.select_related("user")
        .filter(
            merchant_id=merchant_id,
            status=TeamMember.Status.ACTIVE,
            user__is_active=True,
            role=Role.OWNER,
        )
        .order_by("created_at")
        .first()
    )
    if owner is not None:
        return owner.user
    fallback = (
        TeamMember.objects.select_related("user")
        .filter(
            merchant_id=merchant_id,
            status=TeamMember.Status.ACTIVE,
            user__is_active=True,
        )
        .order_by("created_at")
        .first()
    )
    if fallback is not None:
        return fallback.user
    raise MerchantNotImpersonableError(
        "No active user is associated with this merchant — invite one before impersonating."
    )


def issue_impersonation_token(
    *,
    merchant_id: str,
    admin: Optional[PlatformAdmin],
    request: HttpRequest | None = None,
) -> ImpersonationTokenResult:
    """Mint a signed, short-lived impersonation URL for ``merchant_id``."""
    if admin is None:
        raise ImpersonationError("Authentication required.")
    user = _resolve_impersonation_target(merchant_id)
    payload = f"{user.id}:{admin.id}"
    token = _signer().sign(payload)
    redirect_url = f"{_backend_base_url(request)}/api/v1/auth/impersonate?token={token}"
    log_event(
        action="platform.merchant.impersonate.issue",
        actor_user=None,
        actor_label=getattr(admin, "display_name", "") or getattr(admin, "email", ""),
        actor_role="platform_admin",
        target_type="merchant",
        target_id=str(merchant_id),
        metadata={
            "user_id": str(user.id),
            "user_email": user.email,
            "ttl_seconds": IMPERSONATION_TTL_SECONDS,
        },
        request=request,
    )
    return ImpersonationTokenResult(
        token=token,
        redirect_url=redirect_url,
        user_id=str(user.id),
        user_email=user.email,
        user_name=user.display_name or user.get_full_name() or user.email,
    )


@dataclass(frozen=True)
class ConsumedImpersonation:
    user: User
    admin_id: str


def consume_impersonation_token(token: str) -> ConsumedImpersonation:
    """Verify a signed impersonation token and return the target user.

    Raises :class:`ImpersonationError` for any verification or lookup
    failure. Caller is responsible for actually establishing the
    Django session (``django.contrib.auth.login``).
    """
    if not token:
        raise ImpersonationError("Missing impersonation token.")
    try:
        payload = _signer().unsign(token, max_age=IMPERSONATION_TTL_SECONDS)
    except SignatureExpired as exc:
        raise ImpersonationError("Impersonation link has expired. Generate a new one.") from exc
    except BadSignature as exc:
        raise ImpersonationError("Invalid impersonation link.") from exc
    parts = payload.split(":", 1)
    if len(parts) != 2:
        raise ImpersonationError("Malformed impersonation payload.")
    user_id, admin_id = parts
    try:
        user = User.objects.get(pk=user_id, is_active=True)
    except User.DoesNotExist as exc:
        raise ImpersonationError("Target user no longer exists.") from exc
    return ConsumedImpersonation(user=user, admin_id=admin_id)


def merchant_dashboard_url() -> str:
    """Public accessor for the consume view to redirect to."""
    return _merchant_dashboard_url()


__all__ = [
    "ImpersonationError",
    "MerchantNotImpersonableError",
    "ImpersonationTokenResult",
    "ConsumedImpersonation",
    "issue_impersonation_token",
    "consume_impersonation_token",
    "merchant_dashboard_url",
    "IMPERSONATION_TTL_SECONDS",
]
