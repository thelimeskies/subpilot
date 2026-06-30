"""Payments domain models.

Adapter logic + services land in Sprint 2 per
docs/delivery/django-file-by-file-build-plan.md.
"""
from __future__ import annotations

from django.db import models

from apps.common.models import TenantDomainModel


class PaymentAttempt(TenantDomainModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"
        ABANDONED = "abandoned", "Abandoned"

    invoice = models.ForeignKey(
        "invoices.Invoice", on_delete=models.PROTECT, related_name="payment_attempts"
    )
    payment_method = models.ForeignKey(
        "customers.PaymentMethod",
        on_delete=models.SET_NULL,
        related_name="payment_attempts",
        null=True,
        blank=True,
    )
    attempt_number = models.PositiveIntegerField(default=1)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    amount_minor = models.BigIntegerField()
    currency = models.CharField(max_length=3)
    failure_code = models.CharField(max_length=64, blank=True, default="")
    failure_message = models.CharField(max_length=400, blank=True, default="")
    processor_reference = models.CharField(max_length=128, blank=True, default="", db_index=True)
    idempotency_key = models.CharField(max_length=128, blank=True, default="")
    next_retry_at = models.DateTimeField(null=True, blank=True, db_index=True)
    # Free-form metadata. S13 stamps ``routing_policy`` here based on the
    # ``smart_routing`` feature flag - currently a hint only (single adapter
    # today), reserved for the upcoming multi-adapter routing work.
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "payments_paymentattempt"
        constraints = [
            models.UniqueConstraint(
                fields=["invoice", "attempt_number"],
                name="uniq_paymentattempt_invoice_number",
            ),
            models.UniqueConstraint(
                fields=["merchant", "environment", "idempotency_key"],
                condition=~models.Q(idempotency_key=""),
                name="uniq_paymentattempt_idempotency",
            ),
        ]
        indexes = [
            models.Index(
                fields=["merchant", "environment", "status", "next_retry_at"],
                name="pa_scope_status_retry_idx",
            ),
        ]


class BalanceTransaction(TenantDomainModel):
    """Immutable signed money movement for revenue reporting.

    Positive amounts increase collected balance. Negative amounts reduce it.
    Credits are tracked separately from cash refunds so revenue reporting can
    distinguish cash collected from receivables adjustments.
    """

    class Type(models.TextChoices):
        CHARGE = "charge", "Charge"
        REFUND = "refund", "Refund"
        CREDIT = "credit", "Credit"
        ADJUSTMENT = "adjustment", "Adjustment"

    type = models.CharField(max_length=16, choices=Type.choices, db_index=True)
    signed_amount_minor = models.BigIntegerField()
    currency = models.CharField(max_length=3)
    invoice = models.ForeignKey(
        "invoices.Invoice",
        on_delete=models.PROTECT,
        related_name="balance_transactions",
    )
    payment_attempt = models.ForeignKey(
        PaymentAttempt,
        on_delete=models.SET_NULL,
        related_name="balance_transactions",
        null=True,
        blank=True,
    )
    credit_note = models.ForeignKey(
        "invoices.CreditNote",
        on_delete=models.SET_NULL,
        related_name="balance_transactions",
        null=True,
        blank=True,
    )
    processor_reference = models.CharField(max_length=128, blank=True, default="", db_index=True)
    idempotency_key = models.CharField(max_length=160, blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "payments_balancetransaction"
        constraints = [
            models.CheckConstraint(
                check=~models.Q(signed_amount_minor=0),
                name="bt_signed_amount_nonzero",
            ),
            models.UniqueConstraint(
                fields=["merchant", "environment", "idempotency_key"],
                condition=~models.Q(idempotency_key=""),
                name="uniq_bt_scope_idempotency",
            ),
        ]
        indexes = [
            models.Index(
                fields=["merchant", "environment", "created_at"],
                name="bt_scope_created_idx",
            ),
            models.Index(
                fields=["merchant", "environment", "type", "created_at"],
                name="bt_scope_type_created_idx",
            ),
        ]


class ProcessorEvent(TenantDomainModel):
    class Provider(models.TextChoices):
        NOMBA = "nomba", "Nomba"
        MOCK = "mock", "Mock"

    provider = models.CharField(max_length=16, choices=Provider.choices, default=Provider.NOMBA)
    provider_event_id = models.CharField(max_length=128)
    processor_reference = models.CharField(max_length=128, blank=True, default="", db_index=True)
    event_type = models.CharField(max_length=64, db_index=True)
    payload = models.JSONField(default=dict, blank=True)
    received_at = models.DateTimeField(auto_now_add=True, db_index=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "payments_processorevent"
        constraints = [
            models.UniqueConstraint(
                fields=["merchant", "environment", "provider", "provider_event_id"],
                name="uniq_processorevent_scope_provider_id",
            ),
        ]
