"""Customers selectors: read-only query composition."""
from __future__ import annotations

from django.db.models import QuerySet

from .models import Customer, PaymentMethod, PortalSession


def customers_for(merchant, environment) -> QuerySet[Customer]:
    return Customer.objects.filter(merchant=merchant, environment=environment)


def payment_methods_for(customer: Customer) -> QuerySet[PaymentMethod]:
    return PaymentMethod.objects.filter(customer=customer).order_by(
        "-is_default", "-created_at"
    )


def portal_sessions_for(customer: Customer) -> QuerySet[PortalSession]:
    return PortalSession.objects.filter(customer=customer).order_by("-created_at")


def default_payment_method(customer: Customer) -> PaymentMethod | None:
    return (
        PaymentMethod.objects.filter(
            customer=customer, is_default=True, status=PaymentMethod.Status.ACTIVE
        )
        .order_by("-created_at")
        .first()
    )
