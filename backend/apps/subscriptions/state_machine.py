"""Subscription state machine.

A subscription's status moves through a finite set of transitions; every
transition is validated here before a service applies it. Each call writes a
``SubscriptionEvent`` row so the timeline is replayable.
"""
from __future__ import annotations

from typing import Iterable

from apps.common.exceptions import ServiceError

from .models import Subscription, SubscriptionEvent

S = Subscription.Status

# Allowed transitions: source -> set of valid targets.
_TRANSITIONS: dict[str, set[str]] = {
    S.INCOMPLETE: {S.TRIALING, S.ACTIVE, S.CANCELED, S.EXPIRED},
    S.TRIALING: {S.ACTIVE, S.PAST_DUE, S.CANCELED, S.PAUSED, S.EXPIRED},
    S.ACTIVE: {S.PAST_DUE, S.PAUSED, S.CANCELED, S.EXPIRED},
    S.PAST_DUE: {S.ACTIVE, S.CANCELED, S.EXPIRED, S.PAUSED},
    S.PAUSED: {S.ACTIVE, S.CANCELED, S.EXPIRED},
    S.CANCELED: set(),  # terminal
    S.EXPIRED: set(),  # terminal
}


def can_transition(current: str, target: str) -> bool:
    return target in _TRANSITIONS.get(current, set())


def assert_can_transition(current: str, target: str) -> None:
    if not can_transition(current, target):
        raise ServiceError(
            f"Invalid subscription transition {current!r} -> {target!r}."
        )


def allowed_targets(current: str) -> Iterable[str]:
    return tuple(_TRANSITIONS.get(current, set()))


def transition(
    *,
    subscription: Subscription,
    target: str,
    event_type: str,
    actor_label: str = "",
    metadata: dict | None = None,
) -> Subscription:
    """Validated state change; writes a ``SubscriptionEvent`` row."""
    assert_can_transition(subscription.status, target)
    from_status = subscription.status
    subscription.status = target
    subscription.save(update_fields=["status", "updated_at"])
    SubscriptionEvent.objects.create(
        subscription=subscription,
        event_type=event_type,
        from_status=from_status,
        to_status=target,
        actor_label=actor_label,
        metadata=metadata or {},
    )
    return subscription
