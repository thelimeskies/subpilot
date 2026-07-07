"""Hosted checkout entry point for tokenized-card subscriptions."""
from __future__ import annotations

from apps.common.exceptions import ServiceError
from apps.invoices.models import Invoice, InvoiceLineItem
from apps.invoices.services.create_invoice import create_invoice
from apps.invoices.services.lifecycle import finalize_invoice
from apps.payments.services import create_nomba_tokenized_checkout

from ..models import Subscription, SubscriptionItem


def start_subscription_tokenized_checkout(
    *,
    subscription: Subscription,
    actor_user=None,
    request=None,
) -> tuple[Invoice, dict]:
    """Create the first customer-present checkout for a subscription.

    The subscription remains incomplete until the Nomba payment_success webhook
    delivers tokenizedCardData.tokenKey. That webhook attaches the payment
    method, makes it default, and activates the subscription.
    """
    subscription.refresh_from_db()
    if subscription.status != Subscription.Status.INCOMPLETE:
        raise ServiceError("Only incomplete subscriptions can start tokenized checkout.")

    invoice = (
        Invoice.objects.filter(
            subscription=subscription,
            metadata__initial_subscription_checkout=True,
        )
        .exclude(status=Invoice.Status.VOID)
        .order_by("-created_at")
        .first()
    )
    if invoice is None:
        item = (
            SubscriptionItem.objects.filter(
                subscription=subscription,
                status=SubscriptionItem.Status.ACTIVE,
            )
            .select_related("price_version")
            .first()
        )
        if item is None:
            raise ServiceError("Subscription has no active item.")
        pv = item.price_version
        invoice = create_invoice(
            merchant=subscription.merchant,
            environment=subscription.environment,
            customer=subscription.customer,
            currency=pv.currency,
            line_items=[
                {
                    "type": InvoiceLineItem.Type.SUBSCRIPTION,
                    "description": f"{subscription.plan.name} initial payment",
                    "amount_minor": pv.amount_minor,
                    "quantity": item.quantity,
                    "currency": pv.currency,
                    "metadata": {"price_version_id": str(pv.id)},
                }
            ],
            subscription=subscription,
            metadata={
                "initial_subscription_checkout": True,
                "subscription_id": str(subscription.id),
                "price_version_id": str(pv.id),
            },
            actor_user=actor_user,
            request=request,
        )
        invoice = finalize_invoice(invoice=invoice, actor_user=actor_user, request=request)

    response = create_nomba_tokenized_checkout(invoice=invoice)
    invoice.refresh_from_db()
    return invoice, response
