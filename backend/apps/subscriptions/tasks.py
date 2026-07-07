"""Celery tasks for the subscriptions app.

Routed to the ``billing`` queue per docs/technical/celery-job-contracts.md.
"""
from __future__ import annotations

import logging

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from .models import Subscription
from .services.lifecycle import cancel_subscription

logger = logging.getLogger(__name__)


@shared_task(name="apps.subscriptions.tasks.scan_due_subscriptions", queue="billing")
def scan_due_subscriptions() -> dict:
    """Scheduled scan that fans out renewal jobs and end-of-period cancellations.

    Runs every 15 minutes per ``config.celery.beat_schedule``. It:
    1. Finds subscriptions whose ``current_period_end`` <= now and either
       active or trialing -> queues a renewal-invoice creation.
    2. Cancels subscriptions whose ``cancel_at_period_end`` is True and whose
       period has ended.
    """
    now = timezone.now()
    due_qs = Subscription.objects.filter(
        status__in=[Subscription.Status.ACTIVE, Subscription.Status.TRIALING],
        current_period_end__lte=now,
    ).values_list("id", flat=True)
    cancel_qs = Subscription.objects.filter(
        cancel_at_period_end=True,
        current_period_end__lte=now,
        status__in=[
            Subscription.Status.ACTIVE,
            Subscription.Status.TRIALING,
            Subscription.Status.PAST_DUE,
        ],
    ).values_list("id", flat=True)

    enqueued = 0
    for sub_id in due_qs:
        renew_subscription.apply_async(
            kwargs={"subscription_id": str(sub_id)},
            queue="billing",
        )
        enqueued += 1

    canceled = 0
    for sub_id in list(cancel_qs):
        finalize_period_end_cancellation.apply_async(
            kwargs={"subscription_id": str(sub_id)},
            queue="billing",
        )
        canceled += 1

    logger.info(
        "scan_due_subscriptions: enqueued=%s canceled=%s now=%s",
        enqueued, canceled, now.isoformat(),
    )
    return {"enqueued": enqueued, "canceled": canceled, "scanned_at": now.isoformat()}


@shared_task(
    name="apps.subscriptions.tasks.renew_subscription",
    queue="billing",
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=5,
)
def renew_subscription(*, subscription_id: str) -> dict:
    """Generate the next invoice for a single subscription. Idempotent."""
    from apps.common.exceptions import ConflictError
    from apps.invoices.services.create_renewal_invoice import create_renewal_invoice
    from apps.payments.services import charge_invoice

    with transaction.atomic():
        sub = (
            Subscription.objects.select_for_update(skip_locked=True)
            .filter(id=subscription_id)
            .first()
        )
        if sub is None:
            return {"skipped": "not_found", "subscription_id": subscription_id}
        try:
            invoice = create_renewal_invoice(subscription=sub)
        except ConflictError as e:
            logger.info("renew_subscription idempotent skip: %s", e)
            return {"skipped": "duplicate", "subscription_id": subscription_id}
    payment_method = sub.default_payment_method
    if payment_method is not None and payment_method.token:
        outcome = charge_invoice(
            invoice=invoice,
            payment_method=payment_method,
        )
        return {
            "invoice_id": str(invoice.id),
            "number": invoice.number,
            "attempt_id": str(outcome.attempt.id),
            "charged": True,
            "success": outcome.result.success,
        }
    return {
        "invoice_id": str(invoice.id),
        "number": invoice.number,
        "charged": False,
        "skipped_charge": "missing_tokenized_payment_method",
    }


@shared_task(
    name="apps.subscriptions.tasks.finalize_period_end_cancellation",
    queue="billing",
)
def finalize_period_end_cancellation(*, subscription_id: str) -> dict:
    """Flip ``cancel_at_period_end`` subscriptions to canceled after period end."""
    sub = Subscription.objects.filter(id=subscription_id).first()
    if sub is None:
        return {"skipped": "not_found"}
    if not sub.cancel_at_period_end:
        return {"skipped": "no_pending_cancel"}
    cancel_subscription(subscription=sub, at_period_end=False, reason="period_end")
    return {"subscription_id": subscription_id, "status": sub.status}
