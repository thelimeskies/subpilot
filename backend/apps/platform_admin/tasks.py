"""Celery tasks for the platform admin app.

The platform overview snapshot is recomputed every 15 minutes by Celery
beat (see [config/celery.py](file:///Users/mac/Desktop/Projects/HackathonxNomba/backend/config/celery.py))
so cold-cache reads on the dashboard remain rare.
"""
from __future__ import annotations

from celery import shared_task


@shared_task(
    name="apps.platform_admin.tasks.refresh_platform_overview",
    queue="analytics",
)
def refresh_platform_overview() -> dict:
    """Recompute and cache the cross-tenant overview snapshot."""
    from apps.platform_admin.services.overview import (
        refresh_platform_overview as _refresh,
    )

    payload = _refresh(actor_label="celery")
    return {
        "refreshed": True,
        "live_merchants": payload["raw"]["liveMerchants"],
        "mrr_minor": payload["raw"]["mrrMinor"],
        "net_revenue_this_month_minor": payload["raw"]["netRevenueThisMonthMinor"],
    }
