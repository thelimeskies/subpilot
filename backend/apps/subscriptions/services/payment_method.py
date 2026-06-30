"""Subscription payment-method mutations."""
from __future__ import annotations

from apps.audit.services.log_event import log_event
from apps.common.db import atomic_with_retry
from apps.common.exceptions import ServiceError
from apps.customers.models import PaymentMethod

from ..models import Subscription, SubscriptionEvent


@atomic_with_retry
def set_subscription_payment_method(
    *,
    subscription: Subscription,
    payment_method: PaymentMethod,
    actor_user=None,
    request=None,
) -> Subscription:
    subscription.refresh_from_db()
    if payment_method.customer_id != subscription.customer_id:
        raise ServiceError("Payment method does not belong to this subscription customer.")
    if payment_method.merchant_id != subscription.merchant_id or payment_method.environment_id != subscription.environment_id:
        raise ServiceError("Payment method does not belong to this tenant.")
    if payment_method.status != PaymentMethod.Status.ACTIVE:
        raise ServiceError("Only active payment methods can be used for subscriptions.")

    previous_id = str(subscription.default_payment_method_id) if subscription.default_payment_method_id else ""
    subscription.default_payment_method = payment_method
    subscription.metadata = {
        **(subscription.metadata or {}),
        "last_payment_method_change": {
            "previous_payment_method_id": previous_id,
            "payment_method_id": str(payment_method.id),
            "brand": payment_method.brand,
            "last4": payment_method.last4,
        },
    }
    subscription.save(update_fields=["default_payment_method", "metadata", "updated_at"])

    SubscriptionEvent.objects.create(
        subscription=subscription,
        event_type="subscription.payment_method_changed",
        from_status=subscription.status,
        to_status=subscription.status,
        actor_label=getattr(actor_user, "email", "") or "",
        metadata={
            "previous_payment_method_id": previous_id,
            "payment_method_id": str(payment_method.id),
        },
    )
    log_event(
        action="subscriptions.payment_method_changed",
        actor_user=actor_user,
        merchant=subscription.merchant,
        environment=subscription.environment,
        target_type="subscription",
        target_id=str(subscription.id),
        metadata={
            "previous_payment_method_id": previous_id,
            "payment_method_id": str(payment_method.id),
            "customer_id": str(subscription.customer_id),
        },
        request=request,
    )

    from apps.events.services.create_event import emit as _emit_event

    _emit_event(
        merchant=subscription.merchant,
        environment=subscription.environment,
        event_type="subscription.updated",
        aggregate_type="subscription",
        aggregate_id=str(subscription.id),
        payload={
            "subscription_id": str(subscription.id),
            "payment_method_id": str(payment_method.id),
            "change": "payment_method_changed",
        },
        actor_user=actor_user,
        request=request,
    )
    return subscription
