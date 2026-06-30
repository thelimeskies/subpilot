"""Create a ``WebhookEvent`` and fan out pending deliveries.

Called from domain service layers (subscriptions, invoices, payments, dunning)
right after a state change. Side-effect free of HTTP — actual delivery is
done asynchronously by :func:`apps.events.tasks.dispatch_outbound_webhook`.
"""
from __future__ import annotations

from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.audit.services.log_event import log_event
from apps.common.db import atomic_with_retry

from ..models import WebhookDelivery, WebhookEndpoint, WebhookEvent


def _endpoint_matches(endpoint: WebhookEndpoint, event_type: str) -> bool:
    filters = endpoint.event_filters or []
    if not filters:
        return True
    for pattern in filters:
        if pattern == event_type:
            return True
        if pattern.endswith(".*") and event_type.startswith(pattern[:-1]):
            return True
        if pattern == "*":
            return True
    return False


@atomic_with_retry
def create_event(
    *,
    merchant,
    environment,
    event_type: str,
    payload: dict[str, Any] | None = None,
    aggregate_type: str = "",
    aggregate_id: str = "",
    actor_user=None,
    request=None,
) -> WebhookEvent:
    """Persist a :class:`WebhookEvent` and queue deliveries for matching endpoints."""
    event = WebhookEvent.objects.create(
        merchant=merchant,
        environment=environment,
        event_type=event_type,
        aggregate_type=aggregate_type,
        aggregate_id=str(aggregate_id) if aggregate_id else "",
        payload=payload or {},
    )

    endpoints = WebhookEndpoint.objects.filter(
        merchant=merchant, environment=environment, enabled=True
    )
    pending_delivery_ids: list[str] = []
    now = timezone.now()
    for endpoint in endpoints:
        if not _endpoint_matches(endpoint, event_type):
            continue
        delivery = WebhookDelivery.objects.create(
            webhook_event=event,
            endpoint=endpoint,
            status=WebhookDelivery.Status.PENDING,
            next_attempt_at=now,
        )
        pending_delivery_ids.append(str(delivery.id))

    log_event(
        action="events.event_created",
        actor_user=actor_user,
        merchant=merchant,
        environment=environment,
        target_type="WebhookEvent",
        target_id=str(event.id),
        metadata={
            "event_type": event_type,
            "aggregate_type": aggregate_type,
            "aggregate_id": str(aggregate_id) if aggregate_id else "",
            "delivery_count": len(pending_delivery_ids),
        },
        request=request,
    )

    if pending_delivery_ids:
        # Queue dispatch after commit so workers don't see uncommitted rows.
        try:
            from apps.events.tasks import dispatch_outbound_webhook
        except Exception:  # pragma: no cover - defensive
            return event
        for delivery_id in pending_delivery_ids:
            transaction.on_commit(
                lambda did=delivery_id: dispatch_outbound_webhook.delay(did)
            )
    return event


def emit(
    *,
    merchant,
    environment,
    event_type: str,
    payload: dict[str, Any] | None = None,
    aggregate_type: str = "",
    aggregate_id: str = "",
    actor_user=None,
    request=None,
) -> WebhookEvent | None:
    """Best-effort wrapper used by domain services.

    Domain services must never fail because the event bus failed; they emit
    via this helper so any unexpected error becomes a no-op (the event will
    be missing but the primary mutation still completes).
    """
    try:
        return create_event(
            merchant=merchant,
            environment=environment,
            event_type=event_type,
            payload=payload,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            actor_user=actor_user,
            request=request,
        )
    except Exception:  # pragma: no cover - defensive
        return None
