"""DRF permission classes for the platform admin console."""
from __future__ import annotations

from rest_framework.permissions import BasePermission

from .models import PlatformAdmin, PlatformAdminRole, PlatformAdminStatus


class IsPlatformAdmin(BasePermission):
    """Authenticated as a (non-suspended) ``PlatformAdmin``.

    Strictly checks ``isinstance(request.user, PlatformAdmin)`` — does NOT
    look at ``is_staff``. This intentionally rejects merchant users even
    if they have ``is_staff=True`` so that platform endpoints stay walled
    off from the merchant auth domain.
    """

    message = "Platform admin session required."

    def has_permission(self, request, view) -> bool:
        user = getattr(request, "user", None)
        return (
            isinstance(user, PlatformAdmin)
            and user.status == PlatformAdminStatus.ACTIVE
        )


def IsPlatformAdminRole(*roles: str) -> type[BasePermission]:  # noqa: N802 - factory looks like a class
    """Permission factory: ``permission_classes = [IsPlatformAdminRole("owner")]``."""

    allowed = {r.lower() for r in roles}

    class _IsPlatformAdminRole(BasePermission):
        message = f"Requires one of platform roles: {sorted(allowed)}"

        def has_permission(self, request, view) -> bool:  # type: ignore[override]
            user = getattr(request, "user", None)
            if not isinstance(user, PlatformAdmin):
                return False
            if user.status != PlatformAdminStatus.ACTIVE:
                return False
            return user.role in allowed

    _IsPlatformAdminRole.__name__ = f"IsPlatformAdminRole_{'_'.join(sorted(allowed))}"
    return _IsPlatformAdminRole


# Convenience: writes that require Owner-only privileges.
IsPlatformOwner = IsPlatformAdminRole(PlatformAdminRole.OWNER)
# Operator+ (owner OR operator).
IsPlatformOperatorOrOwner = IsPlatformAdminRole(
    PlatformAdminRole.OWNER, PlatformAdminRole.OPERATOR
)
