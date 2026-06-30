"""Subscriptions selectors: read-only query composition."""
from __future__ import annotations

from django.db.models import QuerySet

from .models import Subscription, SubscriptionEvent, SubscriptionItem


def subscriptions_for(merchant, environment) -> QuerySet[Subscription]:
    return (
        Subscription.objects.filter(merchant=merchant, environment=environment)
        .select_related("customer", "plan", "default_payment_method")
    )


def items_for(subscription: Subscription) -> QuerySet[SubscriptionItem]:
    return SubscriptionItem.objects.filter(subscription=subscription).select_related(
        "price_version"
    )


def events_for(subscription: Subscription) -> QuerySet[SubscriptionEvent]:
    return SubscriptionEvent.objects.filter(subscription=subscription)
