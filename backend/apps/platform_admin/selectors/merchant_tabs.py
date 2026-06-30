"""Per-merchant per-tab list selectors (S13).

Each function below scopes a top-level admin list endpoint to a single
merchant id and returns ``(rows, total)`` ready for FE pagination.

The row projections deliberately mirror the existing seed shapes the FE
already knows about — see :file:`apps/subpilot-admin/src/data/seed.ts`.
"""
from __future__ import annotations

from typing import Any

from django.db.models import Count, Q

from apps.accounts.models import Merchant
from apps.analytics.selectors import _normalise_to_monthly_minor  # noqa: PLC2701
from apps.audit.models import AuditLog
from apps.subscriptions.models import (
    Subscription,
    SubscriptionItem,
)

from ..services.formatting import format_compact_money
from .merchants import _plan_bucket
from .payments import list_payments_cross_tenant, project_payment
from .webhooks import list_deliveries_cross_tenant, project_delivery


# --- Resolver --------------------------------------------------------------


def _resolve(merchant_id: str) -> Merchant | None:
    try:
        return Merchant.objects.get(pk=merchant_id)
    except (Merchant.DoesNotExist, ValueError):
        return None


def _bound_page(page: int, page_size: int) -> tuple[int, int, int]:
    """Clamp ``page``/``page_size`` and return ``(page, size, offset)``."""
    page = max(1, int(page or 1))
    size = max(1, min(100, int(page_size or 25)))
    return page, size, (page - 1) * size


# --- Subscriptions ---------------------------------------------------------


_SUB_STATUS_LABEL = {
    Subscription.Status.ACTIVE: "Active",
    Subscription.Status.TRIALING: "Trialing",
    Subscription.Status.PAUSED: "Paused",
    Subscription.Status.PAST_DUE: "Past due",
    Subscription.Status.CANCELED: "Canceled",
    Subscription.Status.EXPIRED: "Expired",
    Subscription.Status.INCOMPLETE: "Incomplete",
}


def _subscription_mrr_minor(sub: Subscription) -> tuple[int, str]:
    items = sub.items.select_related("price_version").filter(
        status=SubscriptionItem.Status.ACTIVE
    )
    total_minor = 0
    currency = ""
    for it in items:
        pv = it.price_version
        if pv is None:
            continue
        line = pv.amount_minor * max(1, int(it.quantity or 1))
        total_minor += _normalise_to_monthly_minor(line, pv.interval_unit, pv.interval_count)
        if pv.currency:
            currency = pv.currency
    return total_minor, currency or "NGN"


def list_merchant_subscriptions(
    *,
    merchant_id: str,
    page: int = 1,
    page_size: int = 25,
    status: str | None = None,
) -> dict[str, Any] | None:
    """Subscriptions tab payload — subs page + stats + plan-mix shares.

    Returns ``None`` if the merchant doesn't exist (view maps to 404).
    """
    merchant = _resolve(merchant_id)
    if merchant is None:
        return None

    page, size, offset = _bound_page(page, page_size)
    currency = merchant.default_currency or "NGN"

    qs = (
        Subscription.objects.filter(merchant=merchant)
        .select_related("customer", "plan")
        .order_by("-created_at")
    )

    fe_status = (status or "").strip().lower()
    if fe_status and fe_status not in {"all", ""}:
        normalised = fe_status.replace(" ", "_").replace("-", "_")
        qs = qs.filter(status=normalised)

    total = qs.count()

    rows: list[dict[str, Any]] = []
    for sub in qs[offset : offset + size]:
        mrr_minor, sub_currency = _subscription_mrr_minor(sub)
        rows.append(
            {
                "id": f"sub_{str(sub.id)[:8]}",
                "rawId": str(sub.id),
                "customer": (
                    getattr(sub.customer, "name", "")
                    or getattr(sub.customer, "email", "")
                    or "—"
                ),
                "plan": sub.plan.name if sub.plan else "Default plan",
                "planBucket": _plan_bucket(sub.plan.name if sub.plan else ""),
                "status": _SUB_STATUS_LABEL.get(sub.status, sub.status.title()),
                "rawStatus": sub.status,
                "mrr": format_compact_money(mrr_minor, sub_currency or currency),
                "mrrMinor": mrr_minor,
                "currentPeriodEnd": (
                    sub.current_period_end.isoformat() if sub.current_period_end else None
                ),
                "createdAt": sub.created_at.isoformat() if sub.created_at else "",
            }
        )

    # --- Aggregate stats (always over the full per-merchant set, not the page).
    counts = (
        Subscription.objects.filter(merchant=merchant)
        .aggregate(
            active=Count("id", filter=Q(status=Subscription.Status.ACTIVE)),
            trialing=Count("id", filter=Q(status=Subscription.Status.TRIALING)),
            paused=Count("id", filter=Q(status=Subscription.Status.PAUSED)),
            past_due=Count("id", filter=Q(status=Subscription.Status.PAST_DUE)),
            canceled=Count("id", filter=Q(status=Subscription.Status.CANCELED)),
        )
    )

    active_count = int(counts["active"] or 0)

    # Plan mix (live, by active subs).
    plan_mix_rows = list(
        Subscription.objects.filter(merchant=merchant, status=Subscription.Status.ACTIVE)
        .select_related("plan")
        .values("plan__name")
        .annotate(n=Count("id"))
        .order_by("-n")
    )
    plan_mix: list[dict[str, Any]] = []
    if active_count > 0:
        for row in plan_mix_rows:
            name = row.get("plan__name") or "Default plan"
            count = int(row.get("n") or 0)
            plan_mix.append(
                {
                    "plan": name,
                    "bucket": _plan_bucket(name),
                    "count": count,
                    "sharePct": round(100.0 * count / active_count, 1),
                }
            )

    # MRR + ARPU.
    items = SubscriptionItem.objects.filter(
        subscription__merchant=merchant,
        subscription__status__in=[
            Subscription.Status.ACTIVE,
            Subscription.Status.TRIALING,
            Subscription.Status.PAST_DUE,
        ],
        status=SubscriptionItem.Status.ACTIVE,
    ).select_related("price_version")
    mrr_minor_total = 0
    for it in items:
        pv = it.price_version
        if pv is None:
            continue
        line = pv.amount_minor * max(1, int(it.quantity or 1))
        mrr_minor_total += _normalise_to_monthly_minor(line, pv.interval_unit, pv.interval_count)
        if pv.currency:
            currency = pv.currency
    arpu_minor = int(round(mrr_minor_total / active_count)) if active_count else 0

    top_plan = plan_mix[0]["plan"] if plan_mix else "Default plan"

    return {
        "rows": rows,
        "total": total,
        "page": page,
        "pageSize": size,
        "stats": {
            "active": active_count,
            "trialing": int(counts["trialing"] or 0),
            "paused": int(counts["paused"] or 0),
            "pastDue": int(counts["past_due"] or 0),
            "canceledMtd": int(counts["canceled"] or 0),
            "topPlan": top_plan,
            "arpu": format_compact_money(arpu_minor, currency),
            "arpuMinor": arpu_minor,
            "mrr": format_compact_money(mrr_minor_total, currency),
            "mrrMinor": mrr_minor_total,
            "currency": (currency or "NGN").upper(),
        },
        "planMix": plan_mix,
    }


