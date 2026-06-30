"""Shared DRF permission classes / helpers."""
from __future__ import annotations

from rest_framework.permissions import BasePermission


class IsAuthenticatedAndActive(BasePermission):
    """Authenticated user whose underlying account is still active."""

    def has_permission(self, request, view) -> bool:
        user = getattr(request, "user", None)
        return bool(user and user.is_authenticated and getattr(user, "is_active", True))


class IsPlatformOperator(BasePermission):
    """SubPilot internal staff (Platform Operator role)."""

    def has_permission(self, request, view) -> bool:
        user = getattr(request, "user", None)
        return bool(user and user.is_authenticated and getattr(user, "is_staff", False))


class HasTenantContext(BasePermission):
    """Request must have ``request.merchant`` and ``request.environment`` set.

    Set by :class:`apps.accounts.middleware.TenantContextMiddleware`. Platform
    staff are exempt because they pick the tenant via query parameter at the
    view layer.
    """

    message = "No active merchant/environment for this request."

    def has_permission(self, request, view) -> bool:
        user = getattr(request, "user", None)
        if user and getattr(user, "is_staff", False):
            return True
        return bool(getattr(request, "merchant", None) and getattr(request, "environment", None))

