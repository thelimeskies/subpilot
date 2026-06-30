"""Catalog domain: Product, Plan, PriceVersion, PlanFeature.

All tenant-scoped via :class:`apps.common.models.TenantDomainModel`.

Money is stored in integer minor units per docs/technical/django-model-contracts.md.
"""
from __future__ import annotations

from django.db import models
from django.db.models import Q

from apps.common.models import BaseDomainModel, TenantDomainModel


class Product(TenantDomainModel):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        ARCHIVED = "archived", "Archived"

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, default="")
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.ACTIVE, db_index=True
    )
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "catalog_product"
        constraints = [
            models.UniqueConstraint(
                fields=["merchant", "environment", "name"],
                name="uniq_product_merchant_env_name",
            ),
        ]
        indexes = [
            models.Index(fields=["merchant", "environment", "status"], name="product_scope_status_idx"),
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.name} ({self.status})"


class Plan(TenantDomainModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ACTIVE = "active", "Active"
        ARCHIVED = "archived", "Archived"

    class ProrationPolicy(models.TextChoices):
        PRORATE = "prorate", "Prorate"
        NONE = "none", "No Proration"

    class CancellationPolicy(models.TextChoices):
        AT_PERIOD_END = "at_period_end", "At Period End"
        IMMEDIATE = "immediate", "Immediate"

    product = models.ForeignKey(
        Product, on_delete=models.PROTECT, related_name="plans"
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, default="")
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.DRAFT, db_index=True
    )
    trial_days = models.PositiveIntegerField(default=0)
    dunning_policy = models.ForeignKey(
        "dunning.DunningPolicy",
        on_delete=models.SET_NULL,
        related_name="plans",
        null=True,
        blank=True,
    )
    proration_policy = models.CharField(
        max_length=16, choices=ProrationPolicy.choices, default=ProrationPolicy.PRORATE
    )
    cancellation_policy = models.CharField(
        max_length=20,
        choices=CancellationPolicy.choices,
        default=CancellationPolicy.AT_PERIOD_END,
    )
    tokenized_renewal = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "catalog_plan"
        constraints = [
            models.UniqueConstraint(
                fields=["merchant", "environment", "product", "name"],
                name="uniq_plan_merchant_env_product_name",
            ),
        ]
        indexes = [
            models.Index(fields=["merchant", "environment", "status"], name="plan_scope_status_idx"),
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.product.name} / {self.name} ({self.status})"


class PriceVersion(BaseDomainModel):
    class IntervalUnit(models.TextChoices):
        DAY = "day", "Day"
        WEEK = "week", "Week"
        MONTH = "month", "Month"
        YEAR = "year", "Year"

    plan = models.ForeignKey(Plan, on_delete=models.CASCADE, related_name="price_versions")
    amount_minor = models.BigIntegerField()
    currency = models.CharField(max_length=3)
    interval_unit = models.CharField(max_length=8, choices=IntervalUnit.choices)
    interval_count = models.PositiveIntegerField(default=1)
    setup_fee_minor = models.BigIntegerField(default=0)
    active_from = models.DateTimeField(null=True, blank=True)
    active_to = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "catalog_priceversion"
        constraints = [
            models.CheckConstraint(check=Q(amount_minor__gt=0), name="priceversion_amount_positive"),
            models.CheckConstraint(check=Q(interval_count__gt=0), name="priceversion_interval_positive"),
            # At most one *currently* active price version per plan: enforced at the
            # service layer (apps/catalog/services/create_price_version.py) by closing
            # off the prior active row's active_to before opening a new one.
            models.UniqueConstraint(
                fields=["plan"],
                condition=Q(active_to__isnull=True),
                name="uniq_active_priceversion_per_plan",
            ),
        ]
        indexes = [
            models.Index(fields=["plan", "active_from"], name="priceversion_plan_from_idx"),
        ]

    def __str__(self) -> str:  # pragma: no cover
        major = self.amount_minor / 100.0
        return f"{self.plan.name} {self.currency} {major:.2f}/{self.interval_count}{self.interval_unit}"


class PlanFeature(BaseDomainModel):
    """Marketing-style feature labels rendered on plan cards."""

    plan = models.ForeignKey(Plan, on_delete=models.CASCADE, related_name="features")
    label = models.CharField(max_length=200)
    detail = models.CharField(max_length=400, blank=True, default="")
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "catalog_planfeature"
        constraints = [
            models.UniqueConstraint(
                fields=["plan", "label"], name="uniq_planfeature_plan_label"
            ),
        ]
        ordering = ["sort_order", "label"]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.plan.name}: {self.label}"
