"""Celery application factory.

The app autodiscovers tasks across installed Django apps and routes them to
six dedicated queues (`billing`, `payments`, `dunning`, `webhooks`,
`notifications`, `analytics`) per docs/technical/celery-job-contracts.md.
"""
from __future__ import annotations

import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

app = Celery("subpilot")

# Pull all CELERY_* settings from Django.
app.config_from_object("django.conf:settings", namespace="CELERY")

app.autodiscover_tasks()


# Beat schedule per docs/technical/celery-job-contracts.md.
# Demo cadence is every 15 minutes for billing scans, dunning retries, and analytics.
app.conf.beat_schedule = {
    "billing-scan-due-subscriptions-every-15min": {
        "task": "apps.subscriptions.tasks.scan_due_subscriptions",
        "schedule": crontab(minute="*/15"),
        "options": {"queue": "billing"},
    },
    "dunning-process-due-retries-every-15min": {
        "task": "apps.dunning.tasks.process_due_retries",
        "schedule": crontab(minute="*/15"),
        "options": {"queue": "dunning"},
    },
    "analytics-refresh-dashboard-metrics-every-15min": {
        "task": "apps.analytics.tasks.refresh_dashboard_metrics",
        "schedule": crontab(minute="*/15"),
        "options": {"queue": "analytics"},
    },
    "platform-refresh-overview-every-15min": {
        "task": "apps.platform_admin.tasks.refresh_platform_overview",
        "schedule": crontab(minute="*/15"),
        "options": {"queue": "analytics"},
    },
}


@app.task(bind=True)
def debug_task(self):  # pragma: no cover
    print(f"Request: {self.request!r}")
