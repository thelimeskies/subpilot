"""Manually re-emit a previously stored ``WebhookEvent``.

Replay creates fresh PENDING ``WebhookDelivery`` rows for the original event,
one per currently enabled matching endpoint. The original event row is left
unchanged.
"""
from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from apps.audit.services.log_event import log_event
from apps.common.db import atomic_with_retry

from ..models import WebhookDelivery, WebhookEndpoint, WebhookEvent
from .create_event import _endpoint_matches


@atomic_with_retry
def replay_event(*, event: WebhookEvent, actor_user=None, request=None) -> list[WebhookDelivery]:
    """Create new pending deliveries for ``event`` against current endpoints."""
    endpoints = WebhookEndpoint.objects.filter(
        merchant=event.merchant, environment=event.environment, enabled=True
    )
    deliveries: list[WebhookDelivery] = []
    now = timezone.now()
    for endpoint in endpoints:
        if not _endpoint_matches(endpoint, event.event_type):
            continue
        delivery = WebhookDelivery.objects.create(
            webhook_event=event,
            endpoint=endpoint,
            status=WebhookDelivery.Status.PENDING,
            next_attempt_at=now,
        )
        deliveries.append(delivery)

    log_event(
        action="events.event_replayed",
        actor_user=actor_user,
        merchant=event.merchant,
        environment=event.environment,
        target_type="WebhookEvent",
        target_id=str(event.id),
        metadata={
            "event_type": event.event_type,
            "delivery_count": len(deliveries),
        },
        request=request,
    )

    if deliveries:
        try:
            from apps.events.tasks import dispatch_outbound_webhook
        except Exception:  # pragma: no cover
            return deliveries
        for d in deliveries:
            transaction.on_commit(
                lambda did=str(d.id): dispatch_outbound_webhook.delay(did)
            )
    return deliveries
