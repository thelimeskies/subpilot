"""Charge an invoice through a payment adapter.

Creates / locks a :class:`PaymentAttempt` row, calls the configured adapter,
records the outcome, and (on success) marks the invoice paid via
:func:`apps.invoices.services.lifecycle.mark_paid`. On failure the result
includes a normalized failure category that the dunning engine consumes.
"""
from __future__ import annotations

from dataclasses import dataclass

from apps.audit.services.log_event import log_event
from apps.common.db import atomic_with_retry
from apps.common.exceptions import ConflictError, ServiceError
from apps.customers.models import PaymentMethod
from apps.events.services.create_event import emit as _emit_event
from apps.invoices.models import Invoice
from apps.invoices.services.lifecycle import mark_paid
from apps.platform_admin.feature_flags import get_flag

from ..adapters import ChargeResult, get_adapter
from ..models import PaymentAttempt
from .ledger import record_charge_transaction


@dataclass
class ChargeOutcome:
    attempt: PaymentAttempt
    result: ChargeResult


def _next_attempt_number(invoice: Invoice) -> int:
    last = (
        PaymentAttempt.objects.filter(invoice=invoice)
        .order_by("-attempt_number")
        .values_list("attempt_number", flat=True)
        .first()
    )
    return (last or 0) + 1


def _resolve_payment_method(
    invoice: Invoice, payment_method: PaymentMethod | None
) -> PaymentMethod:
    if payment_method is not None:
        if payment_method.customer_id != invoice.customer_id:
            raise ServiceError("Payment method does not belong to this customer.")
        return payment_method
    pm = (
        PaymentMethod.objects.filter(
            customer=invoice.customer,
            status=PaymentMethod.Status.ACTIVE,
            is_default=True,
        )
        .order_by("-created_at")
        .first()
    )
    if pm is None:
        raise ServiceError("Customer has no active default payment method.")
    return pm


