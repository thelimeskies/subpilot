"""Invoice lifecycle services: finalize, mark_paid, void, mark_uncollectible."""
from __future__ import annotations

from django.utils import timezone

from apps.audit.services.log_event import log_event
from apps.common.db import atomic_with_retry
from apps.common.exceptions import ServiceError
from apps.events.services.create_event import emit as _emit_event

from ..models import CreditNote, Invoice


def _invoice_payload(invoice: Invoice, **extra) -> dict:
    return {
        "invoice_id": str(invoice.id),
        "number": invoice.number,
        "customer_id": str(invoice.customer_id) if invoice.customer_id else "",
        "subscription_id": str(invoice.subscription_id) if invoice.subscription_id else "",
        "status": invoice.status,
        "currency": invoice.currency,
        "total_minor": invoice.total_minor,
        "amount_due_minor": invoice.amount_due_minor,
        **extra,
    }


@atomic_with_retry
def finalize_invoice(*, invoice: Invoice, actor_user=None, request=None) -> Invoice:
    """``draft`` -> ``open``. Locks line items in for billing."""
    invoice.refresh_from_db()
    if invoice.status != Invoice.Status.DRAFT:
        raise ServiceError("Only draft invoices can be finalized.")
    invoice.status = Invoice.Status.OPEN
    invoice.amount_due_minor = invoice.total_minor
    invoice.save(update_fields=["status", "amount_due_minor", "updated_at"])
    log_event(
        action="invoices.invoice_finalized",
        actor_user=actor_user,
        merchant=invoice.merchant,
        environment=invoice.environment,
        target_type="invoice",
        target_id=str(invoice.id),
        metadata={"number": invoice.number},
        request=request,
    )
    _emit_event(
        merchant=invoice.merchant,
        environment=invoice.environment,
        event_type="invoice.finalized",
        aggregate_type="invoice",
        aggregate_id=str(invoice.id),
        payload=_invoice_payload(invoice),
        actor_user=actor_user,
        request=request,
    )
    return invoice


@atomic_with_retry
def mark_paid(
    *,
    invoice: Invoice,
    paid_amount_minor: int | None = None,
    paid_at=None,
    actor_user=None,
    request=None,
) -> Invoice:
    invoice.refresh_from_db()
    if invoice.status not in {Invoice.Status.OPEN, Invoice.Status.DRAFT}:
        raise ServiceError(f"Cannot mark {invoice.status!r} invoice paid.")
    paid = paid_amount_minor if paid_amount_minor is not None else invoice.amount_due_minor
    if paid < 0:
        raise ServiceError("paid_amount_minor cannot be negative.")
    invoice.amount_due_minor = max(0, invoice.amount_due_minor - paid)
    invoice.paid_at = paid_at or timezone.now()
    if invoice.amount_due_minor == 0:
        invoice.status = Invoice.Status.PAID
    invoice.save(update_fields=["amount_due_minor", "paid_at", "status", "updated_at"])
    log_event(
        action="invoices.invoice_marked_paid",
        actor_user=actor_user,
        merchant=invoice.merchant,
        environment=invoice.environment,
        target_type="invoice",
        target_id=str(invoice.id),
        metadata={
            "number": invoice.number,
            "paid_amount_minor": paid,
            "remaining_due_minor": invoice.amount_due_minor,
        },
        request=request,
    )
    _emit_event(
        merchant=invoice.merchant,
        environment=invoice.environment,
        event_type="invoice.payment_succeeded",
        aggregate_type="invoice",
        aggregate_id=str(invoice.id),
        payload=_invoice_payload(invoice, paid_amount_minor=paid),
        actor_user=actor_user,
        request=request,
    )
    return invoice


@atomic_with_retry
def mark_manual_payment(
    *,
    invoice: Invoice,
    paid_amount_minor: int | None = None,
    paid_at=None,
    actor_user=None,
    request=None,
) -> Invoice:
    """Record an operator-entered payment and reconcile the invoice.

    Processor-driven charges create their own ``PaymentAttempt`` rows before
    calling ``mark_paid``. This service is only for the dashboard's manual
    reconciliation action, where no processor attempt exists yet.
    """
    invoice.refresh_from_db()
    if invoice.status not in {Invoice.Status.OPEN, Invoice.Status.DRAFT}:
        raise ServiceError(f"Cannot mark {invoice.status!r} invoice paid.")

    paid = paid_amount_minor if paid_amount_minor is not None else invoice.amount_due_minor
    if paid <= 0:
        raise ServiceError("paid_amount_minor must be positive.")
    if paid > invoice.amount_due_minor:
        raise ServiceError("paid_amount_minor cannot exceed the outstanding amount.")

    from apps.payments.models import PaymentAttempt
    from apps.payments.services import record_charge_transaction

    last_attempt_number = (
        PaymentAttempt.objects.filter(invoice=invoice)
        .order_by("-attempt_number")
        .values_list("attempt_number", flat=True)
        .first()
    )
    attempt = PaymentAttempt.objects.create(
        merchant=invoice.merchant,
        environment=invoice.environment,
        invoice=invoice,
        payment_method=getattr(invoice.subscription, "default_payment_method", None),
        attempt_number=(last_attempt_number or 0) + 1,
        status=PaymentAttempt.Status.SUCCEEDED,
        amount_minor=paid,
        currency=invoice.currency,
        processor_reference=f"manual-{invoice.number}-{(last_attempt_number or 0) + 1}"[:128],
        idempotency_key=f"manual:{invoice.id}:{(last_attempt_number or 0) + 1}",
        metadata={"source": "merchant_dashboard_manual"},
    )
    invoice = mark_paid(
        invoice=invoice,
        paid_amount_minor=paid,
        paid_at=paid_at,
        actor_user=actor_user,
        request=request,
    )
    record_charge_transaction(attempt=attempt)
    return invoice


