"""Payments selectors."""
from __future__ import annotations

from django.db.models import QuerySet

from .models import PaymentAttempt, ProcessorEvent


def payment_attempts_for(merchant, environment) -> QuerySet[PaymentAttempt]:
    return (
        PaymentAttempt.objects.filter(merchant=merchant, environment=environment)
        .select_related("invoice", "payment_method")
    )


def attempts_for_invoice(invoice) -> QuerySet[PaymentAttempt]:
    return PaymentAttempt.objects.filter(invoice=invoice).order_by("attempt_number")


def processor_events_for(merchant, environment) -> QuerySet[ProcessorEvent]:
    return ProcessorEvent.objects.filter(merchant=merchant, environment=environment)