@atomic_with_retry
def charge_invoice(
    *,
    invoice: Invoice,
    payment_method: PaymentMethod | None = None,
    adapter_name: str | None = None,
    actor_user=None,
    request=None,
) -> ChargeOutcome:
    invoice.refresh_from_db()
    if invoice.status not in {Invoice.Status.OPEN, Invoice.Status.DRAFT}:
        raise ServiceError(f"Cannot charge invoice in status {invoice.status!r}.")
    if invoice.amount_due_minor <= 0:
        raise ServiceError("Invoice has no outstanding amount due.")

    pm = _resolve_payment_method(invoice, payment_method)
    attempt_number = _next_attempt_number(invoice)
    idempotency_key = f"charge:{invoice.id}:{attempt_number}"

    # S13: ``smart_routing`` is a hint only today (single adapter). Stamp the
    # resolved policy onto PaymentAttempt.metadata so future multi-adapter
    # routing can select a path without re-checking the flag.
    routing_policy = "smart" if get_flag(invoice.merchant, "smart_routing") else "default"

    # Pre-create attempt row (PENDING) with idempotency key to detect dup runs.
    try:
        attempt = PaymentAttempt.objects.create(
            merchant=invoice.merchant,
            environment=invoice.environment,
            invoice=invoice,
            payment_method=pm,
            attempt_number=attempt_number,
            status=PaymentAttempt.Status.PENDING,
            amount_minor=invoice.amount_due_minor,
            currency=invoice.currency,
            idempotency_key=idempotency_key,
            metadata={"routing_policy": routing_policy},
        )
    except Exception as exc:  # uniq violation -> someone else already started this
        raise ConflictError("A charge attempt is already in progress for this invoice.") from exc

    adapter = get_adapter(adapter_name, environment=invoice.environment)

    try:
        result = adapter.charge(
            amount_minor=invoice.amount_due_minor,
            currency=invoice.currency,
            token=pm.token,
            idempotency_key=idempotency_key,
            metadata={
                "invoice_id": str(invoice.id),
                "customer_id": str(invoice.customer_id),
                "_invoice": invoice,
                "_payment_method": pm,
                **(pm.metadata or {}),
            },
        )
    except Exception as exc:
        attempt.status = PaymentAttempt.Status.FAILED
        attempt.failure_code = "processor_error"
        attempt.failure_message = str(exc)[:400]
        attempt.save(
            update_fields=["status", "failure_code", "failure_message", "updated_at"]
        )
        log_event(
            action="payments.charge_attempt_errored",
            actor_user=actor_user,
            merchant=invoice.merchant,
            environment=invoice.environment,
            target_type="payment_attempt",
            target_id=str(attempt.id),
            metadata={"error": str(exc)[:200], "invoice_id": str(invoice.id)},
            request=request,
        )
        raise ServiceError(f"Adapter raised: {exc}") from exc

    # Persist the outcome.
    if result.success:
        attempt.status = PaymentAttempt.Status.SUCCEEDED
        attempt.processor_reference = result.processor_reference[:128]
        attempt.failure_code = ""
        attempt.failure_message = ""
        attempt.save(
            update_fields=[
                "status",
                "processor_reference",
                "failure_code",
                "failure_message",
                "updated_at",
            ]
        )
        mark_paid(invoice=invoice, actor_user=actor_user, request=request)
        record_charge_transaction(attempt=attempt)
        log_event(
            action="payments.charge_succeeded",
            actor_user=actor_user,
            merchant=invoice.merchant,
            environment=invoice.environment,
            target_type="payment_attempt",
            target_id=str(attempt.id),
            metadata={
                "invoice_id": str(invoice.id),
                "amount_minor": attempt.amount_minor,
                "currency": attempt.currency,
                "reference": attempt.processor_reference,
            },
            request=request,
        )
    else:
        attempt.status = PaymentAttempt.Status.FAILED
        attempt.failure_code = (result.failure_code or "")[:64]
        attempt.failure_message = (result.failure_message or "")[:400]
        attempt.save(
            update_fields=[
                "status",
                "failure_code",
                "failure_message",
                "updated_at",
            ]
        )
        log_event(
            action="payments.charge_failed",
            actor_user=actor_user,
            merchant=invoice.merchant,
            environment=invoice.environment,
            target_type="payment_attempt",
            target_id=str(attempt.id),
            metadata={
                "invoice_id": str(invoice.id),
                "failure_code": attempt.failure_code,
                "failure_category": result.failure_category,
            },
            request=request,
        )
        _emit_event(
            merchant=invoice.merchant,
            environment=invoice.environment,
            event_type="invoice.payment_failed",
            aggregate_type="invoice",
            aggregate_id=str(invoice.id),
            payload={
                "invoice_id": str(invoice.id),
                "number": invoice.number,
                "customer_id": str(invoice.customer_id) if invoice.customer_id else "",
                "subscription_id": str(invoice.subscription_id) if invoice.subscription_id else "",
                "attempt_id": str(attempt.id),
                "attempt_number": attempt.attempt_number,
                "amount_minor": attempt.amount_minor,
                "currency": attempt.currency,
                "failure_code": attempt.failure_code,
                "failure_category": result.failure_category,
            },
            actor_user=actor_user,
            request=request,
        )
        # Hand off to the dunning engine: open or advance the run.
        _drive_dunning_after_failure(invoice=invoice, attempt=attempt, result=result, request=request)

    return ChargeOutcome(attempt=attempt, result=result)


def _drive_dunning_after_failure(*, invoice, attempt, result, request=None) -> None:
    """Open a dunning run on the first failure, otherwise advance the existing run."""
    try:
        from apps.dunning.models import DunningRun
        from apps.dunning.services import record_attempt_outcome, start_dunning_run
    except Exception:  # pragma: no cover — dunning app should always be installed
        return

    existing = DunningRun.objects.filter(
        invoice=invoice, status=DunningRun.Status.ACTIVE
    ).first()
    if existing is None:
        try:
            start_dunning_run(
                invoice=invoice, failure_code=result.failure_code, request=request
            )
        except Exception:  # noqa: BLE001 — never let dunning kill the charge path
            pass
        return
    try:
        record_attempt_outcome(
            run=existing,
            success=False,
            failure_code=result.failure_code,
            request=request,
        )
    except Exception:  # noqa: BLE001
        pass
        pass
        pass
        pass
        pass
