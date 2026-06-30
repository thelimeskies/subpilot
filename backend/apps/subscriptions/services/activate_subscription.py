"""Service: activate_subscription.

Marks an `incomplete`/`trialing` subscription as `active`, sets the billing
anchor (= activation time), current period start/end (computed from the
active price version's interval), and trial_end if a trial was requested.
"""
from __future__ import annotations

from datetime import timedelta

from django.utils import timezone

from apps.audit.services.log_event import log_event
from apps.common.db import atomic_with_retry
from apps.common.exceptions import ServiceError
from apps.events.services.create_event import emit as _emit_event

from ..models import Subscription
from ..periods import compute_period_end
from ..state_machine import S, transition


@atomic_with_retry
def activate_subscription(
    *,
    subscription: Subscription,
    with_trial: bool = False,
    actor_user=None,
    request=None,
) -> Subscription:
    subscription.refresh_from_db()
    if subscription.status == S.ACTIVE:
        return subscription
    if subscription.status == S.TRIALING and with_trial:
        return subscription
    if subscription.status not in {S.INCOMPLETE, S.TRIALING}:
        raise ServiceError(
            f"Cannot activate subscription in status {subscription.status!r}."
        )
    item = subscription.items.filter(status="active").select_related("price_version").first()
    if item is None:
        raise ServiceError("Subscription has no active item.")

    now = timezone.now()
    subscription.billing_anchor = subscription.billing_anchor or now
    subscription.current_period_start = now
    subscription.current_period_end = compute_period_end(now, item.price_version)
    if with_trial and subscription.plan.trial_days > 0:
        subscription.trial_end = now + timedelta(days=subscription.plan.trial_days)
        subscription.status = S.TRIALING
    subscription.save(
        update_fields=[
            "billing_anchor",
            "current_period_start",
            "current_period_end",
            "trial_end",
            "status",
            "updated_at",
        ]
    )

    if subscription.status != S.TRIALING:
        transition(
            subscription=subscription,
            target=S.ACTIVE,
            event_type="subscription.activated",
            actor_label=getattr(actor_user, "email", "") or "",
        )

    log_event(
        action="subscriptions.subscription_activated",
        actor_user=actor_user,
        merchant=subscription.merchant,
        environment=subscription.environment,
        target_type="subscription",
        target_id=str(subscription.id),
        metadata={
            "with_trial": with_trial,
            "current_period_end": subscription.current_period_end.isoformat()
            if subscription.current_period_end
            else None,
        },
        request=request,
    )
    _emit_event(
        merchant=subscription.merchant,
        environment=subscription.environment,
        event_type=(
            "subscription.trialing" if subscription.status == S.TRIALING
            else "subscription.activated"
        ),
        aggregate_type="subscription",
        aggregate_id=str(subscription.id),
        payload={
            "subscription_id": str(subscription.id),
            "customer_id": str(subscription.customer_id),
            "plan_id": str(subscription.plan_id) if subscription.plan_id else "",
            "status": subscription.status,
            "current_period_start": (
                subscription.current_period_start.isoformat()
                if subscription.current_period_start else None
            ),
            "current_period_end": (
                subscription.current_period_end.isoformat()
                if subscription.current_period_end else None
            ),
        },
        actor_user=actor_user,
        request=request,
    )
    return subscription
