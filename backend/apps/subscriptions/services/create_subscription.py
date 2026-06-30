"""Service: create_subscription.

Creates a subscription in the `incomplete` state with one initial item bound
to the plan's currently-active PriceVersion. The subscription is then
typically activated by ``activate_subscription`` after an initial invoice is
paid (or directly, for trial / free flows).
"""
from __future__ import annotations

from apps.audit.services.log_event import log_event
from apps.catalog.models import Plan
from apps.catalog.selectors import active_price_version
from apps.common.db import atomic_with_retry
from apps.common.exceptions import ServiceError
from apps.customers.models import Customer, PaymentMethod

from ..models import Subscription, SubscriptionEvent, SubscriptionItem


@atomic_with_retry
def create_subscription(
    *,
    merchant,
    environment,
    customer: Customer,
    plan: Plan,
    quantity: int = 1,
    default_payment_method: PaymentMethod | None = None,
    metadata: dict | None = None,
    actor_user=None,
    request=None,
) -> Subscription:
    if customer.merchant_id != merchant.id or customer.environment_id != environment.id:
        raise ServiceError("Customer does not belong to this tenant.")
    if plan.merchant_id != merchant.id or plan.environment_id != environment.id:
        raise ServiceError("Plan does not belong to this tenant.")
    if plan.status != Plan.Status.ACTIVE:
        raise ServiceError("Only active plans can be subscribed to.")
    pv = active_price_version(plan)
    if pv is None:
        raise ServiceError("Plan has no active price version.")
    if default_payment_method is not None and default_payment_method.customer_id != customer.id:
        raise ServiceError("Payment method does not belong to this customer.")
    if quantity < 1:
        raise ServiceError("Quantity must be >= 1.")

    sub = Subscription.objects.create(
        merchant=merchant,
        environment=environment,
        customer=customer,
        plan=plan,
        status=Subscription.Status.INCOMPLETE,
        default_payment_method=default_payment_method,
        dunning_policy=plan.dunning_policy,
        metadata=metadata or {},
    )
    SubscriptionItem.objects.create(
        subscription=sub,
        price_version=pv,
        quantity=quantity,
    )
    SubscriptionEvent.objects.create(
        subscription=sub,
        event_type="subscription.created",
        from_status="",
        to_status=sub.status,
        actor_label=getattr(actor_user, "email", "") or "",
    )
    log_event(
        action="subscriptions.subscription_created",
        actor_user=actor_user,
        merchant=merchant,
        environment=environment,
        target_type="subscription",
        target_id=str(sub.id),
        metadata={
            "customer_id": str(customer.id),
            "plan_id": str(plan.id),
            "price_version_id": str(pv.id),
            "quantity": quantity,
        },
        request=request,
    )
    from apps.events.services.create_event import emit as _emit_event

    _emit_event(
        merchant=merchant,
        environment=environment,
        event_type="subscription.created",
        aggregate_type="subscription",
        aggregate_id=str(sub.id),
        payload={
            "subscription_id": str(sub.id),
            "customer_id": str(customer.id),
            "plan_id": str(plan.id),
            "price_version_id": str(pv.id),
            "status": sub.status,
            "quantity": quantity,
        },
        actor_user=actor_user,
        request=request,
    )
    return sub
