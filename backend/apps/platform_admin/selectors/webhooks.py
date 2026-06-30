"""Cross-tenant Webhooks selector for the platform admin (S6).

Maps :class:`apps.events.models.WebhookDelivery` rows onto the FE
``WebhookDelivery`` shape declared in
[seed.ts](file:///Users/mac/Desktop/Projects/HackathonxNomba/apps/subpilot-admin/src/data/seed.ts#L206-L215).

Internal → FE status mapping:
    delivered  → "Delivered"
    pending    → "Retrying"   (queued for next attempt)
    failed     → "Retrying"   (next_attempt_at scheduled, will retry)
    abandoned  → "Failed"     (gave up after max attempts)
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import Iterable

from django.db.models import Count, Q
from django.utils import timezone

from apps.events.models import WebhookDelivery


# --- Status mapping --------------------------------------------------------


_FE_DELIVERED = "Delivered"
_FE_RETRYING = "Retrying"
_FE_FAILED = "Failed"


def _derive_fe_status(delivery: WebhookDelivery) -> str:
    if delivery.status == WebhookDelivery.Status.DELIVERED:
        return _FE_DELIVERED
    if delivery.status == WebhookDelivery.Status.ABANDONED:
        return _FE_FAILED
    return _FE_RETRYING  # pending / failed → queued / scheduled to retry


_FE_TO_INTERNAL = {
    "delivered": [WebhookDelivery.Status.DELIVERED],
    "retrying": [WebhookDelivery.Status.PENDING, WebhookDelivery.Status.FAILED],
    "failed": [WebhookDelivery.Status.ABANDONED],
}


# --- Helpers ---------------------------------------------------------------


def _short_id(value, prefix: str) -> str:
    raw = str(value).replace("-", "")
    return f"{prefix}_{raw[:12].upper()}"


def _last_attempt_at(delivery: WebhookDelivery) -> str:
    """Pick the most relevant timestamp for the FE's ``lastAttempt`` field."""
    if delivery.delivered_at:
        return delivery.delivered_at.isoformat()
    if delivery.attempt_count > 0:
        # ``updated_at`` is bumped by ``dispatch_delivery``; falls back to created.
        return (delivery.updated_at or delivery.created_at).isoformat()
    return delivery.created_at.isoformat() if delivery.created_at else ""


# --- Public API ------------------------------------------------------------


@dataclass(frozen=True)
class DeliveryListItem:
    id: str
    raw_id: str
    merchant_id: str
    merchant: str
    event: str
    event_id: str
    endpoint: str
    endpoint_id: str
    status: str
    raw_status: str
    attempts: int
    last_attempt: str
    next_attempt_at: str | None
    response_code: int
    response_body_excerpt: str

    def as_dict(self) -> dict:
        return asdict(self)


def list_deliveries_cross_tenant(
    *,
    status: str | None = None,
    merchant_id: str | None = None,
    event_type: str | None = None,
    endpoint_id: str | None = None,
    q: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = 25,
    offset: int = 0,
) -> tuple[list[DeliveryListItem], int]:
    """Cross-tenant paginated deliveries list. Returns ``(rows, total)``."""
    qs = (
        WebhookDelivery.objects.select_related(
            "webhook_event",
            "webhook_event__merchant",
            "webhook_event__environment",
            "endpoint",
        ).order_by("-created_at")
    )

    fe_status = (status or "").strip().lower()
    if fe_status and fe_status not in {"all", ""}:
        internal = _FE_TO_INTERNAL.get(fe_status)
        if internal:
            qs = qs.filter(status__in=internal)
        else:
            qs = qs.filter(status=fe_status)

    if merchant_id:
        qs = qs.filter(webhook_event__merchant_id=merchant_id)

    if event_type:
        qs = qs.filter(webhook_event__event_type=event_type)

    if endpoint_id:
        qs = qs.filter(endpoint_id=endpoint_id)

    if date_from is not None:
        qs = qs.filter(created_at__gte=date_from)
    if date_to is not None:
        qs = qs.filter(created_at__lte=date_to)

    if q:
        needle = q.strip()
        if needle:
            qs = qs.filter(
                Q(webhook_event__event_type__icontains=needle)
                | Q(webhook_event__merchant__name__icontains=needle)
                | Q(endpoint__url__icontains=needle)
            )

    total = qs.count()

    rows: list[DeliveryListItem] = []
    page = qs[offset : offset + limit]
    for d in page:
        event = d.webhook_event
        merchant = getattr(event, "merchant", None)
        endpoint = d.endpoint
        rows.append(
            DeliveryListItem(
                id=_short_id(d.id, "evt"),
                raw_id=str(d.id),
                merchant_id=str(merchant.id) if merchant else "",
                merchant=getattr(merchant, "name", "") or "—",
                event=getattr(event, "event_type", "") or "",
                event_id=str(event.id) if event else "",
                endpoint=getattr(endpoint, "url", "") or "",
                endpoint_id=str(endpoint.id) if endpoint else "",
                status=_derive_fe_status(d),
                raw_status=d.status,
                attempts=int(d.attempt_count or 0),
                last_attempt=_last_attempt_at(d),
                next_attempt_at=(
                    d.next_attempt_at.isoformat() if d.next_attempt_at else None
                ),
                response_code=int(d.last_status_code or 0),
                response_body_excerpt=(d.last_response_body or "")[:280],
            )
        )

    return rows, total


