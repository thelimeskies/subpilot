"""Write actions for platform-admin team management (S9).

* :func:`invite_admin` — Owner-only. Creates a fresh ``PlatformAdmin`` in
  ``INVITED`` state and mints a single-use ``PlatformInviteToken`` valid
  for 24h. Emits ``platform.team.invite``.
* :func:`accept_invite` — Resolves a token, sets the admin's password,
  flips status to ``ACTIVE`` and stamps the token's ``accepted_at``.
* :func:`update_admin` — Owner-only. Patches role / status / display_name.
* :func:`suspend_admin` — Owner-only. Sets status=SUSPENDED.
* :func:`reactivate_admin` — Owner-only. Sets status=ACTIVE.

The mail step uses Django's configured email backend; in dev that is the
console/locmem backend so the script keeps working without MailHog. In
production the same code path will route through the real backend.
"""
from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import timedelta

from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from apps.audit.services.log_event import log_event

from ..models import (
    PlatformAdmin,
    PlatformAdminRole,
    PlatformAdminStatus,
    PlatformInviteToken,
)
from ..selectors.team import normalize_role, normalize_status


INVITE_TTL = timedelta(hours=24)


class TeamFieldError(ValueError):
    """Raised on bad input to a team write action."""


class TeamNotFoundError(LookupError):
    """Raised when the target admin cannot be found."""


class InviteTokenError(ValueError):
    """Raised when an invite token is invalid / expired / already used."""


def _actor_label(admin: PlatformAdmin | None) -> str:
    if admin is None:
        return "platform-admin"
    return admin.display_name or admin.email or "platform-admin"


# --- Invite ---------------------------------------------------------------


@dataclass(frozen=True)
class InviteResult:
    admin: PlatformAdmin
    token: PlatformInviteToken
    invite_url: str


def _build_invite_url(token: str) -> str:
    """Build the FE acceptance URL. Uses ``ADMIN_BASE_URL`` if defined,
    otherwise points at the dev FE on :5175."""
    from django.conf import settings

    base = getattr(settings, "ADMIN_BASE_URL", None) or "http://localhost:5175"
    return f"{base.rstrip('/')}/accept-invite?token={token}"


@transaction.atomic
def invite_admin(
    *,
    email: str,
    display_name: str = "",
    role: str = "operator",
    invited_by: PlatformAdmin,
    request=None,
) -> InviteResult:
    if invited_by is None or invited_by.role != PlatformAdminRole.OWNER:
        raise TeamFieldError("Only platform Owners can invite teammates.")

    email = (email or "").strip().lower()
    if not email or "@" not in email:
        raise TeamFieldError("A valid email is required.")

    norm_role = normalize_role(role) or PlatformAdminRole.OPERATOR
    if norm_role == PlatformAdminRole.OWNER:
        # Allow owners to invite owners — keeps S9 simple.
        pass

    if PlatformAdmin.objects.filter(email__iexact=email).exists():
        raise TeamFieldError("An admin with that email already exists.")

    admin = PlatformAdmin.objects.create(
        email=email,
        display_name=(display_name or "").strip() or email.split("@")[0].title(),
        role=norm_role,
        status=PlatformAdminStatus.INVITED,
    )
    # No password yet — accept_invite will set it.

    raw_token = secrets.token_urlsafe(32)
    token = PlatformInviteToken.objects.create(
        admin=admin,
        token=raw_token,
        expires_at=timezone.now() + INVITE_TTL,
    )

    invite_url = _build_invite_url(raw_token)

    # Best-effort email. Never fail the request because the email backend
    # had a hiccup — the token row + audit log keep us honest.
    try:
        send_mail(
            subject="You've been invited to SubPilot Platform Admin",
            message=(
                f"Hello {admin.display_name},\n\n"
                f"{_actor_label(invited_by)} has invited you to the SubPilot "
                f"Platform Admin console.\n\n"
                f"Accept your invite within 24 hours: {invite_url}\n\n"
                "If you weren't expecting this email, you can ignore it."
            ),
            from_email=None,
            recipient_list=[admin.email],
            fail_silently=True,
        )
    except Exception:  # pragma: no cover - belt and suspenders
        pass

    log_event(
        action="platform.team.invite",
        actor_user=None,
        actor_label=_actor_label(invited_by),
        actor_role="platform_admin",
        merchant=None,
        target_type="platform_admin",
        target_id=str(admin.id),
        metadata={
            "email": admin.email,
            "role": admin.role,
            "expires_at": token.expires_at.isoformat(),
        },
        request=request,
    )

    return InviteResult(admin=admin, token=token, invite_url=invite_url)


# --- Accept invite --------------------------------------------------------


@transaction.atomic
def accept_invite(
    *,
    token_value: str,
    password: str,
    display_name: str | None = None,
    request=None,
) -> PlatformAdmin:
    if not password or len(password) < 8:
        raise InviteTokenError("Password must be at least 8 characters.")

    try:
        token = PlatformInviteToken.objects.select_for_update().select_related("admin").get(
            token=token_value or ""
        )
    except PlatformInviteToken.DoesNotExist as exc:
        raise InviteTokenError("Invite is invalid or already used.") from exc

    if token.accepted_at is not None:
        raise InviteTokenError("Invite has already been accepted.")
    if token.expires_at and token.expires_at < timezone.now():
        raise InviteTokenError("Invite has expired.")

    admin = token.admin
    admin.set_password(password)
    if display_name:
        admin.display_name = display_name.strip()[:128]
    admin.status = PlatformAdminStatus.ACTIVE
    admin.save()

    token.accepted_at = timezone.now()
    token.save(update_fields=["accepted_at", "updated_at"])

    log_event(
        action="platform.team.accept_invite",
        actor_user=None,
        actor_label=_actor_label(admin),
        actor_role="platform_admin",
        merchant=None,
        target_type="platform_admin",
        target_id=str(admin.id),
        metadata={"email": admin.email},
        request=request,
    )
    return admin


