"""Invoice domain models.

Lifecycle services (create, finalize, mark paid, void, mark uncollectible) land
in Sprint 2 per docs/delivery/django-file-by-file-build-plan.md.
"""
from __future__ import annotations

from django.db import models
from django.db.models import Q

from apps.common.models import BaseDomainModel, TenantDomainModel


class Invoice(TenantDomainModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        OPEN = "open", "Open"
        PAID = "paid", "Paid"
        VOID = "void", "Void"
        UNCOLLECTIBLE = "uncollectible", "Uncollectible"

    customer = models.ForeignKey(
        "customers.Customer", on_delete=models.PROTECT, related_name="invoices"
    )
    subscription = models.ForeignKey(
        "subscriptions.Subscription",
        on_delete=models.SET_NULL,
        related_name="invoices",
        null=True,
        blank=True,
    )
    number = models.CharField(max_length=64)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.DRAFT, db_index=True
    )
    subtotal_minor = models.BigIntegerField(default=0)
    discount_minor = models.BigIntegerField(default=0)
    tax_minor = models.BigIntegerField(default=0)
    total_minor = models.BigIntegerField(default=0)
    amount_due_minor = models.BigIntegerField(default=0)
    currency = models.CharField(max_length=3)
    due_at = models.DateTimeField(null=True, blank=True, db_index=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    hosted_payment_url = models.URLField(max_length=2048, blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "invoices_invoice"
        constraints = [
            models.UniqueConstraint(
                fields=["merchant", "environment", "number"],
                name="uniq_invoice_merchant_env_number",
            ),
            models.CheckConstraint(check=Q(subtotal_minor__gte=0), name="invoice_subtotal_nonneg"),
            models.CheckConstraint(check=Q(total_minor__gte=0), name="invoice_total_nonneg"),
        ]
        indexes = [
            models.Index(
                fields=["merchant", "environment", "status", "due_at"],
                name="invoice_scope_status_due_idx",
            ),
            models.Index(
                fields=["merchant", "environment", "subscription"],
                name="invoice_scope_sub_idx",
            ),
        ]


class InvoiceLineItem(BaseDomainModel):
    class Type(models.TextChoices):
        SUBSCRIPTION = "subscription", "Subscription"
        ONE_TIME = "one_time", "One Time"
        SETUP_FEE = "setup_fee", "Setup Fee"
        PRORATION = "proration", "Proration"
        DISCOUNT = "discount", "Discount"
        TAX = "tax", "Tax"
        CREDIT = "credit", "Credit"

    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="line_items")
    type = models.CharField(max_length=20, choices=Type.choices)
    description = models.CharField(max_length=400, blank=True, default="")
    amount_minor = models.BigIntegerField()
    quantity = models.PositiveIntegerField(default=1)
    currency = models.CharField(max_length=3)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "invoices_lineitem"
        ordering = ["created_at"]


class CreditNote(TenantDomainModel):
    class Reason(models.TextChoices):
        REFUND = "refund", "Refund"
        DUPLICATE = "duplicate", "Duplicate Charge"
        FRAUD = "fraud", "Fraud"
        OTHER = "other", "Other"

    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name="credit_notes")
    amount_minor = models.BigIntegerField()
    currency = models.CharField(max_length=3)
    reason = models.CharField(max_length=16, choices=Reason.choices, default=Reason.OTHER)
    note = models.TextField(blank=True, default="")

    class Meta:
        db_table = "invoices_creditnote"
