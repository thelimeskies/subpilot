"""Invoice selectors: read-only query composition."""
from __future__ import annotations

from django.db.models import QuerySet

from .models import Invoice, InvoiceLineItem


def invoices_for(merchant, environment) -> QuerySet[Invoice]:
    return (
        Invoice.objects.filter(merchant=merchant, environment=environment)
        .select_related("customer", "subscription")
        .prefetch_related("line_items")
    )


def line_items_for(invoice: Invoice) -> QuerySet[InvoiceLineItem]:
    return InvoiceLineItem.objects.filter(invoice=invoice)


def open_invoices_for(merchant, environment) -> QuerySet[Invoice]:
    return invoices_for(merchant, environment).filter(status=Invoice.Status.OPEN)
