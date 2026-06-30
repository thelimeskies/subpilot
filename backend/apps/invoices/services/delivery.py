"""Invoice delivery helpers: PDF rendering and customer reminders."""
from __future__ import annotations

from decimal import Decimal

from apps.audit.services.log_event import log_event
from apps.common.email import format_email_date, merchant_email_context, send_templated_email
from apps.common.exceptions import ServiceError
from apps.common.money import format_money

from ..models import Invoice


def _money(amount_minor: int, currency: str) -> str:
    return f"{currency.upper()} {Decimal(amount_minor) / Decimal(100):,.2f}"


def _pdf_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _pdf_text_line(y: int, text: str, *, size: int = 10, bold: bool = False) -> str:
    font = "F2" if bold else "F1"
    return f"BT /{font} {size} Tf 54 {y} Td ({_pdf_escape(text[:96])}) Tj ET"


def build_invoice_pdf(invoice: Invoice) -> bytes:
    """Build a compact, dependency-free PDF for invoice download."""
    invoice = (
        Invoice.objects.select_related("customer", "merchant")
        .prefetch_related("line_items")
        .get(pk=invoice.pk)
    )
    customer = invoice.customer
    lines = [
        _pdf_text_line(770, "SubPilot invoice", size=18, bold=True),
        _pdf_text_line(742, f"Invoice: {invoice.number}", size=13, bold=True),
        _pdf_text_line(722, f"Merchant: {invoice.merchant.name}"),
        _pdf_text_line(706, f"Customer: {customer.name or customer.email} <{customer.email}>"),
        _pdf_text_line(690, f"Status: {invoice.status}"),
        _pdf_text_line(674, f"Issued: {invoice.created_at.date().isoformat()}"),
        _pdf_text_line(658, f"Due: {invoice.due_at.date().isoformat() if invoice.due_at else '-'}"),
        _pdf_text_line(628, "Line items", size=12, bold=True),
    ]
    y = 608
    for item in invoice.line_items.all()[:18]:
        amount = item.amount_minor * item.quantity
        lines.append(
            _pdf_text_line(
                y,
                f"{item.description or item.type} | Qty {item.quantity} | {_money(amount, item.currency)}",
            )
        )
        y -= 16
    y -= 12
    lines.extend(
        [
            _pdf_text_line(y, f"Subtotal: {_money(invoice.subtotal_minor, invoice.currency)}"),
            _pdf_text_line(y - 16, f"Discount: {_money(invoice.discount_minor, invoice.currency)}"),
            _pdf_text_line(y - 32, f"Tax: {_money(invoice.tax_minor, invoice.currency)}"),
            _pdf_text_line(y - 48, f"Total: {_money(invoice.total_minor, invoice.currency)}", bold=True),
            _pdf_text_line(y - 64, f"Balance due: {_money(invoice.amount_due_minor, invoice.currency)}", bold=True),
        ]
    )
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


def send_invoice_reminder(
    *,
    invoice: Invoice,
    channel: str,
    message: str,
    actor_user=None,
    request=None,
) -> dict:
    invoice = Invoice.objects.select_related("customer", "merchant", "environment").get(
        pk=invoice.pk
    )
    channel = (channel or "email").strip().lower()
    if channel not in {"email", "sms"}:
        raise ServiceError("Unsupported reminder channel.")
    message = (message or "").strip()
    if not message:
        raise ServiceError("Reminder message is required.")

    sent = False
    if channel == "email":
        subject = f"Reminder: invoice {invoice.number}"
        send_templated_email(
            to=invoice.customer.email,
            subject=subject,
            template="invoice_reminder",
            context=merchant_email_context(
                invoice.merchant,
                email_label="Invoice reminder",
                recipient_name=invoice.customer.name or invoice.customer.email,
                invoice_number=invoice.number,
                amount_due=format_money(invoice.amount_due_minor, invoice.currency),
                due_at=format_email_date(invoice.due_at),
                hosted_payment_url=invoice.hosted_payment_url,
                message=message,
            ),
        )
        sent = True

    log_event(
        action="invoices.invoice_reminder_sent",
        actor_user=actor_user,
        merchant=invoice.merchant,
        environment=invoice.environment,
        target_type="invoice",
        target_id=str(invoice.id),
        metadata={
            "number": invoice.number,
            "channel": channel,
            "sent": sent,
            "recipient": invoice.customer.email if channel == "email" else invoice.customer.phone,
        },
        request=request,
    )
    return {
        "ok": True,
        "channel": channel,
        "sent": sent,
        "recipient": invoice.customer.email if channel == "email" else invoice.customer.phone,
    }
