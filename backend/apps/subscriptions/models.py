"""Subscription domain models.

Full state-machine + lifecycle services land in Sprint 2 per
docs/delivery/django-file-by-file-build-plan.md. The base ``Subscription`` and
``SubscriptionItem`` rows are introduced here so cross-app FKs (e.g. on
``customers.PortalSession``) can resolve.
"""
from __future__ import annotations

from django.db import models
from django.db.models import Q

from apps.common.models import BaseDomainModel, TenantDomainModel


class Subscription(TenantDomainModel):
    class Status(models.TextChoices):
        INCOMPLETE = "incomplete", "Incomplete"
        TRIALING = "trialing", "Trialing"
        ACTIVE = "active", "Active"
        PAST_DUE = "past_due", "Past Due"
        PAUSED = "paused", "Paused"
        CANCELED = "canceled", "Canceled"
        EXPIRED = "expired", "Expired"

    customer = models.ForeignKey(
        "customers.Customer", on_delete=models.PROTECT, related_name="subscriptions"
    )
    plan = models.ForeignKey(
        "catalog.Plan", on_delete=models.PROTECT, related_name="subscriptions"
    )
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.INCOMPLETE, db_index=True
    )
    billing_anchor = models.DateTimeField(null=True, blank=True)
    current_period_start = models.DateTimeField(null=True, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True, db_index=True)
    trial_end = models.DateTimeField(null=True, blank=True)
    cancel_at_period_end = models.BooleanField(default=False)
    canceled_at = models.DateTimeField(null=True, blank=True)
    default_payment_method = models.ForeignKey(
        "customers.PaymentMethod",
        on_delete=models.SET_NULL,
        related_name="default_for_subscriptions",
        null=True,
        blank=True,
    )
    dunning_policy = models.ForeignKey(
        "dunning.DunningPolicy",
        on_delete=models.SET_NULL,
        related_name="subscriptions",
        null=True,
        blank=True,
    )
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "subscriptions_subscription"
        indexes = [
            models.Index(
                fields=["merchant", "environment", "status", "current_period_end"],
                name="sub_scope_status_periodend_idx",
            ),
            models.Index(
                fields=["merchant", "environment", "customer"],
                name="sub_scope_customer_idx",
            ),
        ]


class SubscriptionItem(BaseDomainModel):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        REMOVED = "removed", "Removed"

    subscription = models.ForeignKey(
        Subscription, on_delete=models.CASCADE, related_name="items"
    )
    price_version = models.ForeignKey(
        "catalog.PriceVersion", on_delete=models.PROTECT, related_name="subscription_items"
    )
    quantity = models.PositiveIntegerField(default=1)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.ACTIVE
    )

    class Meta:
        db_table = "subscriptions_subscriptionitem"
        constraints = [
            models.CheckConstraint(check=Q(quantity__gt=0), name="subitem_qty_positive"),
        ]


class SubscriptionEvent(BaseDomainModel):
    """Append-only state-transition log for a subscription."""

    subscription = models.ForeignKey(
        Subscription, on_delete=models.CASCADE, related_name="events"
    )
    event_type = models.CharField(max_length=64, db_index=True)
    from_status = models.CharField(max_length=16, blank=True, default="")
    to_status = models.CharField(max_length=16, blank=True, default="")
    actor_label = models.CharField(max_length=200, blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)
    occurred_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "subscriptions_subscriptionevent"
        ordering = ["-occurred_at"]
