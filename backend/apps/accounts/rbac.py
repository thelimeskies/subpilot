"""Declarative RBAC capability matrix.

Mirrors docs/product/rbac-permissions-matrix.md. The keys are stable
capability names referenced by ``HasCapability("retry_invoice")``-style DRF
permission classes, so renaming a key requires a code change *and* an audit
trail review.

Cells in the matrix that are "Limited", "Scoped", "Masked", or "API only" are
modeled as separate capabilities (e.g. ``retry_invoice_limited``) rather than
overloading a single name; the views decide which one to require.
"""
from __future__ import annotations

from .models import Role

# fmt: off
CAPABILITIES: dict[str, set[str]] = {
    # Dashboard & visibility
    "view_dashboard": {Role.OWNER, Role.BILLING_ADMIN, Role.DEVELOPER, Role.FINANCE,
                       Role.SUPPORT, Role.ANALYST, Role.PLATFORM_OPERATOR},

    # Catalog
    "create_product": {Role.OWNER, Role.BILLING_ADMIN},
    "edit_product": {Role.OWNER, Role.BILLING_ADMIN},
    "create_plan": {Role.OWNER, Role.BILLING_ADMIN},
    "edit_plan": {Role.OWNER, Role.BILLING_ADMIN},
    "activate_archive_plan": {Role.OWNER, Role.BILLING_ADMIN},

    # Customers
    "view_customers": {Role.OWNER, Role.BILLING_ADMIN, Role.FINANCE, Role.SUPPORT,
                       Role.ANALYST, Role.PLATFORM_OPERATOR},
    "create_customer": {Role.OWNER, Role.BILLING_ADMIN, Role.SUPPORT, Role.DEVELOPER},

    # Subscriptions
    "create_subscription": {Role.OWNER, Role.BILLING_ADMIN, Role.DEVELOPER},
    "pause_resume_subscription": {Role.OWNER, Role.BILLING_ADMIN, Role.SUPPORT, Role.PLATFORM_OPERATOR},
    "cancel_subscription": {Role.OWNER, Role.BILLING_ADMIN, Role.SUPPORT, Role.PLATFORM_OPERATOR},
    "preview_proration": {Role.OWNER, Role.BILLING_ADMIN, Role.FINANCE, Role.SUPPORT,
                          Role.ANALYST, Role.PLATFORM_OPERATOR},

    # Invoices
    "retry_invoice": {Role.OWNER, Role.BILLING_ADMIN, Role.FINANCE, Role.SUPPORT, Role.PLATFORM_OPERATOR},
    "apply_credit_note": {Role.OWNER, Role.BILLING_ADMIN, Role.FINANCE, Role.PLATFORM_OPERATOR},
    "refund_payment": {Role.OWNER, Role.BILLING_ADMIN, Role.FINANCE, Role.PLATFORM_OPERATOR},
    "void_invoice": {Role.OWNER, Role.BILLING_ADMIN, Role.FINANCE, Role.PLATFORM_OPERATOR},
    "mark_uncollectible": {Role.OWNER, Role.BILLING_ADMIN, Role.FINANCE, Role.PLATFORM_OPERATOR},
    "export_invoices": {Role.OWNER, Role.BILLING_ADMIN, Role.FINANCE, Role.ANALYST, Role.PLATFORM_OPERATOR},

    # Payment methods
    "view_payment_methods_masked": {Role.OWNER, Role.BILLING_ADMIN, Role.FINANCE, Role.SUPPORT,
                                    Role.PLATFORM_OPERATOR},
    "create_payment_method_session": {Role.OWNER, Role.BILLING_ADMIN, Role.SUPPORT,
                                      Role.DEVELOPER, Role.PLATFORM_OPERATOR},

    # Dunning
    "manage_dunning_policies": {Role.OWNER, Role.BILLING_ADMIN},

    # Events / webhooks / API keys
    "view_event_logs": {Role.OWNER, Role.BILLING_ADMIN, Role.DEVELOPER, Role.FINANCE,
                       Role.SUPPORT, Role.PLATFORM_OPERATOR},
    "replay_webhooks": {Role.OWNER, Role.DEVELOPER, Role.PLATFORM_OPERATOR},
    "manage_webhook_endpoints": {Role.OWNER, Role.DEVELOPER},
    "manage_api_keys": {Role.OWNER, Role.DEVELOPER},

    # Team / org
    "manage_team_roles": {Role.OWNER},
    "export_workspace_data": {Role.OWNER},
    "force_workspace_signout": {Role.OWNER},
    "transfer_workspace_ownership": {Role.OWNER},
    "close_workspace": {Role.OWNER},

    # Audit logs
    "view_audit_logs": {Role.OWNER, Role.BILLING_ADMIN, Role.DEVELOPER, Role.FINANCE,
                       Role.SUPPORT, Role.PLATFORM_OPERATOR},
}
# fmt: on


def has_capability(role: str | None, capability: str) -> bool:
    """Return True if ``role`` is permitted to perform ``capability``."""
    if role is None:
        return False
    allowed = CAPABILITIES.get(capability)
    if allowed is None:
        # Fail closed: unknown capability -> deny.
        return False
    return role in allowed


def list_capabilities(role: str) -> list[str]:
    """Return all capability names available to ``role``. Ordered for stability."""
    return sorted(name for name, allowed in CAPABILITIES.items() if role in allowed)
