"""Subscription-level pending credits."""
from __future__ import annotations

from apps.audit.services.log_event import log_event
from apps.common.db import atomic_with_retry

from ..models import Subscription, SubscriptionEvent


def _active_currency(subscription: Subscription) -> str:
    item = (
        subscription.items.filter(status="active")
        .select_related("price_version")
        .first()
    )
    return item.price_version.currency if item else "NGN"


@atomic_with_retry
def apply_subscription_credit(
    *,
    subscription: Subscription,
    amount_minor: int,
    note: str = "",
    actor_user=None,
    request=None,
) -> Subscription:
    subscription.refresh_from_db()
    currency = _active_currency(subscription)
    existing = subscription.metadata.get("pending_credits", []) if isinstance(subscription.metadata, dict) else []
    if not isinstance(existing, list):
        existing = []

    entry = {
        "amount_minor": amount_minor,
        "currency": currency,
        "note": note.strip(),
        "actor": getattr(actor_user, "email", "") or "",
    }
    total = sum(
        credit.get("amount_minor", 0)
        for credit in existing
        if isinstance(credit, dict) and isinstance(credit.get("amount_minor"), int)
    ) + amount_minor
    subscription.metadata = {
        **(subscription.metadata or {}),
        "pending_credits": [entry, *existing][:20],
        "pending_credit_minor_total": total,
    }
    subscription.save(update_fields=["metadata", "updated_at"])

    metadata = {
        "amount_minor": amount_minor,
        "currency": currency,
        "note": note.strip(),
        "pending_credit_minor_total": total,
    }
    SubscriptionEvent.objects.create(
        subscription=subscription,
        event_type="subscription.credit_applied",
        from_status=subscription.status,
        to_status=subscription.status,
        actor_label=getattr(actor_user, "email", "") or "",
        metadata=metadata,
    )
    log_event(
        action="subscriptions.credit_applied",
        actor_user=actor_user,
        merchant=subscription.merchant,
        environment=subscription.environment,
        target_type="subscription",
        target_id=str(subscription.id),
        metadata=metadata,
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
            "change": "credit_applied",
            **metadata,
        },
        actor_user=actor_user,
        request=request,
    )
    return subscription