# --- Update / Suspend / Reactivate ---------------------------------------


def _ensure_owner(actor: PlatformAdmin | None) -> None:
    if actor is None or actor.role != PlatformAdminRole.OWNER:
        raise TeamFieldError("Only platform Owners can perform this action.")


def _resolve_admin(admin_id: str) -> PlatformAdmin:
    try:
        return PlatformAdmin.objects.get(pk=admin_id)
    except (PlatformAdmin.DoesNotExist, ValueError, TypeError) as exc:
        raise TeamNotFoundError("Admin not found.") from exc


@transaction.atomic
def update_admin(
    *,
    admin_id: str,
    actor: PlatformAdmin | None,
    request=None,
    role: str | None = None,
    status: str | None = None,
    display_name: str | None = None,
    mfa_enabled: bool | None = None,
) -> PlatformAdmin:
    _ensure_owner(actor)
    target = _resolve_admin(admin_id)

    changed: dict[str, tuple] = {}

    if role is not None:
        norm = normalize_role(role)
        if norm is None:
            raise TeamFieldError("role is invalid.")
        if target.role != norm:
            # Guard: don't allow an Owner to demote themselves to non-owner
            # if they are the LAST owner — would lock the platform out.
            if target.id == actor.id and norm != PlatformAdminRole.OWNER:
                last_owner = (
                    PlatformAdmin.objects.filter(role=PlatformAdminRole.OWNER)
                    .exclude(id=target.id)
                    .exists()
                )
                if not last_owner:
                    raise TeamFieldError(
                        "Cannot demote the last remaining Owner."
                    )
            changed["role"] = (target.role, norm)
            target.role = norm

    if status is not None:
        norm_st = normalize_status(status)
        if norm_st is None:
            raise TeamFieldError("status is invalid.")
        if target.status != norm_st:
            changed["status"] = (target.status, norm_st)
            target.status = norm_st

    if display_name is not None and display_name != target.display_name:
        changed["display_name"] = (target.display_name, display_name)
        target.display_name = display_name.strip()[:128]

    if mfa_enabled is not None and bool(mfa_enabled) != bool(target.mfa_enabled):
        changed["mfa_enabled"] = (target.mfa_enabled, bool(mfa_enabled))
        target.mfa_enabled = bool(mfa_enabled)

    if changed:
        target.save()
        log_event(
            action="platform.team.update",
            actor_user=None,
            actor_label=_actor_label(actor),
            actor_role="platform_admin",
            merchant=None,
            target_type="platform_admin",
            target_id=str(target.id),
            metadata={
                "changes": {k: {"from": v[0], "to": v[1]} for k, v in changed.items()},
            },
            request=request,
        )
    return target


@transaction.atomic
def suspend_admin(
    *,
    admin_id: str,
    actor: PlatformAdmin | None,
    request=None,
) -> PlatformAdmin:
    _ensure_owner(actor)
    target = _resolve_admin(admin_id)
    if target.id == actor.id:
        raise TeamFieldError("You cannot suspend your own account.")
    # If we're suspending the last active Owner, refuse.
    if target.role == PlatformAdminRole.OWNER:
        active_owners = (
            PlatformAdmin.objects.filter(
                role=PlatformAdminRole.OWNER, status=PlatformAdminStatus.ACTIVE
            )
            .exclude(id=target.id)
            .exists()
        )
        if not active_owners:
            raise TeamFieldError("Cannot suspend the last active Owner.")

    if target.status != PlatformAdminStatus.SUSPENDED:
        prev = target.status
        target.status = PlatformAdminStatus.SUSPENDED
        target.save(update_fields=["status", "updated_at"])
        log_event(
            action="platform.team.suspend",
            actor_user=None,
            actor_label=_actor_label(actor),
            actor_role="platform_admin",
            merchant=None,
            target_type="platform_admin",
            target_id=str(target.id),
            metadata={"from": prev, "to": target.status, "email": target.email},
            request=request,
        )
    return target


@transaction.atomic
def reactivate_admin(
    *,
    admin_id: str,
    actor: PlatformAdmin | None,
    request=None,
) -> PlatformAdmin:
    _ensure_owner(actor)
    target = _resolve_admin(admin_id)
    if target.status != PlatformAdminStatus.ACTIVE:
        prev = target.status
        target.status = PlatformAdminStatus.ACTIVE
        target.save(update_fields=["status", "updated_at"])
        log_event(
            action="platform.team.reactivate",
            actor_user=None,
            actor_label=_actor_label(actor),
            actor_role="platform_admin",
            merchant=None,
            target_type="platform_admin",
            target_id=str(target.id),
            metadata={"from": prev, "to": target.status, "email": target.email},
            request=request,
        )
    return target


__all__ = [
    "TeamFieldError",
    "TeamNotFoundError",
    "InviteTokenError",
    "InviteResult",
    "INVITE_TTL",
    "invite_admin",
    "accept_invite",
    "update_admin",
    "suspend_admin",
    "reactivate_admin",
]
