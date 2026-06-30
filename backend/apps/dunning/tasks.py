"""Celery tasks for dunning.

Routed to the ``dunning`` queue per docs/technical/celery-job-contracts.md.
"""
from __future__ import annotations

import logging

from celery import shared_task
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(name="apps.dunning.tasks.process_due_retries", queue="dunning")
def process_due_retries() -> dict:
    """Scan for active dunning runs whose ``next_retry_at`` <= now and retry.

    For each due run, fan out a charge attempt to the ``payments`` queue.
    Idempotent: enqueueing a duplicate charge is safe (uniqueness on
    ``(invoice, attempt_number)`` and on ``idempotency_key``).
    """
    from apps.payments.tasks import charge_invoice_task

    from .models import DunningRun

    now = timezone.now()
    due = DunningRun.objects.filter(
        status=DunningRun.Status.ACTIVE,
        next_retry_at__lte=now,
    ).values_list("id", "invoice_id")

    enqueued = 0
    for _run_id, invoice_id in list(due):
        charge_invoice_task.apply_async(
            kwargs={"invoice_id": str(invoice_id)},
            queue="payments",
        )
        enqueued += 1
        # Defer the next retry until the attempt finishes - the post-charge
        # task ``record_attempt_outcome_task`` flips next_retry_at.

    logger.info("dunning.process_due_retries enqueued=%s now=%s", enqueued, now.isoformat())
    return {"enqueued": enqueued, "scanned_at": now.isoformat()}


@shared_task(name="apps.dunning.tasks.start_for_failed_invoice", queue="dunning")
def start_for_failed_invoice(*, invoice_id: str, failure_code: str = "") -> dict:
    """Open a dunning run for a recently failed charge."""
    from apps.invoices.models import Invoice

    from .services import start_dunning_run

    with transaction.atomic():
        invoice = Invoice.objects.filter(id=invoice_id).first()
        if invoice is None:
            return {"skipped": "invoice_not_found"}
        run = start_dunning_run(invoice=invoice, failure_code=failure_code)
    return {"run_id": str(run.id), "status": run.status}


@shared_task(name="apps.dunning.tasks.record_attempt_outcome", queue="dunning")
def record_attempt_outcome_task(
    *, run_id: str, success: bool, failure_code: str = ""
) -> dict:
    """Advance a dunning run's state machine after a retry attempt finished."""
    from .models import DunningRun
    from .services import record_attempt_outcome

    with transaction.atomic():
        run = (
            DunningRun.objects.select_for_update(skip_locked=True)
            .filter(id=run_id)
            .first()
        )
        if run is None:
            return {"skipped": "not_found"}
        run = record_attempt_outcome(
            run=run, success=success, failure_code=failure_code
        )
    return {"run_id": str(run.id), "status": run.status}


# Back-compat alias.
apply_final_action = record_attempt_outcome_task


@shared_task(name="apps.dunning.tasks.send_recovery_notification", queue="notifications")
def send_recovery_notification_task(*, run_id: str) -> dict:
    """Send the branded customer recovery email for a dunning run."""
    from .models import DunningRun
    from .services import send_recovery_notification

    run = DunningRun.objects.filter(id=run_id).first()
    if run is None:
        return {"skipped": "not_found", "run_id": run_id}
    log = send_recovery_notification(run=run)
    if log is None:
        return {"skipped": "email_disabled", "run_id": run_id}
    return {
        "run_id": run_id,
        "notification_id": str(log.id),
        "status": log.status,
        "template_key": log.template_key,
    }
