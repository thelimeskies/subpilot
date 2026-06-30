"""Plan-change services for subscriptions: preview + apply.

A plan change replaces the active SubscriptionItem with one bound to the new
plan's active PriceVersion. When the subscription's plan has
``proration_policy=prorate``, we compute a credit for the unused portion of
the current period and a charge for the new plan covering the same window —
both expressed as proration ``InvoiceLineItem``s on the next renewal invoice
(deferred to ``apps.invoices.services.create_renewal_invoice``).

This service returns a small dict describing the planned changes; the actual
invoice line items are written when the next renewal invoice is generated.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

from django.utils import timezone

from apps.audit.services.log_event import log_event
from apps.catalog.models import Plan, PriceVersion
from apps.catalog.selectors import active_price_version
from apps.common.db import atomic_with_retry
from apps.common.exceptions import ServiceError

from ..models import Subscription, SubscriptionEvent, SubscriptionItem


@dataclass
class ChangePreview:
    current_plan_id: str
    new_plan_id: str
    current_price_version_id: str
    new_price_version_id: str
    proration_credit_minor: int
    proration_charge_minor: int
    net_minor: int
    currency: str
    effective_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _seconds_remaining(now: datetime, end: datetime | None) -> int:
    if end is None:
        return 0
    delta = (end - now).total_seconds()
    return max(0, int(delta))


def _seconds_total(start: datetime | None, end: datetime | None) -> int:
    if start is None or end is None:
        return 0
    delta = (end - start).total_seconds()
    return max(1, int(delta))  # avoid div-by-zero


def _proration_amounts(
    *,
    now: datetime,
    sub: Subscription,
    current_pv: PriceVersion,
    new_pv: PriceVersion,
) -> tuple[int, int]:
    """Return (credit_minor, charge_minor) for the unused portion of the period."""
    if sub.plan.proration_policy != Plan.ProrationPolicy.PRORATE:
        return 0, 0
    total = _seconds_total(sub.current_period_start, sub.current_period_end)
    remaining = _seconds_remaining(now, sub.current_period_end)
    if total == 0 or remaining == 0:
        return 0, 0
    credit = round(current_pv.amount_minor * remaining / total)
    charge = round(new_pv.amount_minor * remaining / total)
    return int(credit), int(charge)


def preview_change(
    *,
    subscription: Subscription,
    new_plan: Plan,
) -> ChangePreview:
    if new_plan.merchant_id != subscription.merchant_id or new_plan.environment_id != subscription.environment_id:
        raise ServiceError("Plan does not belong to this tenant.")
    if new_plan.status != Plan.Status.ACTIVE:
        raise ServiceError("Target plan must be active.")
    new_pv = active_price_version(new_plan)
    if new_pv is None:
        raise ServiceError("Target plan has no active price version.")
    item = (
        subscription.items.filter(status="active")
        .select_related("price_version")
        .first()
    )
    if item is None:
        raise ServiceError("Subscription has no active item.")
    current_pv = item.price_version
    if current_pv.currency != new_pv.currency:
        raise ServiceError("Cannot change between plans with different currencies.")

    now = timezone.now()
    credit, charge = _proration_amounts(
        now=now, sub=subscription, current_pv=current_pv, new_pv=new_pv
    )
    return ChangePreview(
        current_plan_id=str(subscription.plan_id),
        new_plan_id=str(new_plan.id),
        current_price_version_id=str(current_pv.id),
        new_price_version_id=str(new_pv.id),
        proration_credit_minor=credit,
        proration_charge_minor=charge,
        net_minor=charge - credit,
        currency=new_pv.currency,
        effective_at=now.isoformat(),
    )


@atomic_with_retry
def change_plan(
    *,
    subscription: Subscription,
    new_plan: Plan,
    actor_user=None,
    request=None,
) -> tuple[Subscription, ChangePreview]:
    subscription.refresh_from_db()
    preview = preview_change(subscription=subscription, new_plan=new_plan)

    new_pv = active_price_version(new_plan)
    assert new_pv is not None  # guarded by preview_change

    # Mark current item as removed; create a new active item.
    SubscriptionItem.objects.filter(
        subscription=subscription, status=SubscriptionItem.Status.ACTIVE
    ).update(status=SubscriptionItem.Status.REMOVED)
    SubscriptionItem.objects.create(
        subscription=subscription,
        price_version=new_pv,
        quantity=1,
        status=SubscriptionItem.Status.ACTIVE,
    )

    subscription.plan = new_plan
    subscription.metadata = {
        **(subscription.metadata or {}),
        "last_plan_change": preview.to_dict(),
    }
    subscription.save(update_fields=["plan", "metadata", "updated_at"])

    SubscriptionEvent.objects.create(
        subscription=subscription,
        event_type="subscription.plan_changed",
        from_status=subscription.status,
        to_status=subscription.status,
        actor_label=getattr(actor_user, "email", "") or "",
        metadata=preview.to_dict(),
    )
    log_event(
        action="subscriptions.subscription_plan_changed",
        actor_user=actor_user,
        merchant=subscription.merchant,
        environment=subscription.environment,
        target_type="subscription",
        target_id=str(subscription.id),
        metadata=preview.to_dict(),
        request=request,
    )
    from apps.events.services.create_event import emit as _emit_event

    _emit_event(
        merchant=subscription.merchant,
        environment=subscription.environment,
        event_type="subscription.changed",
        aggregate_type="subscription",
        aggregate_id=str(subscription.id),
        payload={
            "subscription_id": str(subscription.id),
            "new_plan_id": str(new_plan.id),
            "preview": preview.to_dict(),
        },
        actor_user=actor_user,
        request=request,
    )
    return subscription, preview
