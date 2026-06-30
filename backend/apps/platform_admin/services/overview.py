"""Cache + audit wrapper around the cross-tenant overview selector.

Mirrors :mod:`apps.analytics.services.refresh_metrics` but stores the
platform-wide snapshot under a single Redis key and never accepts a
tenant scope.
"""
from __future__ import annotations

from django.core.cache import cache

from apps.audit.services.log_event import log_event

from ..selectors.overview import platform_overview
from .formatting import format_compact_money, format_pct

_CACHE_TTL = 60 * 15  # 15 minutes
_CACHE_KEY = "platform:overview:stats"


def _to_fe_shape(snapshot) -> dict:
    """Project the dataclass to the camelCase shape the FE seed expects."""
    delta_count = snapshot.live_merchants_delta
    delta_text = (
        f"+{delta_count} this month" if delta_count >= 0 else f"{delta_count} this month"
    )
    return {
        "liveMerchants": snapshot.live_merchants,
        "liveMerchantsDelta": delta_text,
        "mrr": format_compact_money(snapshot.mrr_minor, snapshot.currency),
        "mrrDelta": format_pct(snapshot.mrr_delta_pct, signed=True),
        "revenueAtRisk": format_compact_money(
            snapshot.revenue_at_risk_minor, snapshot.currency
        ),
        "revenueAtRiskDelta": (
            f"{snapshot.failed_invoice_count} failed invoice"
            + ("s" if snapshot.failed_invoice_count != 1 else "")
        ),
        "webhookHealth": format_pct(snapshot.webhook_health_pct),
        "webhookHealthDelta": (
            f"{snapshot.webhook_retries_in_flight} retr"
            + ("ies" if snapshot.webhook_retries_in_flight != 1 else "y")
        ),
        "recoveredThisMonth": format_compact_money(
            snapshot.recovered_this_month_minor, snapshot.currency
        ),
        "collectedThisMonth": format_compact_money(
            snapshot.collected_this_month_minor, snapshot.currency
        ),
        "netRevenueThisMonth": format_compact_money(
            snapshot.net_revenue_this_month_minor, snapshot.currency
        ),
        "recoveryRate": format_pct(snapshot.recovery_rate_pct),
        # Raw fields (minor units) so power users can drill in without
        # re-parsing the formatted strings.
        "raw": {
            "liveMerchants": snapshot.live_merchants,
            "liveMerchantsDelta": snapshot.live_merchants_delta,
            "mrrMinor": snapshot.mrr_minor,
            "mrrDeltaPct": snapshot.mrr_delta_pct,
            "revenueAtRiskMinor": snapshot.revenue_at_risk_minor,
            "failedInvoiceCount": snapshot.failed_invoice_count,
            "webhookHealthPct": snapshot.webhook_health_pct,
            "webhookRetriesInFlight": snapshot.webhook_retries_in_flight,
            "recoveredThisMonthMinor": snapshot.recovered_this_month_minor,
            "collectedThisMonthMinor": snapshot.collected_this_month_minor,
            "netRevenueThisMonthMinor": snapshot.net_revenue_this_month_minor,
            "recoveryRatePct": snapshot.recovery_rate_pct,
            "currency": snapshot.currency,
        },
    }


def refresh_platform_overview(*, actor_label: str | None = None, request=None) -> dict:
    """Recompute, cache and return the overview snapshot."""
    snapshot = platform_overview()
    payload = _to_fe_shape(snapshot)
    cache.set(_CACHE_KEY, payload, _CACHE_TTL)
    log_event(
        action="platform.overview.refreshed",
        actor_user=None,
        actor_label=actor_label or "system",
        actor_role="platform_admin",
        merchant=None,
        environment=None,
        target_type="platform",
        target_id="overview",
        metadata={
            "live_merchants": snapshot.live_merchants,
            "mrr_minor": snapshot.mrr_minor,
            "revenue_at_risk_minor": snapshot.revenue_at_risk_minor,
        },
        request=request,
    )
    return payload


def get_cached_overview() -> dict | None:
    return cache.get(_CACHE_KEY)


def get_or_refresh_overview(*, actor_label: str | None = None, request=None) -> dict:
    """Read cache; on miss compute synchronously and warm cache."""
    cached = get_cached_overview()
    if cached is not None:
        return cached
    return refresh_platform_overview(actor_label=actor_label, request=request)
