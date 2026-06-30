"""Celery tasks for payments.

Routed to the ``payments`` queue per docs/technical/celery-job-contracts.md.
Webhook ingestion (verified payload) routes to ``webhooks``.
"""
from __future__ import annotations

import logging

from celery import shared_task
from django.db import transaction

from apps.common.exceptions import ConflictError, ServiceError

logger = logging.getLogger(__name__)


@shared_task(
    name="apps.payments.tasks.charge_invoice",
    queue="payments",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    max_retries=4,
)
def charge_invoice_task(*, invoice_id: str, payment_method_id: str | None = None,
                         adapter_name: str | None = None) -> dict:
    """Run a charge attempt against an invoice. Idempotent on (invoice, attempt#)."""
    from apps.invoices.models import Invoice
    from apps.customers.models import PaymentMethod

    from .services import charge_invoice

    with transaction.atomic():
        invoice = (
            Invoice.objects.select_for_update(skip_locked=True)
            .filter(id=invoice_id)
            .first()
        )
        if invoice is None:
            return {"skipped": "not_found", "invoice_id": invoice_id}

        pm = None
        if payment_method_id:
            pm = PaymentMethod.objects.filter(id=payment_method_id).first()

        try:
            outcome = charge_invoice(
                invoice=invoice,
                payment_method=pm,
                adapter_name=adapter_name,
            )
        except ConflictError as exc:
            logger.info("charge_invoice_task idempotent skip: %s", exc)
            return {"skipped": "duplicate", "invoice_id": invoice_id}
        except ServiceError as exc:
            logger.warning(
                "charge_invoice_task service error: invoice=%s err=%s",
                invoice_id, exc,
            )
            return {"failed": "service_error", "invoice_id": invoice_id, "error": str(exc)}

    return {
        "invoice_id": invoice_id,
        "attempt_id": str(outcome.attempt.id),
        "success": outcome.result.success,
        "failure_code": outcome.result.failure_code,
        "failure_category": outcome.result.failure_category,
    }


@shared_task(
    name="apps.payments.tasks.process_processor_webhook",
    queue="webhooks",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    max_retries=5,
)
def process_processor_webhook_task(*, merchant_id: str, environment_id: str,
                                    parsed: dict) -> dict:
    """Async wrapper around :func:`process_processor_event`.

    Used when the synchronous webhook view chooses to push processing to the
    background (e.g. heavy events). For the standard path the view processes
    inline so the gateway sees a synchronous 200.
    """
    from apps.accounts.models import Environment, Merchant

    from .services import process_processor_event

    merchant = Merchant.objects.filter(id=merchant_id).first()
    environment = Environment.objects.filter(id=environment_id).first()
    if merchant is None or environment is None:
        return {"skipped": "tenant_not_found"}

    event = process_processor_event(
        merchant=merchant, environment=environment, parsed=parsed
    )
    return {"event_id": str(event.id), "processed": event.processed_at is not None}


# Back-compat aliases referenced by older docs / tests.
charge_invoice_with_nomba = charge_invoice_task
process_nomba_webhook = process_processor_webhook_task
