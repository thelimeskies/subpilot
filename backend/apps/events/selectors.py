"""Read-side helpers for events queries."""
from __future__ import annotations

from django.db.models import QuerySet

from .models import WebhookDelivery, WebhookEndpoint, WebhookEvent


def list_events(*, merchant, environment, event_type: str | None = None) -> QuerySet[WebhookEvent]:
    qs = WebhookEvent.objects.filter(merchant=merchant, environment=environment)
    if event_type:
        qs = qs.filter(event_type=event_type)
    return qs.order_by("-occurred_at")


def list_endpoints(*, merchant, environment) -> QuerySet[WebhookEndpoint]:
    return WebhookEndpoint.objects.filter(
        merchant=merchant, environment=environment
    ).order_by("-created_at")


def list_deliveries(*, merchant, environment, event_id=None) -> QuerySet[WebhookDelivery]:
    qs = WebhookDelivery.objects.filter(
        webhook_event__merchant=merchant, webhook_event__environment=environment
    )
    if event_id:
        qs = qs.filter(webhook_event_id=event_id)
    return qs.select_related("webhook_event", "endpoint").order_by("-created_at")
