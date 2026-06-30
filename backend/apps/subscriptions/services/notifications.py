"""Subscription customer notification helpers."""
from __future__ import annotations

from apps.audit.services.log_event import log_event
from apps.common.email import format_email_date, merchant_email_context, send_templated_email

from ..models import Subscription


def send_subscription_canceled_email(
    *, subscription: Subscription, portal_link: str = "", actor_user=None, request=None
) -> dict:
    subscription = (
        Subscription.objects.select_related(
            "customer",
            "merchant",
            "environment",
            "plan",
        )
        .get(pk=subscription.pk)
    )
    customer = subscription.customer
    subject = f"Your {subscription.plan.name} subscription has been canceled"
    send_templated_email(
        to=customer.email,
        subject=subject,
        template="subscription_canceled",
        context=merchant_email_context(
            subscription.merchant,
            email_label="Subscription status",
            recipient_name=customer.name or customer.email,
            plan_name=subscription.plan.name,
            canceled_at=format_email_date(subscription.canceled_at),
            portal_link=portal_link,
        ),
    )
    log_event(
        action="subscriptions.cancellation_emailed",
        actor_user=actor_user,
        merchant=subscription.merchant,
        environment=subscription.environment,
        target_type="subscription",
        target_id=str(subscription.id),
        metadata={"recipient": customer.email, "plan": subscription.plan.name},
        request=request,
    )
    return {"ok": True, "recipient": customer.email, "subscription_id": str(subscription.id)}
