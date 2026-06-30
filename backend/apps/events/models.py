"""Events / outbound webhooks domain.

Signature, dispatch, retry, replay services land in Sprint 4 per
docs/delivery/django-file-by-file-build-plan.md.
"""
from __future__ import annotations

from django.db import models

from apps.common.crypto import decrypt, encrypt
from apps.common.models import BaseDomainModel, TenantDomainModel


class WebhookEndpoint(TenantDomainModel):
    url = models.URLField(max_length=500)
    description = models.CharField(max_length=400, blank=True, default="")
    enabled = models.BooleanField(default=True, db_index=True)
    secret_encrypted = models.CharField(max_length=512, blank=True, default="")
    event_filters = models.JSONField(default=list, blank=True)

    class Meta:
        db_table = "events_webhookendpoint"
        indexes = [
            models.Index(
                fields=["merchant", "environment", "enabled"],
                name="wh_endpoint_scope_enabled_idx",
            ),
        ]

    @property
    def secret(self) -> str:
        return decrypt(self.secret_encrypted)

    @secret.setter
    def secret(self, value: str) -> None:
        self.secret_encrypted = encrypt(value) if value else ""


class WebhookEvent(TenantDomainModel):
    event_type = models.CharField(max_length=64, db_index=True)
    aggregate_type = models.CharField(max_length=64, blank=True, default="")
    aggregate_id = models.CharField(max_length=128, blank=True, default="")
    payload = models.JSONField(default=dict, blank=True)
    occurred_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "events_webhookevent"
        indexes = [
            models.Index(
                fields=["merchant", "environment", "event_type", "occurred_at"],
                name="webhookevent_scope_type_at_idx",
            ),
        ]


class WebhookDelivery(BaseDomainModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        DELIVERED = "delivered", "Delivered"
        FAILED = "failed", "Failed"
        ABANDONED = "abandoned", "Abandoned"

    webhook_event = models.ForeignKey(
        WebhookEvent, on_delete=models.CASCADE, related_name="deliveries"
    )
    endpoint = models.ForeignKey(
        WebhookEndpoint, on_delete=models.CASCADE, related_name="deliveries"
    )
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    attempt_count = models.PositiveIntegerField(default=0)
    last_status_code = models.IntegerField(null=True, blank=True)
    last_response_body = models.TextField(blank=True, default="")
    next_attempt_at = models.DateTimeField(null=True, blank=True, db_index=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "events_webhookdelivery"
        indexes = [
            models.Index(
                fields=["status", "next_attempt_at"], name="delivery_status_nextat_idx"
            ),
        ]
