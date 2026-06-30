"""Read-only analytics selectors for the merchant dashboard.

All selectors are merchant + environment scoped. Numbers are returned in
**minor units** (e.g. kobo, cents) so the API layer never loses precision.
The dashboard converts to major units client-side.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import timedelta

from django.db.models import Count, Q, Sum
from django.utils import timezone

from apps.catalog.models import PriceVersion
from apps.dunning.models import DunningRun
from apps.invoices.models import Invoice
from apps.payments.models import BalanceTransaction
from apps.subscriptions.models import Subscription, SubscriptionItem

# ---------------------------------------------------------------------------
# MRR
# ---------------------------------------------------------------------------

# Approximate days in a month for normalising non-monthly intervals into MRR.
_DAYS_IN_MONTH = 30
_INTERVAL_DAYS = {
    PriceVersion.IntervalUnit.DAY: 1,
    PriceVersion.IntervalUnit.WEEK: 7,
    PriceVersion.IntervalUnit.MONTH: 30,
    PriceVersion.IntervalUnit.YEAR: 365,
}


def _normalise_to_monthly_minor(amount_minor: int, unit: str, count: int) -> int:
    """Convert a recurring price into its monthly-equivalent minor amount."""
    days = _INTERVAL_DAYS.get(unit, 30) * max(1, int(count or 1))
    if days <= 0:
        return 0
    return int(round(amount_minor * _DAYS_IN_MONTH / days))


@dataclass(frozen=True)
class MetricsOverview:
    mrr_minor: int
    active_subscriptions: int
    trialing_subscriptions: int
    past_due_subscriptions: int
    revenue_at_risk_minor: int
    collected_revenue_minor: int
    recovery_rate_pct: float
    open_invoices_minor: int
    currency: str

    def as_dict(self) -> dict:
        return asdict(self)


def mrr_minor(*, merchant, environment) -> tuple[int, str]:
    """Sum of monthly-normalised recurring revenue across active + trialing
    + past_due subscriptions for the given tenant scope.

    Excludes ``canceled``, ``expired``, ``paused`` and ``incomplete`` per the
    plan ([Sprint 4 acceptance](file:///Users/mac/Desktop/Projects/HackathonxNomba/docs/delivery/django-file-by-file-build-plan.md#L424)).
    Returns ``(amount_minor, currency)`` — currency falls back to merchant
    default when no items exist.
    """
    qs = (
        SubscriptionItem.objects.select_related("price_version", "subscription")
        .filter(
            subscription__merchant=merchant,
            subscription__environment=environment,
            subscription__status__in=[
                Subscription.Status.ACTIVE,
                Subscription.Status.TRIALING,
                Subscription.Status.PAST_DUE,
            ],
            status=SubscriptionItem.Status.ACTIVE,
        )
    )
    total = 0
    currency = getattr(merchant, "default_currency", "") or "NGN"
    for item in qs:
        pv = item.price_version
        if pv is None:
            continue
        line = pv.amount_minor * max(1, int(item.quantity or 1))
        total += _normalise_to_monthly_minor(line, pv.interval_unit, pv.interval_count)
        currency = pv.currency or currency
    return total, currency


def active_subscriptions_count(*, merchant, environment) -> int:
    return Subscription.objects.filter(
        merchant=merchant,
        environment=environment,
        status=Subscription.Status.ACTIVE,
    ).count()


def subscription_status_counts(*, merchant, environment) -> dict[str, int]:
    rows = (
        Subscription.objects.filter(merchant=merchant, environment=environment)
        .values("status")
        .annotate(n=Count("id"))
    )
    out = {choice.value: 0 for choice in Subscription.Status}
    for row in rows:
        out[row["status"]] = row["n"]
    return out


def revenue_at_risk_minor(*, merchant, environment) -> int:
    """Outstanding ``amount_due_minor`` across **open** invoices that have an
    **active** dunning run — i.e. money the recovery engine is fighting for.
    """
    risk = (
        Invoice.objects.filter(
            merchant=merchant,
            environment=environment,
            status=Invoice.Status.OPEN,
            dunning_runs__status=DunningRun.Status.ACTIVE,
        )
        .distinct()
        .aggregate(total=Sum("amount_due_minor"))
    )
    return int(risk["total"] or 0)


def open_invoices_minor(*, merchant, environment) -> int:
    """Total ``amount_due_minor`` across all open invoices regardless of dunning."""
    agg = Invoice.objects.filter(
        merchant=merchant,
        environment=environment,
        status=Invoice.Status.OPEN,
    ).aggregate(total=Sum("amount_due_minor"))
    return int(agg["total"] or 0)


def collected_revenue_minor(*, merchant, environment, days: int = 30) -> int:
    """Net collected cash movements for this tenant in the trailing window."""
    cutoff = timezone.now() - timedelta(days=days)
    agg = BalanceTransaction.objects.filter(
        merchant=merchant,
        environment=environment,
        type__in=[BalanceTransaction.Type.CHARGE, BalanceTransaction.Type.REFUND],
        created_at__gte=cutoff,
    ).aggregate(total=Sum("signed_amount_minor"))
    return int(agg["total"] or 0)


def recovery_rate_pct(*, merchant, environment, days: int = 30) -> float:
    """Percentage of dunning runs in the last ``days`` that ended ``recovered``.

    Returns ``0.0`` when no runs have terminated in the window.
    """
    cutoff = timezone.now() - timedelta(days=days)
    qs = DunningRun.objects.filter(
        merchant=merchant,
        environment=environment,
        updated_at__gte=cutoff,
    )
    counts = qs.aggregate(
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
    terminated = int(counts["terminated"] or 0)
    if terminated == 0:
        return 0.0
    return round(100.0 * int(counts["recovered"] or 0) / terminated, 2)


def dashboard_overview(*, merchant, environment) -> MetricsOverview:
    """Single-call snapshot used by ``DashboardOverviewView``."""
    mrr, currency = mrr_minor(merchant=merchant, environment=environment)
    counts = subscription_status_counts(merchant=merchant, environment=environment)
    return MetricsOverview(
        mrr_minor=mrr,
        active_subscriptions=counts.get(Subscription.Status.ACTIVE, 0),
        trialing_subscriptions=counts.get(Subscription.Status.TRIALING, 0),
        past_due_subscriptions=counts.get(Subscription.Status.PAST_DUE, 0),
        revenue_at_risk_minor=revenue_at_risk_minor(
            merchant=merchant, environment=environment
        ),
        collected_revenue_minor=collected_revenue_minor(
            merchant=merchant, environment=environment
        ),
        recovery_rate_pct=recovery_rate_pct(merchant=merchant, environment=environment),
        open_invoices_minor=open_invoices_minor(
            merchant=merchant, environment=environment
        ),
        currency=currency,
    )
