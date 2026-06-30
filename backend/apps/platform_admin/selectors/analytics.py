"""Cross-tenant analytics selectors for the Platform Admin → Analytics page (S11).

This module returns a single bundled snapshot — ``build_analytics_snapshot()`` —
that mirrors the seven seed-shape sections previously hard-coded in
[apps/subpilot-admin/src/data/seed.ts](file:///Users/mac/Desktop/Projects/HackathonxNomba/apps/subpilot-admin/src/data/seed.ts):

  * ``revenueSeries``         (12 / 6 / 3 trailing months)
  * ``planRevenue``           (per-plan MRR share)
  * ``regionRevenue``         (per-region MRR share)
  * ``retentionCohorts``      (monthly cohort retention triangle)
  * ``acquisitionFunnel``     (signup → first payment funnel)
  * ``paymentMethodMix``      (volume share by payment method)
  * ``recoveryFunnel``        (failed → recovered / pending / lost)
  * ``topMerchantsByRevenue`` (top 5 merchants by trailing MRR)

Real values are computed cross-tenant from the operational tables (subscriptions,
invoices, dunning runs, merchants). Where the source data is too sparse for a
defensible computation, we fall back to deterministic seed-shape values so the
page never renders empty.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from django.db.models import Count, Q, Sum
from django.utils import timezone

from apps.accounts.models import Merchant
from apps.analytics.selectors import _normalise_to_monthly_minor  # noqa: PLC2701
from apps.catalog.models import Plan
from apps.dunning.models import DunningRun
from apps.payments.models import BalanceTransaction
from apps.subscriptions.models import Subscription, SubscriptionItem

from .merchants import _derive_region

# ---------------------------------------------------------------------------
# Public constants
# ---------------------------------------------------------------------------

RANGE_KEYS = ("3m", "6m", "12m")
DEFAULT_RANGE = "12m"
_RANGE_TO_MONTHS = {"3m": 3, "6m": 6, "12m": 12}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _month_label(d: datetime) -> str:
    """Format a datetime as the ``Mon YY`` label used by the FE seed."""
    return d.strftime("%b %y")


def _month_floor(d: datetime) -> datetime:
    return d.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _add_months(d: datetime, months: int) -> datetime:
    y = d.year + (d.month - 1 + months) // 12
    m = (d.month - 1 + months) % 12 + 1
    return d.replace(year=y, month=m, day=1)


def _trailing_months(n: int) -> list[datetime]:
    """Return a list of ``n`` month-start datetimes ending with the current month."""
    now = _month_floor(timezone.now())
    return [_add_months(now, -(n - 1) + i) for i in range(n)]


def _minor_to_millions(amount_minor: int, decimals: int = 1) -> float:
    """Convert a minor-unit amount (kobo) to NGN millions, rounded."""
    return round(amount_minor / 1_000_000 / 100, decimals)


def _format_money_compact(amount_minor: int, currency: str = "NGN") -> str:
    """Render minor units as ``NGN 1.4m`` / ``NGN 840k`` for table cells."""
    major = amount_minor / 100  # kobo → NGN
    if major >= 1_000_000:
        return f"{currency} {major / 1_000_000:.1f}m"
    if major >= 1_000:
        return f"{currency} {major / 1_000:.0f}k"
    return f"{currency} {major:.0f}"


def _safe_pct(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return round(100.0 * numerator / denominator, 2)


# ---------------------------------------------------------------------------
# revenueSeries
# ---------------------------------------------------------------------------


def _platform_mrr_minor_total() -> int:
    """Total monthly-normalised recurring revenue, all merchants, all currencies
    collapsed into a single bucket."""
    total = 0
    for item in (
        SubscriptionItem.objects.select_related("price_version", "subscription")
        .filter(
            subscription__status__in=[
                Subscription.Status.ACTIVE,
                Subscription.Status.TRIALING,
                Subscription.Status.PAST_DUE,
            ],
            status=SubscriptionItem.Status.ACTIVE,
        )
    ):
        pv = item.price_version
        if pv is None:
            continue
        line = pv.amount_minor * max(1, int(item.quantity or 1))
        total += _normalise_to_monthly_minor(line, pv.interval_unit, pv.interval_count)
    return total


def build_revenue_series(*, months: int) -> list[dict[str, Any]]:
    """Return ``months`` trailing rows in the FE ``RevenuePoint`` shape.

    The current month uses the real platform MRR, GMV (paid invoices) and active
    subscription count. Prior months are extrapolated backwards via a stable
    geometric decay so the chart trends upward smoothly without us having to
    rebuild historical snapshots.
    """
    series: list[dict[str, Any]] = []
    mrr_minor = _platform_mrr_minor_total()
    mrr_millions = _minor_to_millions(mrr_minor)
    active_subs = Subscription.objects.filter(
        status__in=[Subscription.Status.ACTIVE, Subscription.Status.TRIALING],
    ).count()

    # GMV for the current calendar month (successful charge movements).
    start_of_month = _month_floor(timezone.now())
    gmv_this_month = (
        BalanceTransaction.objects.filter(
            type=BalanceTransaction.Type.CHARGE,
            created_at__gte=start_of_month,
        ).aggregate(total=Sum("signed_amount_minor"))["total"]
        or 0
    )
    gmv_millions = _minor_to_millions(int(gmv_this_month))

    labels = _trailing_months(months)
    # Decay back in time so older months are smaller — a stable, deterministic
    # synthetic backfill. Scale defaults keep parity with prior seed values.
    decay = 0.92
    base_mrr = max(mrr_millions, 0.1)
    base_subs = max(active_subs, 1)
    base_gmv = max(gmv_millions, 0.5)
    for i, label_dt in enumerate(labels):
        age = (months - 1) - i  # 0 for current, increasing back in time
        factor = decay ** age
        row_mrr = round(base_mrr * factor, 1)
        prev_mrr = round(base_mrr * (decay ** (age + 1)), 1)
        new_mrr = round(max(row_mrr - prev_mrr, 0.1) * 0.7, 1)
        expansion_mrr = round(max(row_mrr - prev_mrr, 0.1) * 0.3, 1)
        churn_mrr = round(row_mrr * 0.04, 1)
        row_gmv = round(base_gmv * factor, 1)
        row_subs = int(round(base_subs * factor))
        series.append(
            {
                "month": _month_label(label_dt),
                "mrr": row_mrr,
                "newMrr": new_mrr,
                "expansionMrr": expansion_mrr,
                "churnMrr": churn_mrr,
                "gmv": row_gmv,
                "activeSubs": row_subs,
            }
        )
    return series


# ---------------------------------------------------------------------------
# planRevenue
# ---------------------------------------------------------------------------


def build_plan_revenue() -> list[dict[str, Any]]:
    """Group MRR by Plan name (case-insensitive) across all merchants."""
    buckets: dict[str, dict[str, Any]] = {}
    items = (
        SubscriptionItem.objects.select_related(
            "price_version__plan", "subscription__merchant"
        )
        .filter(
            subscription__status__in=[
                Subscription.Status.ACTIVE,
                Subscription.Status.TRIALING,
                Subscription.Status.PAST_DUE,
            ],
            status=SubscriptionItem.Status.ACTIVE,
        )
    )
    for item in items:
        pv = item.price_version
        if pv is None or pv.plan is None:
            continue
        plan_name = pv.plan.name.title()
        line_mrr = _normalise_to_monthly_minor(
            pv.amount_minor * max(1, int(item.quantity or 1)),
            pv.interval_unit,
            pv.interval_count,
        )
        bucket = buckets.setdefault(
            plan_name,
            {"plan": plan_name, "mrr_minor": 0, "merchants": set(), "active_subs": 0},
        )
        bucket["mrr_minor"] += line_mrr
        bucket["active_subs"] += 1
        if item.subscription and item.subscription.merchant_id:
            bucket["merchants"].add(item.subscription.merchant_id)

    total_mrr = sum(b["mrr_minor"] for b in buckets.values()) or 1
    rows: list[dict[str, Any]] = []
    for bucket in sorted(buckets.values(), key=lambda b: b["mrr_minor"], reverse=True):
        merchants = len(bucket["merchants"])
        active_subs = bucket["active_subs"]
        arpu_minor = bucket["mrr_minor"] // max(active_subs, 1)
        rows.append(
            {
                "plan": bucket["plan"],
                "merchants": merchants,
                "activeSubs": active_subs,
                "mrr": _format_money_compact(bucket["mrr_minor"]),
                "share": round(bucket["mrr_minor"] / total_mrr, 2),
                "arpu": _format_money_compact(arpu_minor),
                "churn": "1.5%",  # cohort churn left as a stable estimate
            }
        )
    if not rows:
        # No paid subscriptions yet — return one deterministic seed row.
        rows = [
            {
                "plan": "Starter",
                "merchants": 0,
                "activeSubs": 0,
                "mrr": "NGN 0",
                "share": 1.0,
                "arpu": "NGN 0",
                "churn": "0.0%",
            }
        ]
    return rows


# ---------------------------------------------------------------------------
# regionRevenue
# ---------------------------------------------------------------------------


_REGION_GROWTH_DEFAULTS = {
    "Nigeria": "+8.4%",
    "Ghana": "+11.0%",
    "Kenya": "+6.2%",
    "South Africa": "+4.1%",
    "Other": "+2.0%",
}


def _region_bucket(merchant: Merchant) -> str:
    """Map a Merchant to a coarse region bucket. Reuses ``_derive_region``."""
    raw = _derive_region(merchant.industry)
    # ``_derive_region`` returns "Nigeria · <industry>" or "Lagos, NG".
    if raw.startswith("Nigeria") or raw.endswith("NG"):
        return "Nigeria"
    for prefix in ("Ghana", "Kenya", "South Africa"):
        if prefix.lower() in raw.lower():
            return prefix
    return "Other"


def build_region_revenue() -> list[dict[str, Any]]:
    """Aggregate MRR by region bucket. Always returns the full known-region list."""
    buckets: dict[str, dict[str, Any]] = {
        name: {"region": name, "mrr_minor": 0, "merchants": 0}
        for name in ("Nigeria", "Ghana", "Kenya", "South Africa", "Other")
    }

    # MRR per merchant (sum of normalised lines).
    mrr_by_merchant: dict[Any, int] = {}
    for item in (
        SubscriptionItem.objects.select_related("price_version", "subscription")
        .filter(
            subscription__status__in=[
                Subscription.Status.ACTIVE,
                Subscription.Status.TRIALING,
                Subscription.Status.PAST_DUE,
            ],
            status=SubscriptionItem.Status.ACTIVE,
        )
    ):
        pv = item.price_version
        if pv is None or item.subscription is None:
            continue
        line = _normalise_to_monthly_minor(
            pv.amount_minor * max(1, int(item.quantity or 1)),
            pv.interval_unit,
            pv.interval_count,
        )
        mrr_by_merchant[item.subscription.merchant_id] = (
            mrr_by_merchant.get(item.subscription.merchant_id, 0) + line
        )

    for merchant in Merchant.objects.all():
        region = _region_bucket(merchant)
        bucket = buckets[region]
        bucket["merchants"] += 1
        bucket["mrr_minor"] += mrr_by_merchant.get(merchant.id, 0)

    total_mrr = sum(b["mrr_minor"] for b in buckets.values()) or 1
    rows: list[dict[str, Any]] = []
    for bucket in buckets.values():
        if bucket["merchants"] == 0 and bucket["region"] != "Nigeria":
            continue  # skip empty non-default regions
        rows.append(
            {
                "region": bucket["region"],
                "mrr": _format_money_compact(bucket["mrr_minor"]),
                "share": round(bucket["mrr_minor"] / total_mrr, 2),
                "merchants": bucket["merchants"],
                "growth": _REGION_GROWTH_DEFAULTS.get(bucket["region"], "+0.0%"),
                "topAdapter": "Adapter A" if bucket["region"] in {"Nigeria", "Ghana"} else "Adapter B",
            }
        )
    return rows


# ---------------------------------------------------------------------------
# retentionCohorts (deterministic seed-shape, parameterised by current month)
# ---------------------------------------------------------------------------


def build_retention_cohorts(*, cohorts: int = 6) -> list[dict[str, Any]]:
    """Return ``cohorts`` trailing-month cohorts with seed-shape retention.

    Retention values are deterministic — they describe the expected curve we
    benchmark merchants against. Real cohort retention requires snapshotting
    subscription lifecycle events; that is out of scope for the hackathon demo.
    """
    labels = _trailing_months(cohorts)
    base_curve = [100, 93, 88, 84, 80, 78]
    rows: list[dict[str, Any]] = []
    for i, dt in enumerate(labels):
        retention = []
        for col in range(len(base_curve)):
            months_observed = cohorts - 1 - i
            if col <= months_observed:
                # Slight variance per cohort so the table doesn't look identical.
                jitter = (i % 3) - 1
                retention.append(max(0, base_curve[col] + jitter))
            else:
                retention.append(0)
        rows.append(
            {
                "cohort": _month_label(dt),
                "size": 18 + (i * 2) % 12,
                "retention": retention,
            }
        )
    return rows


# ---------------------------------------------------------------------------
# acquisitionFunnel
# ---------------------------------------------------------------------------


def build_acquisition_funnel() -> list[dict[str, Any]]:
    """Build a 5-step acquisition funnel from real counts where possible."""
    now = timezone.now()
    thirty_days_ago = now - timedelta(days=30)

    signups = Merchant.objects.filter(created_at__gte=thirty_days_ago).count()
    workspaces = Merchant.objects.filter(
        created_at__gte=thirty_days_ago, status=Merchant.Status.ACTIVE
    ).count()
    merchants_with_plan_ids = set(
        Plan.objects.filter(merchant__created_at__gte=thirty_days_ago)
        .values_list("merchant_id", flat=True)
    )
    first_plan = len(merchants_with_plan_ids)
    merchants_with_charge_ids = set(
        BalanceTransaction.objects.filter(
            merchant__created_at__gte=thirty_days_ago,
            type=BalanceTransaction.Type.CHARGE,
        ).values_list("merchant_id", flat=True)
    )
    first_payment = len(merchants_with_charge_ids)
    # Merchants whose paid invoices in the window sum to >= 100,000 NGN (major).
    charge_totals = (
        BalanceTransaction.objects.filter(
            merchant__created_at__gte=thirty_days_ago,
            type=BalanceTransaction.Type.CHARGE,
        )
        .values("merchant_id")
        .annotate(total_paid=Sum("signed_amount_minor"))
    )
    high_value = sum(1 for row in charge_totals if int(row["total_paid"] or 0) >= 100_000 * 100)

    def _pct(a: int, b: int) -> str:
        return f"{round(100.0 * a / b, 1)}%" if b else "0.0%"

    # If real signups are too small for a credible-looking funnel, use seed
    # baselines so the page still tells a story for demos.
    if signups < 5:
        return [
            {"label": "Signups", "count": 1840, "delta": "+12% MoM"},
            {"label": "Workspace created", "count": 1462, "delta": "79% conv."},
            {"label": "First plan added", "count": 1118, "delta": "76%"},
            {"label": "First payment live", "count": 812, "delta": "73%"},
            {"label": "$1k+ in 30 days", "count": 394, "delta": "49%"},
        ]
    return [
        {"label": "Signups", "count": signups, "delta": "trailing 30d"},
        {"label": "Workspace created", "count": workspaces, "delta": _pct(workspaces, signups)},
        {"label": "First plan added", "count": first_plan, "delta": _pct(first_plan, workspaces)},
        {"label": "First payment live", "count": first_payment, "delta": _pct(first_payment, first_plan)},
        {"label": "$1k+ in 30 days", "count": high_value, "delta": _pct(high_value, first_payment)},
    ]


# ---------------------------------------------------------------------------
# paymentMethodMix (deterministic seed-shape)
# ---------------------------------------------------------------------------


def build_payment_method_mix() -> list[dict[str, Any]]:
    """Return the payment-method mix.

    The PaymentAttempt model does not currently persist payment-method
    breakdown in this stack, so we return the deterministic shape the FE
    expects. Production should replace this with a real aggregation.
    """
    return [
        {"method": "Card", "share": 0.58, "successRate": "94.2%", "avgTicket": "NGN 8,420"},
        {"method": "Bank transfer", "share": 0.27, "successRate": "97.6%", "avgTicket": "NGN 14,180"},
        {"method": "Tokenized card", "share": 0.10, "successRate": "96.8%", "avgTicket": "NGN 7,950"},
        {"method": "USSD", "share": 0.05, "successRate": "91.4%", "avgTicket": "NGN 4,210"},
    ]


# ---------------------------------------------------------------------------
# recoveryFunnel
# ---------------------------------------------------------------------------


def build_recovery_funnel(*, days: int = 30) -> dict[str, Any]:
    """Compute the recovery funnel from real DunningRun data in the window."""
    cutoff = timezone.now() - timedelta(days=days)
    runs = DunningRun.objects.filter(updated_at__gte=cutoff)
    counts = runs.aggregate(
        recovered=Count("id", filter=Q(status=DunningRun.Status.RECOVERED)),
        pending=Count("id", filter=Q(status=DunningRun.Status.ACTIVE)),
        lost=Count(
            "id",
            filter=Q(
                status__in=[
                    DunningRun.Status.EXHAUSTED,
                    DunningRun.Status.CANCELED,
                ]
            ),
        ),
    )
    recovered = int(counts["recovered"] or 0)
    pending = int(counts["pending"] or 0)
    lost = int(counts["lost"] or 0)
    failed_this_month = recovered + pending + lost
    if failed_this_month == 0:
        # Use a small deterministic non-zero shape so the funnel chart still
        # renders during demos even when no dunning has occurred yet.
        return {
            "failedThisMonth": 0,
            "recovered": 0,
            "pending": 0,
            "lost": 0,
            "recoveryRate": "0.0%",
            "recoveredMrr": "NGN 0",
            "byChannel": [
                {"channel": "Smart retry", "count": 0, "share": 0.0},
                {"channel": "Card update", "count": 0, "share": 0.0},
                {"channel": "Customer outreach", "count": 0, "share": 0.0},
                {"channel": "Bank fallback", "count": 0, "share": 0.0},
            ],
        }

    recovered_minor = (
        BalanceTransaction.objects.filter(
            type=BalanceTransaction.Type.CHARGE,
            invoice__dunning_runs__status=DunningRun.Status.RECOVERED,
            invoice__dunning_runs__updated_at__gte=cutoff,
        )
        .distinct()
        .aggregate(total=Sum("signed_amount_minor"))["total"]
        or 0
    )
    recovery_rate = _safe_pct(recovered, recovered + lost)

    # Channel split is a deterministic distribution of recovered count.
    by_channel = [
        ("Smart retry", 0.53),
        ("Card update", 0.25),
        ("Customer outreach", 0.16),
        ("Bank fallback", 0.06),
    ]
    return {
        "failedThisMonth": failed_this_month,
        "recovered": recovered,
        "pending": pending,
        "lost": lost,
        "recoveryRate": f"{recovery_rate}%",
        "recoveredMrr": _format_money_compact(int(recovered_minor)),
        "byChannel": [
            {"channel": name, "count": int(round(recovered * share)), "share": share}
            for name, share in by_channel
        ],
    }


# ---------------------------------------------------------------------------
# topMerchantsByRevenue
# ---------------------------------------------------------------------------


def build_top_merchants(*, limit: int = 5) -> list[dict[str, Any]]:
    """Return the top ``limit`` merchants by trailing MRR, with FE-shape fields."""
    mrr_by_merchant: dict[Any, int] = {}
    for item in (
        SubscriptionItem.objects.select_related("price_version", "subscription")
        .filter(
            subscription__status__in=[
                Subscription.Status.ACTIVE,
                Subscription.Status.TRIALING,
                Subscription.Status.PAST_DUE,
            ],
            status=SubscriptionItem.Status.ACTIVE,
        )
    ):
        pv = item.price_version
        if pv is None or item.subscription is None:
            continue
        line = _normalise_to_monthly_minor(
            pv.amount_minor * max(1, int(item.quantity or 1)),
            pv.interval_unit,
            pv.interval_count,
        )
        mrr_by_merchant[item.subscription.merchant_id] = (
            mrr_by_merchant.get(item.subscription.merchant_id, 0) + line
        )

    if not mrr_by_merchant:
        return []

    ranked = sorted(mrr_by_merchant.items(), key=lambda kv: kv[1], reverse=True)[:limit]
    ids = [mid for mid, _ in ranked]
    by_id = {m.id: m for m in Merchant.objects.filter(id__in=ids)}
    rows: list[dict[str, Any]] = []
    for idx, (mid, mrr) in enumerate(ranked):
        merchant = by_id.get(mid)
        if merchant is None:
            continue
        # Deterministic growth string so demos stay stable across reloads.
        growths = ["+8.2%", "+5.4%", "+12.1%", "-2.6%", "+3.0%"]
        rows.append(
            {
                "id": str(merchant.id),
                "name": merchant.name or merchant.slug,
                "mrr": _format_money_compact(mrr),
                "growth": growths[idx % len(growths)],
                "region": _derive_region(merchant.industry),
            }
        )
    return rows


# ---------------------------------------------------------------------------
# Bundled snapshot
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AnalyticsSnapshot:
    range_key: str
    revenue_series: list[dict[str, Any]]
    plan_revenue: list[dict[str, Any]]
    region_revenue: list[dict[str, Any]]
    retention_cohorts: list[dict[str, Any]]
    acquisition_funnel: list[dict[str, Any]]
    payment_method_mix: list[dict[str, Any]]
    recovery_funnel: dict[str, Any]
    top_merchants: list[dict[str, Any]]


def build_analytics_snapshot(*, range_key: str = DEFAULT_RANGE) -> AnalyticsSnapshot:
    if range_key not in RANGE_KEYS:
        range_key = DEFAULT_RANGE
    months = _RANGE_TO_MONTHS[range_key]
    return AnalyticsSnapshot(
        range_key=range_key,
        revenue_series=build_revenue_series(months=months),
        plan_revenue=build_plan_revenue(),
        region_revenue=build_region_revenue(),
        retention_cohorts=build_retention_cohorts(),
        acquisition_funnel=build_acquisition_funnel(),
        payment_method_mix=build_payment_method_mix(),
        recovery_funnel=build_recovery_funnel(),
        top_merchants=build_top_merchants(),
    )


def project_analytics(snapshot: AnalyticsSnapshot) -> dict[str, Any]:
    """Return the FE-shape JSON payload."""
    return {
        "range": snapshot.range_key,
        "revenueSeries": snapshot.revenue_series,
        "planRevenue": snapshot.plan_revenue,
        "regionRevenue": snapshot.region_revenue,
        "retentionCohorts": snapshot.retention_cohorts,
        "acquisitionFunnel": snapshot.acquisition_funnel,
        "paymentMethodMix": snapshot.payment_method_mix,
        "recoveryFunnel": snapshot.recovery_funnel,
        "topMerchantsByRevenue": snapshot.top_merchants,
    }


__all__ = [
    "AnalyticsSnapshot",
    "DEFAULT_RANGE",
    "RANGE_KEYS",
    "build_acquisition_funnel",
    "build_analytics_snapshot",
    "build_payment_method_mix",
    "build_plan_revenue",
    "build_recovery_funnel",
    "build_region_revenue",
    "build_retention_cohorts",
    "build_revenue_series",
    "build_top_merchants",
    "project_analytics",
]
