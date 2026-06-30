"""Balance transaction helpers for revenue-safe reporting."""
from __future__ import annotations

from apps.common.exceptions import ServiceError

from ..models import BalanceTransaction, PaymentAttempt


def _assert_same_scope(*, merchant, environment, invoice=None, payment_attempt=None, credit_note=None) -> None:
    for obj, label in (
        (invoice, "Invoice"),
        (payment_attempt, "Payment attempt"),
        (credit_note, "Credit note"),
    ):
        if obj is None:
            continue
        if obj.merchant_id != merchant.id or obj.environment_id != environment.id:
            raise ServiceError(f"{label} does not belong to this tenant.")


def record_balance_transaction(
    *,
    merchant,
    environment,
    type: str,
    signed_amount_minor: int,
    currency: str,
    invoice,
    payment_attempt: PaymentAttempt | None = None,
    credit_note=None,
    processor_reference: str = "",
    idempotency_key: str = "",
    metadata: dict | None = None,
) -> BalanceTransaction:
    if signed_amount_minor == 0:
        raise ServiceError("Balance transaction amount cannot be zero.")
    if type not in BalanceTransaction.Type.values:
        raise ServiceError(f"Unknown balance transaction type: {type!r}.")
    if not currency or len(currency) != 3:
        raise ServiceError("Currency must be a 3-letter ISO code.")
    _assert_same_scope(
        merchant=merchant,
        environment=environment,
        invoice=invoice,
        payment_attempt=payment_attempt,
        credit_note=credit_note,
    )

    defaults = {
        "type": type,
        "signed_amount_minor": signed_amount_minor,
        "currency": currency.upper(),
        "invoice": invoice,
        "payment_attempt": payment_attempt,
        "credit_note": credit_note,
        "processor_reference": processor_reference[:128],
        "metadata": metadata or {},
    }
    if idempotency_key:
        tx, _created = BalanceTransaction.objects.get_or_create(
            merchant=merchant,
            environment=environment,
            idempotency_key=idempotency_key[:160],
            defaults=defaults,
        )
        return tx

    return BalanceTransaction.objects.create(
        merchant=merchant,
        environment=environment,
        idempotency_key="",
        **defaults,
    )


def record_charge_transaction(*, attempt: PaymentAttempt) -> BalanceTransaction:
    return record_balance_transaction(
        merchant=attempt.merchant,
        environment=attempt.environment,
        type=BalanceTransaction.Type.CHARGE,
        signed_amount_minor=attempt.amount_minor,
        currency=attempt.currency,
        invoice=attempt.invoice,
        payment_attempt=attempt,
        processor_reference=attempt.processor_reference,
        idempotency_key=f"charge:{attempt.id}",
    )


def record_refund_transaction(
    *, attempt: PaymentAttempt, amount_minor: int, credit_note=None, metadata: dict | None = None
) -> BalanceTransaction:
    if amount_minor <= 0:
        raise ServiceError("Refund amount must be positive.")
    refund_key = credit_note.id if credit_note is not None else amount_minor
    return record_balance_transaction(
        merchant=attempt.merchant,
        environment=attempt.environment,
        type=BalanceTransaction.Type.REFUND,
        signed_amount_minor=-amount_minor,
        currency=attempt.currency,
        invoice=attempt.invoice,
        payment_attempt=attempt,
        credit_note=credit_note,
        processor_reference=attempt.processor_reference,
        idempotency_key=f"refund:{attempt.id}:{refund_key}",
        metadata=metadata,
    )


def record_credit_transaction(*, credit_note, metadata: dict | None = None) -> BalanceTransaction:
    return record_balance_transaction(
        merchant=credit_note.merchant,
        environment=credit_note.environment,
        type=BalanceTransaction.Type.CREDIT,
        signed_amount_minor=-credit_note.amount_minor,
        currency=credit_note.currency,
        invoice=credit_note.invoice,
        credit_note=credit_note,
        idempotency_key=f"credit:{credit_note.id}",
        metadata=metadata,
    )