# --- Payments --------------------------------------------------------------


def list_merchant_payments(
    *,
    merchant_id: str,
    page: int = 1,
    page_size: int = 25,
    status: str | None = None,
) -> dict[str, Any] | None:
    """Thin wrapper around the cross-tenant payments selector, merchant-scoped."""
    merchant = _resolve(merchant_id)
    if merchant is None:
        return None

    page, size, offset = _bound_page(page, page_size)
    rows, total = list_payments_cross_tenant(
        status=status or None,
        merchant_id=str(merchant.id),
        limit=size,
        offset=offset,
    )
    return {
        "rows": [project_payment(r) for r in rows],
        "total": total,
        "page": page,
        "pageSize": size,
    }


# --- Webhooks --------------------------------------------------------------


def list_merchant_webhooks(
    *,
    merchant_id: str,
    page: int = 1,
    page_size: int = 25,
    status: str | None = None,
    event_type: str | None = None,
) -> dict[str, Any] | None:
    """Thin wrapper around the cross-tenant deliveries selector, merchant-scoped."""
    merchant = _resolve(merchant_id)
    if merchant is None:
        return None

    page, size, offset = _bound_page(page, page_size)
    rows, total = list_deliveries_cross_tenant(
        status=status or None,
        merchant_id=str(merchant.id),
        event_type=event_type or None,
        limit=size,
        offset=offset,
    )
    return {
        "rows": [project_delivery(r) for r in rows],
        "total": total,
        "page": page,
        "pageSize": size,
    }


# --- Audit -----------------------------------------------------------------


def list_merchant_audit(
    *,
    merchant_id: str,
    page: int = 1,
    page_size: int = 25,
    action: str | None = None,
) -> dict[str, Any] | None:
    """Paginated per-merchant audit log."""
    merchant = _resolve(merchant_id)
    if merchant is None:
        return None

    page, size, offset = _bound_page(page, page_size)
    qs = AuditLog.objects.filter(merchant=merchant).order_by("-occurred_at")
    if action:
        needle = str(action).strip()
        if needle:
            qs = qs.filter(action__icontains=needle)

    total = qs.count()
    rows: list[dict[str, Any]] = []
    for log in qs[offset : offset + size]:
        rows.append(
            {
                "id": f"audit_{str(log.id)[:8]}",
                "rawId": str(log.id),
                "action": log.action,
                "detail": (log.metadata or {}).get("note", "") or log.target_id,
                "actor": log.actor_label or log.actor_role or "system",
                "actorRole": log.actor_role,
                "targetType": log.target_type,
                "targetId": log.target_id,
                "occurredAt": log.occurred_at.isoformat() if log.occurred_at else "",
                "metadata": log.metadata or {},
            }
        )

    return {
        "rows": rows,
        "total": total,
        "page": page,
        "pageSize": size,
    }


__all__ = [
    "list_merchant_subscriptions",
    "list_merchant_payments",
    "list_merchant_webhooks",
    "list_merchant_audit",
]
