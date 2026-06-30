"""Celery tasks for the analytics app.

`refresh_dashboard_metrics` is the worker-side counterpart of
[`refresh_metrics`](file:///Users/mac/Desktop/Projects/HackathonxNomba/backend/apps/analytics/services/refresh_metrics.py).
The beat scheduler fires it every 15 minutes per
[docs/technical/celery-job-contracts.md](file:///Users/mac/Desktop/Projects/HackathonxNomba/docs/technical/celery-job-contracts.md).
"""
from __future__ import annotations

from celery import shared_task


@shared_task(name="apps.analytics.tasks.refresh_dashboard_metrics", queue="analytics")
def refresh_dashboard_metrics(merchant_id: str | None = None, environment_id: str | None = None) -> dict:
    """Recompute the dashboard snapshot for one tenant or all tenants.

    Called with no arguments by Celery Beat — fans out across every active
    merchant + environment pair. Called with explicit IDs from the dashboard
    when a manual refresh is requested.
    """
    from apps.accounts.models import Environment, Merchant
    from apps.analytics.services.refresh_metrics import refresh_metrics

    if merchant_id and environment_id:
        merchant = Merchant.objects.filter(pk=merchant_id).first()
        environment = Environment.objects.filter(pk=environment_id).first()
        if not (merchant and environment):
            return {"refreshed": 0, "reason": "merchant_or_environment_not_found"}
        refresh_metrics(merchant=merchant, environment=environment)
        return {"refreshed": 1, "merchant_id": str(merchant_id), "environment_id": str(environment_id)}

    refreshed = 0
    for env in Environment.objects.select_related("merchant").iterator():
        try:
            refresh_metrics(merchant=env.merchant, environment=env)
            refreshed += 1
        except Exception:  # noqa: BLE001 — one bad tenant must not break the loop
            continue
    return {"refreshed": refreshed}
