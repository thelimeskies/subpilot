"""Cross-tenant Merchant detail selector for the platform admin (S4).

Returns the FE-shape detail payload consumed by
[MerchantDetailPage.tsx](file:///Users/mac/Desktop/Projects/HackathonxNomba/apps/subpilot-admin/src/pages/MerchantDetailPage.tsx).

The payload extends the row from
[selectors/merchants.py](file:///Users/mac/Desktop/Projects/HackathonxNomba/backend/apps/platform_admin/selectors/merchants.py)
with nested objects for subscriptions stats, recent payments, recent
audit-log entries, configured environments, KYC tier, and platform
notes. Fields not yet wired (config/feature-flags) are left for S10.
"""
from __future__ import annotations

from datetime import timedelta
from typing import Any

from django.db.models import Count, Q, Sum
from django.utils import timezone

from apps.accounts.models import Environment, Merchant, Role, TeamMember
from apps.audit.models import AuditLog
from apps.invoices.models import Invoice
from apps.payments.models import PaymentAttempt
from apps.subscriptions.models import Subscription, SubscriptionItem

from ..models import KycReview, PlatformMerchantNote
from ..services.formatting import format_compact_money, format_pct
from ..services.kyc_metadata import sync_merchant_kyc_review_from_metadata
from .merchants import (
    _derive_region,
    _derive_status,
    _normalise_to_monthly_minor,
    _plan_bucket,
)


def _short_id(value: str, prefix: str) -> str:
    """Mimic FE seed style ids — short stable token per real UUID."""
    return f"{prefix}_{str(value)[:8]}"


def _kyc_status_label(value: str) -> str:
    return {
        "verified": "Verified",
        "in_review": "In review",
        "rejected": "Rejected",
        "action_needed": "Action needed",
    }.get(value, "Not submitted")


def _kyc_level_label(value: str) -> str:
    return {"tier_1": "Tier 1", "tier_2": "Tier 2", "tier_3": "Tier 3"}.get(value, "Tier 1")


def _payment_status_label(s: str) -> str:
    return {
        PaymentAttempt.Status.SUCCEEDED: "Captured",
        PaymentAttempt.Status.FAILED: "Failed",
        PaymentAttempt.Status.PENDING: "Pending",
        PaymentAttempt.Status.ABANDONED: "Failed",
    }.get(s, s.title())


