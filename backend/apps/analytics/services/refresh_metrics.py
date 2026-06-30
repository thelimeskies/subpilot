"""Service: refresh_metrics.

Computes the latest dashboard snapshot for a merchant + environment and
caches it in Redis so the dashboard doesn't recompute aggregates on every
request. The Celery beat schedule fires
:func:`apps.analytics.tasks.refresh_dashboard_metrics` every 15 minutes per
[docs/technical/celery-job-contracts.md](file:///Users/mac/Desktop/Projects/HackathonxNomba/docs/technical/celery-job-contracts.md).
"""
from __future__ import annotations

from django.core.cache import cache

from apps.audit.services.log_event import log_event
from apps.common.db import atomic_with_retry

from ..selectors import dashboard_overview

_CACHE_TTL = 60 * 15  # 15 minutes
_CACHE_KEY = "analytics:overview:{merchant_id}:{env_id}"


def cache_key(*, merchant_id: str, environment_id: str) -> str:
    return _CACHE_KEY.format(merchant_id=merchant_id, env_id=environment_id)


@atomic_with_retry
def refresh_metrics(*, merchant, environment, actor_user=None, request=None) -> dict:
    """Recompute, cache, and return the dashboard overview snapshot."""
    overview = dashboard_overview(merchant=merchant, environment=environment)
    payload = overview.as_dict()
    cache.set(
        cache_key(merchant_id=str(merchant.id), environment_id=str(environment.id)),
        payload,
        _CACHE_TTL,
    )
    log_event(
        action="analytics.metrics_refreshed",
        actor_user=actor_user,
        merchant=merchant,
        environment=environment,
        target_type="merchant",
        target_id=str(merchant.id),
        metadata={
            "mrr_minor": payload["mrr_minor"],
            "collected_revenue_minor": payload["collected_revenue_minor"],
            "active_subscriptions": payload["active_subscriptions"],
            "revenue_at_risk_minor": payload["revenue_at_risk_minor"],
        },
        request=request,
    )
    return payload


def get_cached_overview(*, merchant, environment) -> dict | None:
    return cache.get(
        cache_key(merchant_id=str(merchant.id), environment_id=str(environment.id))
    )
