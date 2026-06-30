"""Auth service for platform admins.

Pure business logic — views handle HTTP only. Sign-in writes
``_platform_admin_id`` into Django's session; sign-out clears it.
"""
from __future__ import annotations

from dataclasses import dataclass

from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.http import HttpRequest

from apps.audit.services.log_event import log_event

from ..authentication import SESSION_KEY
from ..models import PlatformAdmin, PlatformAdminStatus


class InvalidCredentialsError(Exception):
    pass


class SuspendedAdminError(Exception):
    pass


class ProfileUpdateError(ValueError):
    """Raised on invalid profile patches (bad email, duplicate, empty name)."""


@dataclass
class SignInResult:
    admin: PlatformAdmin


def sign_in(*, email: str, password: str, request: HttpRequest) -> SignInResult:
    """Authenticate by email + password. Raises on failure."""
    email = (email or "").strip().lower()
    try:
        admin = PlatformAdmin.objects.get(email=email)
    except PlatformAdmin.DoesNotExist:
        raise InvalidCredentialsError("Email or password did not match a SubPilot admin account.")

    if not admin.check_password(password):
        raise InvalidCredentialsError("Email or password did not match a SubPilot admin account.")

    if admin.status == PlatformAdminStatus.SUSPENDED:
        raise SuspendedAdminError("This admin account is suspended.")
    if admin.status == PlatformAdminStatus.INVITED:
        # Invited accounts must accept the invite first (S9). For S1 we treat
        # them as not-yet-active.
        raise SuspendedAdminError("Accept your invite before signing in.")

    # Establish session — distinct key so we never collide with merchant auth.
    request.session[SESSION_KEY] = str(admin.id)
    request.session.modified = True
    admin.touch_login()

    log_event(
        action="platform.auth.sign_in",
        actor_user=None,
        actor_label=admin.email,
        actor_role="platform_admin",
        target_type="platform_admin",
        target_id=str(admin.id),
        request=request,
    )
    return SignInResult(admin=admin)


def sign_out(*, request: HttpRequest) -> None:
    admin = getattr(request, "user", None)
    if isinstance(admin, PlatformAdmin):
        log_event(
            action="platform.auth.sign_out",
            actor_user=None,
            actor_label=admin.email,
            actor_role="platform_admin",
            target_type="platform_admin",
            target_id=str(admin.id),
            request=request,
        )
    if hasattr(request, "session"):
        request.session.pop(SESSION_KEY, None)
        request.session.modified = True


def update_profile(
    *,
    admin: PlatformAdmin,
    display_name: str | None = None,
    email: str | None = None,
    request: HttpRequest | None = None,
) -> PlatformAdmin:
    """Patch the authenticated admin's profile fields.

    Only ``display_name`` and ``email`` are user-editable here. Role,
    status, password and MFA state are managed by other flows (Team
    management, password rotation, MFA setup) so we deliberately do not
    accept them on this endpoint.
    """
    update_fields: list[str] = []
    changed: dict[str, dict[str, str]] = {}

    if display_name is not None:
        new_name = str(display_name).strip()
        if not new_name:
            raise ProfileUpdateError("Display name cannot be empty.")
        if len(new_name) > 128:
            raise ProfileUpdateError("Display name is too long (max 128 characters).")
        if new_name != (admin.display_name or ""):
            changed["display_name"] = {"from": admin.display_name or "", "to": new_name}
            admin.display_name = new_name
            update_fields.append("display_name")

    if email is not None:
        new_email = str(email).strip().lower()
        if not new_email:
            raise ProfileUpdateError("Email cannot be empty.")
        try:
            validate_email(new_email)
        except ValidationError:
            raise ProfileUpdateError("Enter a valid email address.") from None
        if new_email != (admin.email or "").lower():
            if PlatformAdmin.objects.filter(email=new_email).exclude(pk=admin.pk).exists():
                raise ProfileUpdateError("That email is already in use.")
            changed["email"] = {"from": admin.email or "", "to": new_email}
            admin.email = new_email
            update_fields.append("email")

    if update_fields:
        update_fields.append("updated_at")
        try:
            admin.save(update_fields=update_fields)
        except IntegrityError:
            raise ProfileUpdateError("That email is already in use.") from None
        log_event(
            action="platform_admin.profile.update",
            actor_user=None,
            actor_label=admin.display_name or admin.email,
            actor_role="platform_admin",
            target_type="platform_admin",
            target_id=str(admin.id),
            metadata={"changes": changed, "fields": [f for f in update_fields if f != "updated_at"]},
            request=request,
        )
    return admin
