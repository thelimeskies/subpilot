"""Cross-tenant payment write actions (S5).

The platform admin can record a refund on any merchant's captured payment.
We write a negative balance transaction, store display metadata on the
invoice, and emit an audit-log entry under ``platform.payment.refund``.
The external processor refund API is still a follow-up; this service keeps
SubPilot's internal revenue reporting net of the recorded refund.
"""
from __future__ import annotations

from dataclasses import dataclass

from django.db import transaction
from django.http import HttpRequest
from django.utils import timezone

from apps.audit.services.log_event import log_event
from apps.invoices.models import CreditNote
from apps.payments.models import PaymentAttempt
from apps.payments.services import record_refund_transaction

from ..models import PlatformAdmin


class PaymentNotFoundError(LookupError):
    pass


class PaymentNotRefundableError(ValueError):
    pass


@dataclass(frozen=True)
class PaymentActionResult:
    payment_id: str
    status: str
    refunded_at: str | None = None


def _resolve(payment_id) -> PaymentAttempt:
    try:
        return (
            PaymentAttempt.objects.select_related("merchant", "invoice")
            .get(pk=payment_id)
        )
    except (PaymentAttempt.DoesNotExist, ValueError) as exc:
        raise PaymentNotFoundError(str(payment_id)) from exc


def _actor_label(admin: PlatformAdmin | None) -> str:
    if admin is None:
        return "platform_admin"
    return admin.email or admin.display_name or "platform_admin"


@transaction.atomic
def refund_payment(
    *,
    payment_id,
    admin: PlatformAdmin | None,
    reason: str = "",
    note: str = "",
    request: HttpRequest | None = None,
) -> PaymentActionResult:
    """Mark a captured payment as refunded (idempotent).

    Stores ``{refunded_at, refund_reason, refund_admin}`` on
    ``Invoice.metadata`` so the cross-tenant payments list surfaces a
    ``Refunded`` status on the next read. Emits a
    ``platform.payment.refund`` audit row.
    """
    attempt = _resolve(payment_id)

    if attempt.status != PaymentAttempt.Status.SUCCEEDED:
        raise PaymentNotRefundableError(
            f"Cannot refund a {attempt.status} payment.",
        )

    invoice = attempt.invoice
    metadata = dict(invoice.metadata or {})
    already_refunded = bool(metadata.get("refunded_at"))

    if not already_refunded:
        refunded_at = timezone.now()
        credit_note = CreditNote.objects.create(
            merchant=attempt.merchant,
            environment=attempt.environment,
            invoice=invoice,
            amount_minor=attempt.amount_minor,
            currency=attempt.currency,
            reason=CreditNote.Reason.REFUND,
            note=(reason or note or "").strip()[:400],
        )
        record_refund_transaction(
            attempt=attempt,
            amount_minor=attempt.amount_minor,
            credit_note=credit_note,
            metadata={"reason": reason, "note": note, "actor": "platform_admin"},
        )
        metadata.update(
            {
                "refunded_at": refunded_at.isoformat(),
                "refund_reason": (reason or "").strip()[:400],
                "refund_admin_email": getattr(admin, "email", "") if admin else "",
                "refund_payment_attempt_id": str(attempt.id),
                "refunded_amount_minor": attempt.amount_minor,
                "refund_full": True,
            }
        )
        invoice.metadata = metadata
        invoice.save(update_fields=["metadata", "updated_at"])

    log_event(
        action="platform.payment.refund",
        actor_user=None,
        actor_label=_actor_label(admin),
        actor_role="platform_admin",
        merchant=attempt.merchant,
        target_type="payment_attempt",
        target_id=str(attempt.id),
        metadata={
            "reason": (reason or "").strip()[:400],
            "note": (note or "").strip()[:400],
            "invoice_id": str(invoice.id),
            "amount_minor": attempt.amount_minor,
            "currency": attempt.currency,
            "idempotent": already_refunded,
        },
        request=request,
    )
    return PaymentActionResult(
        payment_id=str(attempt.id),
        status="refunded",
        refunded_at=metadata.get("refunded_at"),
    )


__all__ = [
    "PaymentNotFoundError",
    "PaymentNotRefundableError",
    "PaymentActionResult",
    "refund_payment",
]
