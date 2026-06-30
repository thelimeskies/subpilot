"""HTTP dispatch + retry scheduling for ``WebhookDelivery`` rows."""
from __future__ import annotations

import json
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.audit.services.log_event import log_event
from apps.common.db import atomic_with_retry

from ..models import WebhookDelivery
from .sign_payload import sign_payload


# Backoff schedule (minutes from now), index = attempt count just completed.
_RETRY_BACKOFF_MIN: list[int] = [1, 5, 15, 60, 240, 720]
MAX_DELIVERY_ATTEMPTS = len(_RETRY_BACKOFF_MIN) + 1  # 7 attempts total


def _build_envelope(delivery: WebhookDelivery) -> dict:
    event = delivery.webhook_event
    livemode = (getattr(event.environment, "mode", "") == "live")
    return {
        "id": f"evt_{event.id}",
        "type": event.event_type,
        "livemode": livemode,
        "merchant_id": str(event.merchant_id),
        "occurred_at": event.occurred_at.isoformat(),
        "data": event.payload or {},
    }


def _next_attempt_at(attempt_count: int):
    if attempt_count <= 0 or attempt_count > len(_RETRY_BACKOFF_MIN):
        return None
    return timezone.now() + timedelta(minutes=_RETRY_BACKOFF_MIN[attempt_count - 1])


@atomic_with_retry
def dispatch_delivery(*, delivery_id: str, request=None) -> WebhookDelivery:
    """Send one delivery attempt over HTTP and update the row.

    The HTTP layer is imported lazily so unit tests can stub it. On success
    the delivery is marked DELIVERED. On 4xx/5xx or transport failure it is
    marked FAILED and ``next_attempt_at`` is scheduled per the backoff
    table; once ``MAX_DELIVERY_ATTEMPTS`` is reached the delivery is
    abandoned.
    """
    qs = WebhookDelivery.objects.select_for_update().select_related(
        "webhook_event__merchant", "webhook_event__environment", "endpoint"
    )
    delivery = qs.get(pk=delivery_id)
    if delivery.status == WebhookDelivery.Status.DELIVERED:
        return delivery
    if delivery.status == WebhookDelivery.Status.ABANDONED:
        return delivery

    envelope = _build_envelope(delivery)
    raw_body = json.dumps(envelope, separators=(",", ":"), sort_keys=True)
    timestamp = timezone.now().isoformat()
    headers = sign_payload(
        event_id=envelope["id"],
        secret=delivery.endpoint.secret or "",
        timestamp=timestamp,
        raw_body=raw_body,
    ).as_http()

    delivery.attempt_count += 1
    success = False
    status_code: int | None = None
    body_excerpt = ""
    try:
        import requests  # type: ignore

        resp = requests.post(
            delivery.endpoint.url,
            data=raw_body,
            headers=headers,
            timeout=10,
        )
        status_code = resp.status_code
        body_excerpt = (resp.text or "")[:1000]
        success = 200 <= status_code < 300
    except Exception as exc:  # pragma: no cover - network errors
        body_excerpt = f"transport_error: {exc!s}"[:1000]
        success = False

    delivery.last_status_code = status_code
    delivery.last_response_body = body_excerpt

    if success:
        delivery.status = WebhookDelivery.Status.DELIVERED
        delivery.delivered_at = timezone.now()
        delivery.next_attempt_at = None
        log_event(
            action="events.delivery_succeeded",
            merchant=delivery.webhook_event.merchant,
            environment=delivery.webhook_event.environment,
            target_type="WebhookDelivery",
            target_id=str(delivery.id),
            metadata={"status_code": status_code, "attempt": delivery.attempt_count},
            request=request,
        )
    else:
        if delivery.attempt_count >= MAX_DELIVERY_ATTEMPTS:
            delivery.status = WebhookDelivery.Status.ABANDONED
            delivery.next_attempt_at = None
            log_event(
                action="events.delivery_abandoned",
                merchant=delivery.webhook_event.merchant,
                environment=delivery.webhook_event.environment,
                target_type="WebhookDelivery",
                target_id=str(delivery.id),
                metadata={
                    "status_code": status_code,
                    "attempt": delivery.attempt_count,
                },
                request=request,
            )
        else:
            delivery.status = WebhookDelivery.Status.FAILED
            delivery.next_attempt_at = _next_attempt_at(delivery.attempt_count)
            log_event(
                action="events.delivery_failed",
                merchant=delivery.webhook_event.merchant,
                environment=delivery.webhook_event.environment,
                target_type="WebhookDelivery",
                target_id=str(delivery.id),
                metadata={
                    "status_code": status_code,
                    "attempt": delivery.attempt_count,
                    "next_attempt_at": (
                        delivery.next_attempt_at.isoformat()
                        if delivery.next_attempt_at
                        else None
                    ),
                },
                request=request,
            )

    delivery.save(
        update_fields=[
            "attempt_count",
            "status",
            "last_status_code",
            "last_response_body",
            "next_attempt_at",
            "delivered_at",
            "updated_at",
        ]
    )
    return delivery


def retry_delivery(*, delivery: WebhookDelivery, request=None) -> WebhookDelivery:
    """Reset a failed delivery for an immediate retry attempt."""
    if delivery.status not in {
        WebhookDelivery.Status.FAILED,
        WebhookDelivery.Status.ABANDONED,
    }:
        return delivery
    delivery.status = WebhookDelivery.Status.PENDING
    delivery.next_attempt_at = timezone.now()
    delivery.save(update_fields=["status", "next_attempt_at", "updated_at"])
    log_event(
        action="events.delivery_retry_scheduled",
        merchant=delivery.webhook_event.merchant,
        environment=delivery.webhook_event.environment,
        target_type="WebhookDelivery",
        target_id=str(delivery.id),
        metadata={"manual": True},
        request=request,
    )
    return delivery
