"""DRF permission classes for the accounts/RBAC layer."""
from __future__ import annotations

from rest_framework.permissions import BasePermission

from .models import ApiKey
from .rbac import has_capability

READ_SCOPE_CAPABILITIES = {
    "view_dashboard",
    "view_customers",
    "view_payment_methods_masked",
    "view_event_logs",
    "view_audit_logs",
    "preview_proration",
    "export_invoices",
    "export_workspace_data",
}

WRITE_SCOPE_CAPABILITIES = {
    "create_customer",
    "create_subscription",
    "create_payment_method_session",
    "pause_resume_subscription",
    "cancel_subscription",
    "retry_invoice",
}

ADMIN_SCOPE_CAPABILITIES = {
    "create_product",
    "edit_product",
    "create_plan",
    "edit_plan",
    "activate_archive_plan",
    "apply_credit_note",
    "refund_payment",
    "void_invoice",
    "mark_uncollectible",
    "manage_dunning_policies",
    "replay_webhooks",
    "manage_webhook_endpoints",
    "manage_api_keys",
}


def api_key_has_capability(api_key: ApiKey, capability: str) -> bool:
    scopes = set(api_key.scopes or [])
    if "admin" in scopes and capability in ADMIN_SCOPE_CAPABILITIES:
        return True
    if "write" in scopes and capability in WRITE_SCOPE_CAPABILITIES:
        return True
    if "read" in scopes and capability in READ_SCOPE_CAPABILITIES:
        return True
    return False


def HasCapability(capability_name: str) -> type[BasePermission]:  # noqa: N802 - factory looks like a class
    """Permission factory: ``permission_classes = [HasCapability("retry_invoice")]``.

    Reads the role from ``request.team_member.role`` (set by
    ``TenantContextMiddleware``). API-key requests are authorized against the
    key's read/write/admin scopes. Platform operators authenticate via Django
    staff and bypass the merchant-scoped check.
    """

    class _HasCapability(BasePermission):
        message = f"Your role does not allow {capability_name}."

        def has_permission(self, request, view) -> bool:  # type: ignore[override]
            user = getattr(request, "user", None)
            if not user or not user.is_authenticated:
                return False
            # Platform staff bypass merchant-scoped capability checks.
            if getattr(user, "is_staff", False):
                return True
            auth = getattr(request, "auth", None)
            if isinstance(auth, ApiKey):
                return api_key_has_capability(auth, capability_name)
            tm = getattr(request, "team_member", None)
            if tm is None:
                return False
            return has_capability(tm.role, capability_name)

    _HasCapability.__name__ = f"HasCapability_{capability_name}"
    return _HasCapability


class IsTenantMember(BasePermission):
    """Authenticated user must have an active ``TeamMember`` for the resolved merchant."""

    def has_permission(self, request, view) -> bool:
        tm = getattr(request, "team_member", None)
        return tm is not None and tm.status == "active"


class IsPlatformOperator(BasePermission):
    """SubPilot internal staff (Platform Operator role)."""

    def has_permission(self, request, view) -> bool:
        user = getattr(request, "user", None)
        return bool(user and user.is_authenticated and getattr(user, "is_staff", False))
