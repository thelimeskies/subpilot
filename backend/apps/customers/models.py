"""Customers domain: Customer, PaymentMethod, PortalSession.

Token references (`PaymentMethod.token_encrypted`) are encrypted at rest using
:mod:`apps.common.crypto`. The API layer (serializers in
``apps/customers/serializers.py``) MUST NOT expose the token.
"""
from __future__ import annotations

from django.db import models
from django.db.models import Q

from apps.common.crypto import decrypt, encrypt
from apps.common.models import TenantDomainModel


class Customer(TenantDomainModel):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        ARCHIVED = "archived", "Archived"

    external_id = models.CharField(max_length=128, blank=True, default="")
    email = models.EmailField(db_index=True)
    name = models.CharField(max_length=200, blank=True, default="")
    phone = models.CharField(max_length=32, blank=True, default="")
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.ACTIVE, db_index=True
    )
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "customers_customer"
        constraints = [
            models.UniqueConstraint(
                fields=["merchant", "environment", "external_id"],
                condition=~Q(external_id=""),
                name="uniq_customer_external_id_per_env",
            ),
        ]
        indexes = [
            models.Index(
                fields=["merchant", "environment", "email"], name="customer_scope_email_idx"
            ),
            models.Index(
                fields=["merchant", "environment", "status"], name="customer_scope_status_idx"
            ),
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.name or self.email}"


class PaymentMethod(TenantDomainModel):
    class Provider(models.TextChoices):
        NOMBA = "nomba", "Nomba"
        MOCK = "mock", "Mock (demo)"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        EXPIRED = "expired", "Expired"
        REVOKED = "revoked", "Revoked"

    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="payment_methods"
    )
    provider = models.CharField(max_length=16, choices=Provider.choices, default=Provider.NOMBA)
    token_encrypted = models.CharField(max_length=512, blank=True, default="")
    brand = models.CharField(max_length=32, blank=True, default="")
    last4 = models.CharField(max_length=4, blank=True, default="")
    exp_month = models.PositiveSmallIntegerField(null=True, blank=True)
    exp_year = models.PositiveSmallIntegerField(null=True, blank=True)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.ACTIVE, db_index=True
    )
    is_default = models.BooleanField(default=False)
    fingerprint = models.CharField(max_length=128, blank=True, default="", db_index=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "customers_paymentmethod"
        constraints = [
            # At most one default *active* payment method per customer.
            models.UniqueConstraint(
                fields=["customer"],
                condition=Q(is_default=True) & Q(status="active"),
                name="uniq_default_active_pm_per_customer",
            ),
        ]
        indexes = [
            models.Index(
                fields=["merchant", "environment", "customer", "status"],
                name="pm_scope_status_idx",
            ),
        ]

    # --- Encrypted token convenience accessors -------------------------------
    @property
    def token(self) -> str:
        return decrypt(self.token_encrypted)

    @token.setter
    def token(self, value: str) -> None:
        self.token_encrypted = encrypt(value) if value else ""

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.brand} •••• {self.last4} ({self.status})"


class PortalSession(TenantDomainModel):
    """Signed, scoped, expiring customer portal access token.

    The plaintext token is shown to the requester once at creation time; only
    the SHA-256 hash is persisted (see :func:`apps.common.crypto.hash_secret`).
    """

    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="portal_sessions"
    )
    subscription = models.ForeignKey(
        "subscriptions.Subscription",
        on_delete=models.SET_NULL,
        related_name="portal_sessions",
        null=True,
        blank=True,
    )
    invoice = models.ForeignKey(
        "invoices.Invoice",
        on_delete=models.SET_NULL,
        related_name="portal_sessions",
        null=True,
        blank=True,
    )
    token_hash = models.CharField(max_length=128, unique=True)
    allowed_actions = models.JSONField(default=list, blank=True)
    return_url = models.URLField(max_length=500, blank=True, default="")
    expires_at = models.DateTimeField(db_index=True)
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "customers_portalsession"
        indexes = [
            models.Index(fields=["merchant", "environment", "customer"], name="ps_scope_customer_idx"),
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"PortalSession(customer={self.customer_id}, expires={self.expires_at})"
