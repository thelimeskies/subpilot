"""Cross-tenant audit log selector for the platform admin console.

The Audit tab on the SubPilot platform Settings page renders entries
from :class:`apps.audit.AuditLog` regardless of merchant. The row
projection mirrors the FE-shape ``AuditEntry`` defined in
``apps/subpilot-admin/src/data/seed.ts`` so the page can drop the seed
import and consume the backend payload directly.
"""
from __future__ import annotations

from typing import Any

from django.db.models import Q

from apps.audit.models import AuditLog


def _bound_page(page: int, page_size: int) -> tuple[int, int, int]:
    page = max(1, int(page or 1))
    size = max(1, min(200, int(page_size or 50)))
    return page, size, (page - 1) * size


def _category_for(action: str, target_type: str) -> str:
    """Map a backend action string to the FE timeline category.

    The FE renders four bins on the Audit tab:
    ``merchant``, ``platform``, ``team``, ``security``. We pick a bin
    based on the action prefix so the UI gets the right pill colour.
    """
    a = (action or "").lower()
    t = (target_type or "").lower()
    if a.startswith(("auth.", "mfa.", "password.")) or "session" in a:
        return "security"
    if a.startswith(("team_member.", "platform_admin.", "team.")) or t in {
        "platform_admin",
        "team_member",
    }:
        return "team"
    if (
        a.startswith(("merchant.", "kyc.", "merchant_config.", "subscription.", "invoice.", "payment."))
        or t in {"merchant", "subscription", "invoice", "payment", "kyc_review"}
    ):
        return "merchant"
    return "platform"


def _detail_for(log: AuditLog) -> str:
    """Best-effort human-friendly detail line.

    Tries the ``note`` and ``message`` keys in metadata first. Falls
    back to a compact summary built from target + changed fields.
    """
    meta = log.metadata or {}
    for key in ("note", "message", "summary", "detail"):
        val = meta.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()

    bits: list[str] = []
    if log.target_type and log.target_id:
        bits.append(f"{log.target_type}:{log.target_id}")
    elif log.target_id:
        bits.append(log.target_id)

    fields = meta.get("fields")
    if isinstance(fields, list) and fields:
        bits.append("changed: " + ", ".join(str(f) for f in fields[:6]))

    return " · ".join(bits) if bits else log.action


def project_audit_log(log: AuditLog) -> dict[str, Any]:
    """FE-shape ``AuditEntry`` row."""
    return {
        "id": f"aud_{str(log.id)[:8]}",
        "rawId": str(log.id),
        "merchantId": str(log.merchant_id) if log.merchant_id else None,
        "actor": log.actor_label or log.actor_role or "system",
        "actorRole": log.actor_role,
        "action": log.action,
        "detail": _detail_for(log),
        "targetType": log.target_type,
        "targetId": log.target_id,
        "category": _category_for(log.action, log.target_type),
        "occurredAt": log.occurred_at.isoformat() if log.occurred_at else "",
        "metadata": log.metadata or {},
    }


def list_platform_audit(
    *,
    page: int = 1,
    page_size: int = 50,
    category: str | None = None,
    search: str | None = None,
) -> dict[str, Any]:
    """Cross-tenant paginated audit log."""
    page, size, offset = _bound_page(page, page_size)
    qs = AuditLog.objects.all().order_by("-occurred_at")

    if search:
        needle = str(search).strip()
        if needle:
            qs = qs.filter(
                Q(action__icontains=needle)
                | Q(actor_label__icontains=needle)
                | Q(target_id__icontains=needle)
            )

    bucket = (category or "").strip().lower()
    if bucket == "security":
        qs = qs.filter(
            Q(action__istartswith="auth.")
            | Q(action__istartswith="mfa.")
            | Q(action__istartswith="password.")
            | Q(action__icontains="session")
        )
    elif bucket == "team":
        qs = qs.filter(
            Q(action__istartswith="team_member.")
            | Q(action__istartswith="platform_admin.")
            | Q(action__istartswith="team.")
            | Q(target_type__in=["platform_admin", "team_member"])
        )
    elif bucket == "merchant":
        qs = qs.filter(
            Q(action__istartswith="merchant.")
            | Q(action__istartswith="kyc.")
            | Q(action__istartswith="merchant_config.")
            | Q(action__istartswith="subscription.")
            | Q(action__istartswith="invoice.")
            | Q(action__istartswith="payment.")
            | Q(target_type__in=["merchant", "subscription", "invoice", "payment", "kyc_review"])
        )
    elif bucket == "platform":
        qs = qs.filter(
            Q(action__istartswith="platform.")
            | Q(action__istartswith="adapter.")
            | Q(action__istartswith="webhook.")
            | Q(target_type__in=["platform_setting", "adapter"])
        )

    total = qs.count()
    rows = [project_audit_log(log) for log in qs[offset : offset + size]]
    return {
        "rows": rows,
        "total": total,
        "page": page,
        "pageSize": size,
    }


__all__ = [
    "list_platform_audit",
    "project_audit_log",
]
