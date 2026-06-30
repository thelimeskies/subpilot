"""Service: create_invoice (manual / one-off).

Creates a draft invoice for a customer with a list of line items. Used by:
- Renewal generators (``create_renewal_invoice``).
- Manual one-off charges from the dashboard.

Line items:
    [{"type": "subscription"|"one_time"|"setup_fee"|...,
      "description": "...", "amount_minor": int, "quantity": int, "currency": "NGN"}]
"""
from __future__ import annotations

from apps.audit.services.log_event import log_event
from apps.common.db import atomic_with_retry
from apps.common.exceptions import ServiceError
from apps.customers.models import Customer
from apps.events.services.create_event import emit as _emit_event

from ..models import Invoice, InvoiceLineItem
from ..numbering import allocate_invoice_number


def _validate_line(line: dict, default_currency: str) -> None:
    if "type" not in line or line["type"] not in dict(InvoiceLineItem.Type.choices):
        raise ServiceError(f"Invalid line item type: {line.get('type')!r}")
    if "amount_minor" not in line:
        raise ServiceError("Line item is missing amount_minor.")
    qty = int(line.get("quantity", 1))
    if qty < 1:
        raise ServiceError("Line item quantity must be >= 1.")
    cur = line.get("currency") or default_currency
    if not cur or len(cur) != 3:
        raise ServiceError("Line item currency must be a 3-letter ISO code.")


@atomic_with_retry
def create_invoice(
    *,
    merchant,
    environment,
    customer: Customer,
    currency: str,
    line_items: list[dict],
    subscription=None,
    due_at=None,
    metadata: dict | None = None,
    actor_user=None,
    request=None,
) -> Invoice:
    if customer.merchant_id != merchant.id or customer.environment_id != environment.id:
        raise ServiceError("Customer does not belong to this tenant.")
    if subscription is not None and (
        subscription.merchant_id != merchant.id or subscription.environment_id != environment.id
    ):
        raise ServiceError("Subscription does not belong to this tenant.")
    if not line_items:
        raise ServiceError("At least one line item is required.")
    if not currency or len(currency) != 3:
        raise ServiceError("Currency must be a 3-letter ISO code.")
    for line in line_items:
        _validate_line(line, currency)

    # Compute totals (positive types add, discount/credit subtract).
    subtotal = 0
    discount = 0
    tax = 0
    for line in line_items:
        amt = int(line["amount_minor"]) * int(line.get("quantity", 1))
        t = line["type"]
        if t == InvoiceLineItem.Type.DISCOUNT:
            discount += amt
        elif t == InvoiceLineItem.Type.TAX:
            tax += amt
        elif t == InvoiceLineItem.Type.CREDIT:
            discount += amt
        else:
            subtotal += amt
    total = max(0, subtotal - discount + tax)

    invoice = Invoice.objects.create(
        merchant=merchant,
        environment=environment,
        customer=customer,
        subscription=subscription,
        number=allocate_invoice_number(merchant=merchant, environment=environment),
        status=Invoice.Status.DRAFT,
        subtotal_minor=subtotal,
        discount_minor=discount,
        tax_minor=tax,
        total_minor=total,
        amount_due_minor=total,
        currency=currency.upper(),
        due_at=due_at,
        metadata=metadata or {},
    )
    for line in line_items:
        InvoiceLineItem.objects.create(
            invoice=invoice,
            type=line["type"],
            description=line.get("description", ""),
            amount_minor=int(line["amount_minor"]),
            quantity=int(line.get("quantity", 1)),
            currency=(line.get("currency") or currency).upper(),
            metadata=line.get("metadata") or {},
        )

    log_event(
        action="invoices.invoice_created",
        actor_user=actor_user,
        merchant=merchant,
        environment=environment,
        target_type="invoice",
        target_id=str(invoice.id),
        metadata={"number": invoice.number, "total_minor": total, "currency": currency.upper()},
        request=request,
    )
    _emit_event(
        merchant=merchant,
        environment=environment,
        event_type="invoice.created",
        aggregate_type="invoice",
        aggregate_id=str(invoice.id),
        payload={
            "invoice_id": str(invoice.id),
            "number": invoice.number,
            "customer_id": str(invoice.customer_id) if invoice.customer_id else "",
            "subscription_id": str(invoice.subscription_id) if invoice.subscription_id else "",
            "status": invoice.status,
            "currency": invoice.currency,
            "total_minor": invoice.total_minor,
            "amount_due_minor": invoice.amount_due_minor,
        },
        actor_user=actor_user,
        request=request,
    )
    return invoice
