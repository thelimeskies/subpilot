"""Dunning domain models.

Full lifecycle (DunningRun, NotificationLog) lands in Sprint 3 per
docs/delivery/django-file-by-file-build-plan.md. The :class:`DunningPolicy`
is created here in Sprint 1d so :class:`apps.catalog.models.Plan` can
reference it via FK.
"""
from __future__ import annotations

from django.db import models

from apps.common.models import TenantDomainModel


class DunningPolicy(TenantDomainModel):
    class FinalAction(models.TextChoices):
        CANCEL = "cancel", "Cancel Subscription"
        PAUSE = "pause", "Pause Subscription"
        MARK_UNCOLLECTIBLE = "mark_uncollectible", "Mark Invoice Uncollectible"
        DO_NOTHING = "do_nothing", "Do Nothing"

    class HardFailureBehavior(models.TextChoices):
        STOP = "stop_until_pm_replaced", "Stop until payment method replaced"
        RETRY = "retry", "Retry on schedule"

    name = models.CharField(max_length=200)
    retry_offsets_days = models.JSONField(default=list, blank=True)
    grace_period_days = models.PositiveIntegerField(default=0)
    final_action = models.CharField(
        max_length=24, choices=FinalAction.choices, default=FinalAction.CANCEL
    )
    notify_email = models.BooleanField(default=True)
    notify_sms = models.BooleanField(default=False)
    notify_webhook = models.BooleanField(default=True)
    hard_failure_behavior = models.CharField(
        max_length=32,
        choices=HardFailureBehavior.choices,
        default=HardFailureBehavior.STOP,
    )

    class Meta:
        db_table = "dunning_policy"
        constraints = [
            models.UniqueConstraint(
                fields=["merchant", "environment", "name"],
                name="uniq_dunningpolicy_merchant_env_name",
            ),
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.name} ({self.final_action})"


class DunningRun(TenantDomainModel):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspended (awaiting payment method)"
        RECOVERED = "recovered", "Recovered"
        EXHAUSTED = "exhausted", "Exhausted"
        CANCELED = "canceled", "Canceled"

    invoice = models.ForeignKey(
        "invoices.Invoice", on_delete=models.PROTECT, related_name="dunning_runs"
    )
    subscription = models.ForeignKey(
        "subscriptions.Subscription",
        on_delete=models.SET_NULL,
        related_name="dunning_runs",
        null=True,
        blank=True,
    )
    policy = models.ForeignKey(
        DunningPolicy, on_delete=models.PROTECT, related_name="runs"
    )
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.ACTIVE, db_index=True
    )
    attempt_count = models.PositiveIntegerField(default=0)
    started_at = models.DateTimeField(auto_now_add=True)
    next_retry_at = models.DateTimeField(null=True, blank=True, db_index=True)
    recovered_at = models.DateTimeField(null=True, blank=True)
    exhausted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "dunning_run"
        constraints = [
            # Only one active dunning run per invoice (partial unique).
            models.UniqueConstraint(
                fields=["invoice"],
                condition=models.Q(status="active"),
                name="uniq_active_dunningrun_per_invoice",
            ),
        ]
        indexes = [
            models.Index(
                fields=["merchant", "environment", "status", "next_retry_at"],
                name="dr_scope_status_retry_idx",
            ),
        ]


class NotificationLog(TenantDomainModel):
    class Channel(models.TextChoices):
        EMAIL = "email", "Email"
        SMS = "sms", "SMS"
        WEBHOOK = "webhook", "Webhook"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"

    dunning_run = models.ForeignKey(
        DunningRun, on_delete=models.CASCADE, related_name="notifications"
    )
    channel = models.CharField(max_length=16, choices=Channel.choices)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    template_key = models.CharField(max_length=64, blank=True, default="")
    sent_at = models.DateTimeField(null=True, blank=True)
    failure_message = models.CharField(max_length=400, blank=True, default="")

    class Meta:
        db_table = "dunning_notificationlog"
