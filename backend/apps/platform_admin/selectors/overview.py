"""Cross-tenant selectors for the platform admin overview.

These mirror the per-tenant selectors in
[apps/analytics/selectors.py](file:///Users/mac/Desktop/Projects/HackathonxNomba/backend/apps/analytics/selectors.py)
but query across ALL merchants. Only :func:`platform_overview` is exposed —
callers never aggregate by hand.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import timedelta

from django.db.models import Count, Q, Sum
from django.utils import timezone

from apps.accounts.models import Merchant

# Reuse the interval-normalisation helper from the merchant analytics layer
# so platform MRR and merchant MRR cannot diverge.
from apps.analytics.selectors import _normalise_to_monthly_minor  # noqa: PLC2701
from apps.dunning.models import DunningRun
from apps.events.models import WebhookDelivery
from apps.invoices.models import Invoice
from apps.payments.models import BalanceTransaction
from apps.subscriptions.models import Subscription, SubscriptionItem


@dataclass(frozen=True)
class PlatformOverview:
    live_merchants: int
    live_merchants_delta: int  # change vs 30 days ago

    mrr_minor: int
    mrr_delta_pct: float  # vs 30 days ago

    revenue_at_risk_minor: int
    failed_invoice_count: int

    webhook_health_pct: float  # last 24h delivered/total
    webhook_retries_in_flight: int

    recovered_this_month_minor: int
    collected_this_month_minor: int
    net_revenue_this_month_minor: int
    recovery_rate_pct: float  # last 30 days

    currency: str

    def as_dict(self) -> dict:
        return asdict(self)


# --- Component selectors ---------------------------------------------------


def live_merchants_count() -> int:
    return Merchant.objects.filter(status=Merchant.Status.ACTIVE).count()


def merchants_created_since(*, since) -> int:
    return Merchant.objects.filter(
        status=Merchant.Status.ACTIVE, created_at__gte=since
    ).count()


def platform_mrr_minor() -> tuple[int, str]:
    """Sum monthly-normalised recurring revenue across ALL merchants.

    Returns ``(amount_minor, currency)``. Currency is taken from the most
    common merchant default (NGN in this stack). When merchants mix
    currencies in production this should be reported as a list — for now
    we collapse to one bucket.
    """
    items = (
        SubscriptionItem.objects.select_related("price_version", "subscription")
        .filter(
            subscription__status__in=[
                Subscription.Status.ACTIVE,
                Subscription.Status.TRIALING,
                Subscription.Status.PAST_DUE,
            ],
            status=SubscriptionItem.Status.ACTIVE,
        )
    )
    total = 0
    currency = "NGN"
    for item in items:
        pv = item.price_version
        if pv is None:
            continue
        line = pv.amount_minor * max(1, int(item.quantity or 1))
        total += _normalise_to_monthly_minor(line, pv.interval_unit, pv.interval_count)
        if pv.currency:
            currency = pv.currency
    return total, currency


def platform_revenue_at_risk_minor() -> tuple[int, int]:
    """Returns (sum_amount_due_minor, failed_invoice_count) across all tenants."""
    qs = Invoice.objects.filter(
        status=Invoice.Status.OPEN,
        dunning_runs__status=DunningRun.Status.ACTIVE,
    ).distinct()
    agg = qs.aggregate(total=Sum("amount_due_minor"), n=Count("id"))
    return int(agg["total"] or 0), int(agg["n"] or 0)


def platform_webhook_health(*, hours: int = 24) -> tuple[float, int]:
    """Returns (delivered_pct_last_n_hours, retries_in_flight)."""
    since = timezone.now() - timedelta(hours=hours)
    counts = WebhookDelivery.objects.filter(created_at__gte=since).aggregate(
        delivered=Count("id", filter=Q(status=WebhookDelivery.Status.DELIVERED)),
        total=Count("id"),
    )
    total = int(counts["total"] or 0)
    delivered = int(counts["delivered"] or 0)
    pct = round(100.0 * delivered / total, 2) if total else 100.0
    in_flight = WebhookDelivery.objects.filter(
        status__in=[WebhookDelivery.Status.PENDING, WebhookDelivery.Status.FAILED],
    ).count()
    return pct, in_flight


def platform_recovery(*, days: int = 30) -> tuple[int, float]:
    """Returns (recovered_minor_this_month, recovery_rate_pct).

    Recovered amount: sum of charge balance transactions from invoices linked
    to a dunning run that ended in RECOVERED state in the last ``days``.
    Recovery rate: percentage of dunning runs that ended RECOVERED out of
    those that terminated (RECOVERED + EXHAUSTED + CANCELED) in the window.
    """
    cutoff = timezone.now() - timedelta(days=days)
    runs = DunningRun.objects.filter(updated_at__gte=cutoff)
    counts = runs.aggregate(
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
    rate = round(100.0 * int(counts["recovered"] or 0) / terminated, 2) if terminated else 0.0
    recovered_minor = (
        BalanceTransaction.objects.filter(
            type=BalanceTransaction.Type.CHARGE,
            invoice__dunning_runs__status=DunningRun.Status.RECOVERED,
            invoice__dunning_runs__updated_at__gte=cutoff,
        )
        .distinct()
        .aggregate(total=Sum("signed_amount_minor"))
    )
    return int(recovered_minor["total"] or 0), rate


def platform_collected_revenue(*, days: int = 30) -> tuple[int, int]:
    """Returns (gross_charges_minor, net_charge_less_refund_minor)."""
    cutoff = timezone.now() - timedelta(days=days)
    gross = BalanceTransaction.objects.filter(
        type=BalanceTransaction.Type.CHARGE,
        created_at__gte=cutoff,
    ).aggregate(total=Sum("signed_amount_minor"))["total"]
    net = BalanceTransaction.objects.filter(
        type__in=[BalanceTransaction.Type.CHARGE, BalanceTransaction.Type.REFUND],
        created_at__gte=cutoff,
    ).aggregate(total=Sum("signed_amount_minor"))["total"]
    return int(gross or 0), int(net or 0)


# --- Aggregator ------------------------------------------------------------


def platform_overview() -> PlatformOverview:
    """Single call used by the platform overview endpoint + Celery refresh."""
    now = timezone.now()
    thirty_days_ago = now - timedelta(days=30)

    live_now = live_merchants_count()
    new_30d = merchants_created_since(since=thirty_days_ago)

    mrr, currency = platform_mrr_minor()
    # MRR delta % vs 30 days ago is approximated by counting current MRR
    # against the count of subscriptions that existed before the cutoff.
    # For S2 we report a simple "+X% vs prior month" derived from the
    # fraction of subs created in the last 30 days; richer time-series
    # belongs in S11.
    older_subs = Subscription.objects.filter(
        status__in=[Subscription.Status.ACTIVE, Subscription.Status.TRIALING],
        created_at__lt=thirty_days_ago,
    ).count()
    new_subs = Subscription.objects.filter(
        status__in=[Subscription.Status.ACTIVE, Subscription.Status.TRIALING],
        created_at__gte=thirty_days_ago,
    ).count()
    mrr_delta = round(100.0 * new_subs / older_subs, 2) if older_subs else 0.0

    rar_minor, failed = platform_revenue_at_risk_minor()
    health_pct, retries = platform_webhook_health()
    recovered_minor, recovery_rate = platform_recovery()
    collected_minor, net_revenue_minor = platform_collected_revenue()

    return PlatformOverview(
        live_merchants=live_now,
        live_merchants_delta=new_30d,
        mrr_minor=mrr,
        mrr_delta_pct=mrr_delta,
        revenue_at_risk_minor=rar_minor,
        failed_invoice_count=failed,
        webhook_health_pct=health_pct,
        webhook_retries_in_flight=retries,
        recovered_this_month_minor=recovered_minor,
        collected_this_month_minor=collected_minor,
        net_revenue_this_month_minor=net_revenue_minor,
        recovery_rate_pct=recovery_rate,
        currency=currency,
    )
