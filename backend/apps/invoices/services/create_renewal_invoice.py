"""Service: create_renewal_invoice.

Generates the next invoice for a subscription based on its active price
version. Idempotent on (subscription_id, period_end). The invoice is
finalized so payment processors can charge it; the payment service then
calls ``mark_paid`` after a successful charge.
"""
from __future__ import annotations

from apps.audit.services.log_event import log_event
from apps.common.db import atomic_with_retry
from apps.common.exceptions import ConflictError, ServiceError
from apps.subscriptions.models import Subscription, SubscriptionItem
from apps.subscriptions.periods import compute_period_end

from ..models import Invoice, InvoiceLineItem
from .create_invoice import create_invoice
from .lifecycle import finalize_invoice


@atomic_with_retry
def create_renewal_invoice(
    *,
    subscription: Subscription,
    actor_user=None,
    request=None,
) -> Invoice:
    if subscription.status not in {
        Subscription.Status.ACTIVE,
        Subscription.Status.PAST_DUE,
        Subscription.Status.TRIALING,
    }:
        raise ServiceError(
            f"Cannot generate renewal for status {subscription.status!r}."
        )

    period_end = subscription.current_period_end
    if period_end is None:
        raise ServiceError("Subscription has no current_period_end.")

    # Idempotency: refuse if an invoice already exists whose billing cycle
    # starts at this subscription's ``current_period_end``. ``period_start``
    # uniquely identifies a billing cycle; ``period_end`` is shared with the
    # NEXT cycle (cycle N's end == cycle N+1's start in subscription terms)
    # so filtering on it produces false-positive collisions on the second
    # renewal of the same subscription.
    existing = Invoice.objects.filter(
        subscription=subscription,
        metadata__period_start=period_end.isoformat(),
    ).first()
    if existing is not None:
        raise ConflictError(
            f"Renewal invoice already exists for period starting {period_end.isoformat()}."
        )

    item = (
        SubscriptionItem.objects.filter(
            subscription=subscription, status=SubscriptionItem.Status.ACTIVE
        )
        .select_related("price_version")
        .first()
    )
    if item is None:
        raise ServiceError("Subscription has no active item.")

    pv = item.price_version
    line_amount = pv.amount_minor * item.quantity

    line_items = [
        {
            "type": InvoiceLineItem.Type.SUBSCRIPTION,
            "description": f"{subscription.plan.name} ({pv.interval_count} {pv.interval_unit})",
            "amount_minor": pv.amount_minor,
            "quantity": item.quantity,
            "currency": pv.currency,
            "metadata": {"price_version_id": str(pv.id)},
        }
    ]

    metadata = {
        "renewal": True,
        "period_start": period_end.isoformat(),
        "period_end": compute_period_end(period_end, pv).isoformat(),
        "price_version_id": str(pv.id),
        "line_amount_minor": line_amount,
    }

    invoice = create_invoice(
        merchant=subscription.merchant,
        environment=subscription.environment,
        customer=subscription.customer,
        currency=pv.currency,
        line_items=line_items,
        subscription=subscription,
        due_at=period_end,
        metadata=metadata,
        actor_user=actor_user,
        request=request,
    )
    invoice = finalize_invoice(invoice=invoice, actor_user=actor_user, request=request)

    # Advance the subscription's current period.
    subscription.current_period_start = period_end
    subscription.current_period_end = compute_period_end(period_end, pv)
    subscription.save(
        update_fields=["current_period_start", "current_period_end", "updated_at"]
    )

    log_event(
        action="invoices.renewal_invoice_created",
        actor_user=actor_user,
        merchant=subscription.merchant,
        environment=subscription.environment,
        target_type="invoice",
        target_id=str(invoice.id),
        metadata={
            "subscription_id": str(subscription.id),
            "number": invoice.number,
        },
        request=request,
    )
    return invoice
