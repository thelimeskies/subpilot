"""Subscription note persistence."""
from __future__ import annotations

from apps.audit.services.log_event import log_event
from apps.common.db import atomic_with_retry

from ..models import Subscription, SubscriptionEvent


@atomic_with_retry
def add_subscription_note(
    *,
    subscription: Subscription,
    note: str,
    actor_user=None,
    request=None,
) -> Subscription:
    subscription.refresh_from_db()
    clean_note = note.strip()
    existing_notes = subscription.metadata.get("notes_history", []) if isinstance(subscription.metadata, dict) else []
    if not isinstance(existing_notes, list):
        existing_notes = []

    entry = {
        "note": clean_note,
        "actor": getattr(actor_user, "email", "") or "",
    }
    subscription.metadata = {
        **(subscription.metadata or {}),
        "notes": clean_note,
        "notes_history": [entry, *existing_notes][:20],
    }
    subscription.save(update_fields=["metadata", "updated_at"])

    SubscriptionEvent.objects.create(
        subscription=subscription,
        event_type="subscription.note_added",
        from_status=subscription.status,
        to_status=subscription.status,
        actor_label=getattr(actor_user, "email", "") or "",
        metadata={"note": clean_note},
    )
    log_event(
        action="subscriptions.note_added",
        actor_user=actor_user,
        merchant=subscription.merchant,
        environment=subscription.environment,
        target_type="subscription",
        target_id=str(subscription.id),
        metadata={"note": clean_note},
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
            "change": "note_added",
        },
        actor_user=actor_user,
        request=request,
    )
    return subscription
