"""Payment delivery helpers."""
from __future__ import annotations

from decimal import Decimal

from apps.audit.services.log_event import log_event
from apps.common.email import merchant_email_context, send_templated_email
from apps.common.money import format_money

from ..models import PaymentAttempt


def _money(amount_minor: int, currency: str) -> str:
    return f"{currency.upper()} {Decimal(amount_minor) / Decimal(100):,.2f}"


def _pdf_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _pdf_text_line(y: int, text: str, *, size: int = 10, bold: bool = False) -> str:
    font = "F2" if bold else "F1"
    return f"BT /{font} {size} Tf 54 {y} Td ({_pdf_escape(text[:96])}) Tj ET"


def _build_pdf(lines: list[str]) -> bytes:
    stream = "\n".join(lines).encode("latin-1", "replace")
    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R /F2 5 0 R >> >> /Contents 6 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>",
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{index} 0 obj\n".encode("ascii"))
        pdf.extend(obj)
        pdf.extend(b"\nendobj\n")
    xref_at = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    pdf.extend(
        f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_at}\n%%EOF\n".encode(
            "ascii"
        )
    )
    return bytes(pdf)


def build_payment_receipt_pdf(attempt: PaymentAttempt) -> bytes:
    """Build a compact PDF receipt for a payment attempt."""
    attempt = (
        PaymentAttempt.objects.select_related(
            "invoice",
            "invoice__customer",
            "payment_method",
            "merchant",
        )
        .get(pk=attempt.pk)
    )
    invoice = attempt.invoice
    customer = invoice.customer
    method = attempt.payment_method
    payment_label = str(attempt.id)
    card_label = "-"
    if method:
        card_label = f"{method.brand.upper()} ending {method.last4}" if method.brand else f"Card ending {method.last4}"

    lines = [
        _pdf_text_line(770, "SubPilot payment receipt", size=18, bold=True),
        _pdf_text_line(742, f"Payment: {payment_label}", size=13, bold=True),
        _pdf_text_line(722, f"Merchant: {attempt.merchant.name}"),
        _pdf_text_line(706, f"Customer: {customer.name or customer.email} <{customer.email}>"),
        _pdf_text_line(690, f"Invoice: {invoice.number}"),
        _pdf_text_line(674, f"Status: {attempt.status}"),
        _pdf_text_line(658, f"Amount: {_money(attempt.amount_minor, attempt.currency)}", bold=True),
        _pdf_text_line(642, f"Payment method: {card_label}"),
        _pdf_text_line(626, f"Processor reference: {attempt.processor_reference or '-'}"),
        _pdf_text_line(610, f"Attempt number: {attempt.attempt_number}"),
        _pdf_text_line(594, f"Created: {attempt.created_at.isoformat()}"),
    ]
    if attempt.failure_message:
        lines.append(_pdf_text_line(570, f"Failure: {attempt.failure_message}"))
    return _build_pdf(lines)


def _payment_method_label(attempt: PaymentAttempt) -> str:
    method = attempt.payment_method
    if method is None:
        return "Payment method on file"
    if method.brand and method.last4:
        return f"{method.brand.upper()} ending {method.last4}"
    if method.last4:
        return f"Card ending {method.last4}"
    return "Payment method on file"


def send_payment_receipt_email(
    *, attempt: PaymentAttempt, actor_user=None, request=None
) -> dict:
    attempt = (
        PaymentAttempt.objects.select_related(
            "invoice",
            "invoice__customer",
            "merchant",
            "environment",
            "payment_method",
        )
        .get(pk=attempt.pk)
    )
    invoice = attempt.invoice
    customer = invoice.customer
    subject = f"Receipt for invoice {invoice.number}"
    send_templated_email(
        to=customer.email,
        subject=subject,
        template="payment_receipt",
        context=merchant_email_context(
            attempt.merchant,
            email_label="Receipt",
            recipient_name=customer.name or customer.email,
            invoice_number=invoice.number,
            amount_paid=format_money(attempt.amount_minor, attempt.currency),
            payment_method_label=_payment_method_label(attempt),
            processor_reference=attempt.processor_reference,
        ),
    )
    log_event(
        action="payments.receipt_emailed",
        actor_user=actor_user,
        merchant=attempt.merchant,
        environment=attempt.environment,
        target_type="payment_attempt",
        target_id=str(attempt.id),
        metadata={
            "invoice_id": str(invoice.id),
            "recipient": customer.email,
            "amount_minor": attempt.amount_minor,
            "currency": attempt.currency,
        },
        request=request,
    )
    return {"ok": True, "recipient": customer.email, "attempt_id": str(attempt.id)}


def send_payment_failed_email(
    *,
    attempt: PaymentAttempt,
    recovery_link: str = "",
    next_retry_at: str = "",
    actor_user=None,
    request=None,
) -> dict:
    attempt = (
        PaymentAttempt.objects.select_related(
            "invoice",
            "invoice__customer",
            "merchant",
            "environment",
            "payment_method",
        )
        .get(pk=attempt.pk)
    )
    invoice = attempt.invoice
    customer = invoice.customer
    subject = f"Payment failed for invoice {invoice.number}"
    send_templated_email(
        to=customer.email,
        subject=subject,
        template="payment_failed",
        context=merchant_email_context(
            attempt.merchant,
            email_label="Payment failed",
            recipient_name=customer.name or customer.email,
            invoice_number=invoice.number,
            amount_due=format_money(attempt.amount_minor, attempt.currency),
            failure_message=attempt.failure_message,
            recovery_link=recovery_link,
            next_retry_at=next_retry_at,
        ),
    )
    log_event(
        action="payments.failure_emailed",
        actor_user=actor_user,
        merchant=attempt.merchant,
        environment=attempt.environment,
        target_type="payment_attempt",
        target_id=str(attempt.id),
        metadata={
            "invoice_id": str(invoice.id),
            "recipient": customer.email,
            "has_recovery_link": bool(recovery_link),
        },
        request=request,
    )
    return {"ok": True, "recipient": customer.email, "attempt_id": str(attempt.id)}
