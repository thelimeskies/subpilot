"""Dunning selectors."""
from __future__ import annotations

from django.db.models import QuerySet

from .models import DunningPolicy, DunningRun, NotificationLog


def policies_for(merchant, environment) -> QuerySet[DunningPolicy]:
    return DunningPolicy.objects.filter(merchant=merchant, environment=environment).order_by("name")


def runs_for(merchant, environment) -> QuerySet[DunningRun]:
    return (
        DunningRun.objects.filter(merchant=merchant, environment=environment)
        .select_related("invoice", "subscription", "policy")
    )


def active_runs_for(merchant, environment) -> QuerySet[DunningRun]:
    return runs_for(merchant, environment).filter(status=DunningRun.Status.ACTIVE)


def notifications_for_run(run: DunningRun) -> QuerySet[NotificationLog]:
    return NotificationLog.objects.filter(dunning_run=run).order_by("-created_at")