def get_merchant_detail(merchant_id: str) -> dict[str, Any] | None:
    """Return the FE-shape detail payload for ``merchant_id``.

    Returns ``None`` when the merchant does not exist (caller maps to 404).
    """
    try:
        m = Merchant.objects.get(pk=merchant_id)
    except Merchant.DoesNotExist:
        return None

    mid = str(m.id)

    # ------------- Owner -----------------------------------------------------
    owner_tm = (
        TeamMember.objects.filter(merchant=m, role=Role.OWNER, status=TeamMember.Status.ACTIVE)
        .select_related("user")
        .order_by("-created_at")
        .first()
    )
    owner_name = (
        (owner_tm.user.display_name or owner_tm.user.email or "Owner") if owner_tm else "—"
    )
    owner_email = (owner_tm.user.email if owner_tm and owner_tm.user.email else "")

    # ------------- Environments ----------------------------------------------
    envs = list(Environment.objects.filter(merchant=m).order_by("mode"))
    env_label = "Test"
    if any(e.mode == Environment.Mode.LIVE for e in envs):
        env_label = "Live"

    # ------------- Subscriptions stats --------------------------------------
    sub_counts = (
        Subscription.objects.filter(merchant=m)
        .aggregate(
            active=Count("id", filter=Q(status=Subscription.Status.ACTIVE)),
            trialing=Count("id", filter=Q(status=Subscription.Status.TRIALING)),
            paused=Count("id", filter=Q(status=Subscription.Status.PAUSED)),
            past_due=Count("id", filter=Q(status=Subscription.Status.PAST_DUE)),
            canceled=Count("id", filter=Q(status=Subscription.Status.CANCELED)),
        )
    )
    active_count = int(sub_counts["active"] or 0)

    # Top plan via most-popular plan among active subs.
    top_plan_row = (
        Subscription.objects.filter(merchant=m, status=Subscription.Status.ACTIVE)
        .select_related("plan")
        .values("plan__name")
        .annotate(n=Count("id"))
        .order_by("-n")
        .first()
    )
    top_plan_name = (
        top_plan_row["plan__name"] if top_plan_row and top_plan_row["plan__name"] else "Default plan"
    )
    plan_bucket = _plan_bucket(top_plan_name)

    # MRR -- per-merchant Python aggregation (same approach as list selector).
    mrr_minor = 0
    currency = m.default_currency or "NGN"
    items = (
        SubscriptionItem.objects.filter(
            subscription__merchant=m,
            subscription__status__in=[
                Subscription.Status.ACTIVE,
                Subscription.Status.TRIALING,
                Subscription.Status.PAST_DUE,
            ],
            status=SubscriptionItem.Status.ACTIVE,
        )
        .select_related("price_version")
    )
    for item in items:
        pv = item.price_version
        if pv is None:
            continue
        line = pv.amount_minor * max(1, int(item.quantity or 1))
        mrr_minor += _normalise_to_monthly_minor(line, pv.interval_unit, pv.interval_count)
        if pv.currency:
            currency = pv.currency

    # ARPU.
    arpu_minor = int(round(mrr_minor / active_count)) if active_count else 0

    # Churn (MTD).
    month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    canceled_mtd = Subscription.objects.filter(
        merchant=m,
        status=Subscription.Status.CANCELED,
        updated_at__gte=month_start,
    ).count()
    starting_subs = max(1, active_count + canceled_mtd)
    churn_pct = round(100.0 * canceled_mtd / starting_subs, 1)

    # ------------- Volume + recovery ----------------------------------------
    cutoff = timezone.now() - timedelta(days=30)
    volume_minor = int(
        PaymentAttempt.objects.filter(
            merchant=m, status=PaymentAttempt.Status.SUCCEEDED, created_at__gte=cutoff
        ).aggregate(total=Sum("amount_minor"))["total"]
        or 0
    )

    # Failed-invoices = open invoices currently tied to an active dunning run.
    from apps.dunning.models import DunningRun

    failed_invoices = (
        Invoice.objects.filter(
            merchant=m, status=Invoice.Status.OPEN, dunning_runs__status=DunningRun.Status.ACTIVE
        )
        .distinct()
        .count()
    )

    runs_agg = DunningRun.objects.filter(merchant=m, updated_at__gte=cutoff).aggregate(
        recovered=Count("id", filter=Q(status=DunningRun.Status.RECOVERED)),
        terminated=Count(
            "id",
            filter=Q(
                status__in=[
                    DunningRun.Status.RECOVERED,
                    DunningRun.Status.EXHAUSTED,
                    DunningRun.Status.CANCELED,
                ]
            ),
        ),
    )
    terminated = int(runs_agg["terminated"] or 0)
    recovery_pct = (
        round(100.0 * int(runs_agg["recovered"] or 0) / terminated, 2) if terminated else 0.0
    )

    derived_status = _derive_status(m.status, failed_invoices)

    # ------------- Recent payments (top 5 for Overview card; full list lives at
    # GET /platform/merchants/<id>/payments — see views.merchant_tabs S13) --
    recent_payments = []
    for pa in (
        PaymentAttempt.objects.filter(merchant=m)
        .select_related("invoice", "invoice__customer")
        .order_by("-created_at")[:5]
    ):
        cust = getattr(pa.invoice, "customer", None) if pa.invoice_id else None
        cust_name = ""
        if cust is not None:
            cust_name = getattr(cust, "name", "") or getattr(cust, "email", "") or ""
        recent_payments.append(
            {
                "id": _short_id(pa.id, "pay"),
                "amount": format_compact_money(int(pa.amount_minor or 0), pa.currency or "NGN"),
                "status": _payment_status_label(pa.status),
                "method": "Card",  # PaymentMethod.kind not enriched here; keep simple for S4.
                "customer": cust_name or "—",
                "occurredAt": pa.created_at.isoformat() if pa.created_at else "",
                "raw": {"amountMinor": int(pa.amount_minor or 0), "currency": pa.currency or "NGN"},
            }
        )

    # ------------- Recent audit (top 5 for Overview card; full list lives at
    # GET /platform/merchants/<id>/audit — see views.merchant_tabs S13) ------
    recent_audit = []
    for log in AuditLog.objects.filter(merchant=m).order_by("-occurred_at")[:5]:
        recent_audit.append(
            {
                "id": _short_id(log.id, "audit"),
                "action": log.action,
                "detail": (log.metadata or {}).get("note", "") or log.target_id,
                "actor": log.actor_label or log.actor_role or "system",
                "actorRole": log.actor_role,
                "occurredAt": log.occurred_at.isoformat() if log.occurred_at else "",
            }
        )

    # ------------- KYC review ------------------------------------------------
    kyc_obj = KycReview.objects.filter(merchant=m).select_related("reviewer").first()
    if kyc_obj is None:
        kyc_obj = sync_merchant_kyc_review_from_metadata(m)
    if kyc_obj is not None:
        kyc = {
            "status": _kyc_status_label(kyc_obj.status),
            "level": _kyc_level_label(kyc_obj.level),
            "documents": kyc_obj.documents or [],
            "flags": kyc_obj.flags or [],
            "notes": kyc_obj.notes or "",
            "reviewer": (
                (kyc_obj.reviewer.display_name or kyc_obj.reviewer.email)
                if kyc_obj.reviewer
                else ""
            ),
            "submittedAt": kyc_obj.submitted_at.isoformat() if kyc_obj.submitted_at else "",
            "reviewedAt": kyc_obj.reviewed_at.isoformat() if kyc_obj.reviewed_at else "",
        }
    else:
        kyc = None

    # ------------- Platform notes -------------------------------------------
    notes = []
    for n in (
        PlatformMerchantNote.objects.filter(merchant=m)
        .select_related("author")
        .order_by("-created_at")[:25]
    ):
        notes.append(
            {
                "id": _short_id(n.id, "note"),
                "body": n.body,
                "author": (n.author.display_name or n.author.email) if n.author else "system",
                "createdAt": n.created_at.isoformat() if n.created_at else "",
            }
        )

    return {
        # Row-level fields (matches FE Merchant interface).
        "id": mid,
        "name": m.name,
        "slug": m.slug,
        "owner": owner_name,
        "ownerEmail": owner_email,
        "plan": plan_bucket,
        "mrr": format_compact_money(mrr_minor, currency),
        "status": derived_status,
        "rawStatus": m.status,
        "failedInvoices": failed_invoices,
        "recoveryRate": format_pct(recovery_pct),
        "environment": env_label,
        "createdAt": m.created_at.isoformat() if m.created_at else "",
        "region": _derive_region(m.industry),
        "monthlyVolume": format_compact_money(volume_minor, currency),
        "activeSubscriptions": active_count,
        # Detail extras.
        "subscriptionStats": {
            "active": active_count,
            "trialing": int(sub_counts["trialing"] or 0),
            "paused": int(sub_counts["paused"] or 0),
            "pastDue": int(sub_counts["past_due"] or 0),
            "canceledMtd": canceled_mtd,
            "churnRate": f"{churn_pct}%",
            "topPlan": top_plan_name,
            "arpu": format_compact_money(arpu_minor, currency),
        },
        "environments": [
            {"id": str(e.id), "mode": e.mode, "label": "Live" if e.mode == "live" else "Test"}
            for e in envs
        ],
        "recentPayments": recent_payments,
        "recentAudit": recent_audit,
        "kyc": kyc,
        "notes": notes,
        "raw": {
            "mrrMinor": mrr_minor,
            "monthlyVolumeMinor": volume_minor,
            "recoveryRatePct": recovery_pct,
            "currency": currency,
            "arpuMinor": arpu_minor,
        },
    }
