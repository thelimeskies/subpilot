"""Celery tasks for outbound webhook delivery."""
from __future__ import annotations

from celery import shared_task
from django.db import transaction
from django.utils import timezone


@shared_task(
    name="apps.events.tasks.dispatch_outbound_webhook",
    queue="webhooks",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=3,
)
def dispatch_outbound_webhook(self, delivery_id: str) -> dict:
    """Send a single ``WebhookDelivery`` row.

    Failures are recorded inside :func:`dispatch_delivery` (status FAILED +
    ``next_attempt_at`` scheduled) so this Celery task does not need to raise
    on HTTP errors. The ``autoretry_for`` covers transient programming /
    infrastructure issues only.
    """
    from apps.events.services.dispatch_delivery import dispatch_delivery

    delivery = dispatch_delivery(delivery_id=delivery_id)
    return {
        "delivery_id": str(delivery.id),
        "status": delivery.status,
        "attempt": delivery.attempt_count,
    }


@shared_task(
    name="apps.events.tasks.scan_due_deliveries",
    queue="webhooks",
)
def scan_due_deliveries() -> dict:
    """Pick up FAILED deliveries whose ``next_attempt_at`` has passed."""
    from apps.events.models import WebhookDelivery

    now = timezone.now()
    due_ids: list[str] = []
    with transaction.atomic():
        qs = (
            WebhookDelivery.objects.filter(
                status=WebhookDelivery.Status.FAILED,
                next_attempt_at__lte=now,
            )
            .select_for_update(skip_locked=True)
            .only("id")
            [:500]
        )
        for d in qs:
            due_ids.append(str(d.id))
    for did in due_ids:
        dispatch_outbound_webhook.delay(did)
    return {"due": len(due_ids)}