def get_delivery(delivery_id) -> WebhookDelivery | None:
    """Cross-tenant lookup. Returns ``None`` if missing or invalid id."""
    try:
        return (
            WebhookDelivery.objects.select_related(
                "webhook_event__merchant",
                "webhook_event__environment",
                "endpoint",
            )
            .get(pk=delivery_id)
        )
    except (WebhookDelivery.DoesNotExist, ValueError):
        return None


def project_delivery(item: DeliveryListItem) -> dict:
    """Map an internal :class:`DeliveryListItem` to the FE WebhookDelivery dict."""
    return {
        "id": item.id,
        "rawId": item.raw_id,
        "merchantId": item.merchant_id,
        "merchant": item.merchant,
        "event": item.event,
        "eventId": item.event_id,
        "endpoint": item.endpoint,
        "endpointId": item.endpoint_id,
        "status": item.status,
        "rawStatus": item.raw_status,
        "attempts": item.attempts,
        "lastAttempt": item.last_attempt,
        "nextAttemptAt": item.next_attempt_at,
        "responseCode": item.response_code,
        "responseBodyExcerpt": item.response_body_excerpt,
    }


# --- Aggregate health ------------------------------------------------------


def aggregate_health(*, window_hours: int = 24) -> dict:
    """Return a small dict with counts by status for the last ``window_hours``.

    Shape:
        {
          "windowHours": 24,
          "delivered": int,
          "retrying": int,
          "failed": int,
          "total": int,
          "successRate": float,  # percentage 0-100
        }
    """
    since = timezone.now() - timedelta(hours=int(window_hours))
    qs = WebhookDelivery.objects.filter(created_at__gte=since)
    counts = qs.aggregate(
        delivered=Count("id", filter=Q(status=WebhookDelivery.Status.DELIVERED)),
        pending=Count("id", filter=Q(status=WebhookDelivery.Status.PENDING)),
        failed=Count("id", filter=Q(status=WebhookDelivery.Status.FAILED)),
        abandoned=Count("id", filter=Q(status=WebhookDelivery.Status.ABANDONED)),
        total=Count("id"),
    )
    delivered = int(counts.get("delivered") or 0)
    retrying = int(counts.get("pending") or 0) + int(counts.get("failed") or 0)
    failed = int(counts.get("abandoned") or 0)
    total = int(counts.get("total") or 0)
    success_rate = round((delivered / total) * 100, 1) if total else 0.0
    return {
        "windowHours": int(window_hours),
        "delivered": delivered,
        "retrying": retrying,
        "failed": failed,
        "total": total,
        "successRate": success_rate,
    }


__all__ = [
    "DeliveryListItem",
    "list_deliveries_cross_tenant",
    "get_delivery",
    "project_delivery",
    "aggregate_health",
]