@atomic_with_retry
def apply_credit_note(
    *,
    invoice: Invoice,
    amount_minor: int,
    reason: str = CreditNote.Reason.OTHER,
    note: str = "",
    actor_user=None,
    request=None,
) -> tuple[Invoice, CreditNote]:
    invoice.refresh_from_db()
    if invoice.status not in {Invoice.Status.OPEN, Invoice.Status.DRAFT}:
        raise ServiceError(f"Cannot credit {invoice.status!r} invoice.")
    if amount_minor <= 0:
        raise ServiceError("amount_minor must be positive.")
    applied = min(amount_minor, invoice.amount_due_minor)
    if applied <= 0:
        raise ServiceError("Invoice has no outstanding amount due.")

    credit_note = CreditNote.objects.create(
        merchant=invoice.merchant,
        environment=invoice.environment,
        invoice=invoice,
        amount_minor=applied,
        currency=invoice.currency,
        reason=reason,
        note=note,
    )
    from apps.payments.services import record_credit_transaction

    record_credit_transaction(credit_note=credit_note, metadata={"reason": reason})
    invoice.amount_due_minor = max(0, invoice.amount_due_minor - applied)
    invoice.metadata = {
        **(invoice.metadata or {}),
        "last_credit_note_id": str(credit_note.id),
        "last_credit_note_reason": reason,
        "last_credit_note_note": note,
    }
    update_fields = ["amount_due_minor", "metadata", "updated_at"]
    if invoice.amount_due_minor == 0:
        invoice.status = Invoice.Status.PAID
        invoice.paid_at = timezone.now()
        update_fields.extend(["status", "paid_at"])
    invoice.save(update_fields=update_fields)

    log_event(
        action="invoices.credit_note_applied",
        actor_user=actor_user,
        merchant=invoice.merchant,
        environment=invoice.environment,
        target_type="invoice",
        target_id=str(invoice.id),
        metadata={
            "number": invoice.number,
            "credit_note_id": str(credit_note.id),
            "amount_minor": applied,
            "reason": reason,
            "remaining_due_minor": invoice.amount_due_minor,
        },
        request=request,
    )
    _emit_event(
        merchant=invoice.merchant,
        environment=invoice.environment,
        event_type="invoice.credit_note_applied",
        aggregate_type="invoice",
        aggregate_id=str(invoice.id),
        payload=_invoice_payload(
            invoice,
            credit_note_id=str(credit_note.id),
            amount_minor=applied,
            reason=reason,
        ),
        actor_user=actor_user,
        request=request,
    )
    return invoice, credit_note


@atomic_with_retry
def void_invoice(
    *, invoice: Invoice, reason: str = "", actor_user=None, request=None
) -> Invoice:
    invoice.refresh_from_db()
    if invoice.status not in {Invoice.Status.DRAFT, Invoice.Status.OPEN}:
        raise ServiceError("Only draft/open invoices can be voided.")
    invoice.status = Invoice.Status.VOID
    invoice.amount_due_minor = 0
    invoice.metadata = {**(invoice.metadata or {}), "void_reason": reason}
    invoice.save(update_fields=["status", "amount_due_minor", "metadata", "updated_at"])
    log_event(
        action="invoices.invoice_voided",
        actor_user=actor_user,
        merchant=invoice.merchant,
        environment=invoice.environment,
        target_type="invoice",
        target_id=str(invoice.id),
        metadata={"number": invoice.number, "reason": reason},
        request=request,
    )
    _emit_event(
        merchant=invoice.merchant,
        environment=invoice.environment,
        event_type="invoice.voided",
        aggregate_type="invoice",
        aggregate_id=str(invoice.id),
        payload=_invoice_payload(invoice, reason=reason),
        actor_user=actor_user,
        request=request,
    )
    return invoice


@atomic_with_retry
def mark_uncollectible(
    *, invoice: Invoice, reason: str = "", actor_user=None, request=None
) -> Invoice:
    invoice.refresh_from_db()
    if invoice.status != Invoice.Status.OPEN:
        raise ServiceError("Only open invoices can be marked uncollectible.")
    invoice.status = Invoice.Status.UNCOLLECTIBLE
    invoice.metadata = {**(invoice.metadata or {}), "uncollectible_reason": reason}
    invoice.save(update_fields=["status", "metadata", "updated_at"])
    log_event(
        action="invoices.invoice_marked_uncollectible",
        actor_user=actor_user,
        merchant=invoice.merchant,
        environment=invoice.environment,
        target_type="invoice",
        target_id=str(invoice.id),
        metadata={"number": invoice.number, "reason": reason},
        request=request,
    )
    _emit_event(
        merchant=invoice.merchant,
        environment=invoice.environment,
        event_type="invoice.marked_uncollectible",
        aggregate_type="invoice",
        aggregate_id=str(invoice.id),
        payload=_invoice_payload(invoice, reason=reason),
        actor_user=actor_user,
        request=request,
    )
    return invoice
