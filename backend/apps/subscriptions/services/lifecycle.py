"""Pause / resume / cancel / mark_past_due services for subscriptions."""
from __future__ import annotations

from django.utils import timezone

from apps.audit.services.log_event import log_event
from apps.common.db import atomic_with_retry
from apps.common.exceptions import ServiceError
from apps.events.services.create_event import emit as _emit_event

from ..models import Subscription
from ..state_machine import S, transition


def _emit_sub(subscription: Subscription, event_type: str, **extra) -> None:
    payload = {
        "subscription_id": str(subscription.id),
        "customer_id": str(subscription.customer_id),
        "plan_id": str(subscription.plan_id) if subscription.plan_id else "",
        "status": subscription.status,
        **extra,
    }
    _emit_event(
        merchant=subscription.merchant,
        environment=subscription.environment,
        event_type=event_type,
        aggregate_type="subscription",
        aggregate_id=str(subscription.id),
        payload=payload,
    )


@atomic_with_retry
def pause_subscription(
    *,
    subscription: Subscription,
    reason: str = "",
    resume_at=None,
    actor_user=None,
    request=None,
) -> Subscription:
    subscription.refresh_from_db()
    metadata = dict(subscription.metadata or {})
    if resume_at:
        metadata["resume_at"] = resume_at.isoformat()
    else:
        metadata.pop("resume_at", None)
    subscription.metadata = metadata
    subscription.save(update_fields=["metadata", "updated_at"])
    transition(
        subscription=subscription,
        target=S.PAUSED,
        event_type="subscription.paused",
        actor_label=getattr(actor_user, "email", "") or "",
        metadata={"reason": reason, "resume_at": resume_at.isoformat() if resume_at else None},
    )
    log_event(
        action="subscriptions.subscription_paused",
        actor_user=actor_user,
        merchant=subscription.merchant,
        environment=subscription.environment,
        target_type="subscription",
        target_id=str(subscription.id),
        metadata={"reason": reason, "resume_at": resume_at.isoformat() if resume_at else None},
        request=request,
    )
    _emit_sub(
        subscription,
        "subscription.paused",
        reason=reason,
        resume_at=resume_at.isoformat() if resume_at else None,
    )
    return subscription


@atomic_with_retry
def resume_subscription(
    *, subscription: Subscription, actor_user=None, request=None
) -> Subscription:
    subscription.refresh_from_db()
    if subscription.status != S.PAUSED:
        raise ServiceError("Only paused subscriptions can be resumed.")
    metadata = dict(subscription.metadata or {})
    metadata.pop("resume_at", None)
    subscription.metadata = metadata
    subscription.save(update_fields=["metadata", "updated_at"])
    transition(
        subscription=subscription,
        target=S.ACTIVE,
        event_type="subscription.resumed",
        actor_label=getattr(actor_user, "email", "") or "",
    )
    log_event(
        action="subscriptions.subscription_resumed",
        actor_user=actor_user,
        merchant=subscription.merchant,
        environment=subscription.environment,
        target_type="subscription",
        target_id=str(subscription.id),
        request=request,
    )
    _emit_sub(subscription, "subscription.resumed")
    return subscription


@atomic_with_retry
def cancel_subscription(
    *,
    subscription: Subscription,
    at_period_end: bool = True,
    reason: str = "",
    actor_user=None,
    request=None,
) -> Subscription:
    """Cancel a subscription.

    ``at_period_end=True`` (default) flips ``cancel_at_period_end`` so the
    subscription stays usable until ``current_period_end``; the periodic
    reconciler then flips it to ``canceled``. ``at_period_end=False`` cancels
    immediately.
    """
    subscription.refresh_from_db()
    now = timezone.now()
    if at_period_end and subscription.status in {
        S.ACTIVE,
        S.TRIALING,
        S.PAST_DUE,
    }:
        subscription.cancel_at_period_end = True
        subscription.save(update_fields=["cancel_at_period_end", "updated_at"])
        # No state change yet; the cron flips status to canceled at period end.
        log_event(
            action="subscriptions.subscription_cancel_scheduled",
            actor_user=actor_user,
            merchant=subscription.merchant,
            environment=subscription.environment,
            target_type="subscription",
            target_id=str(subscription.id),
            metadata={"reason": reason},
            request=request,
        )
        _emit_sub(subscription, "subscription.canceling", reason=reason)
        return subscription

    subscription.canceled_at = now
    subscription.save(update_fields=["canceled_at", "updated_at"])
    transition(
        subscription=subscription,
        target=S.CANCELED,
        event_type="subscription.canceled",
        actor_label=getattr(actor_user, "email", "") or "",
        metadata={"reason": reason},
    )
    log_event(
        action="subscriptions.subscription_canceled",
        actor_user=actor_user,
        merchant=subscription.merchant,
        environment=subscription.environment,
        target_type="subscription",
        target_id=str(subscription.id),
        metadata={"reason": reason, "at_period_end": False},
        request=request,
    )
    _emit_sub(subscription, "subscription.canceled", reason=reason)
    return subscription


@atomic_with_retry
def mark_past_due(
    *, subscription: Subscription, invoice_id: str | None = None, actor_user=None, request=None
) -> Subscription:
    subscription.refresh_from_db()
    transition(
        subscription=subscription,
        target=S.PAST_DUE,
        event_type="subscription.past_due",
        actor_label=getattr(actor_user, "email", "") or "system",
        metadata={"invoice_id": invoice_id} if invoice_id else {},
    )
    log_event(
        action="subscriptions.subscription_past_due",
        actor_user=actor_user,
        merchant=subscription.merchant,
        environment=subscription.environment,
        target_type="subscription",
        target_id=str(subscription.id),
        metadata={"invoice_id": invoice_id} if invoice_id else {},
        request=request,
    )
    _emit_sub(
        subscription,
        "subscription.past_due",
        invoice_id=str(invoice_id) if invoice_id else "",
    )
    return subscription


@atomic_with_retry
def mark_recovered(
    *, subscription: Subscription, actor_user=None, request=None
) -> Subscription:
    """``past_due`` -> ``active`` after a successful retry."""
    subscription.refresh_from_db()
    if subscription.status != S.PAST_DUE:
        raise ServiceError("Only past_due subscriptions can be recovered.")
    transition(
        subscription=subscription,
        target=S.ACTIVE,
        event_type="subscription.recovered",
        actor_label=getattr(actor_user, "email", "") or "system",
    )
    log_event(
        action="subscriptions.subscription_recovered",
        actor_user=actor_user,
        merchant=subscription.merchant,
        environment=subscription.environment,
        target_type="subscription",
        target_id=str(subscription.id),
        request=request,
    )
    _emit_sub(subscription, "subscription.activated", recovered=True)
    return subscription
