"""Service: create_price_version.

Closes off the prior active price version (sets ``active_to``) and opens a new
one. The Plan must already exist; the price version contract is enforced
via the partial unique constraint ``uniq_active_priceversion_per_plan``.
"""
from __future__ import annotations

from django.utils import timezone

from apps.audit.services.log_event import log_event
from apps.common.db import atomic_with_retry
from apps.common.exceptions import ServiceError

from ..models import Plan, PriceVersion


@atomic_with_retry
def create_price_version(
    *,
    plan: Plan,
    amount_minor: int,
    currency: str,
    interval_unit: str,
    interval_count: int = 1,
    setup_fee_minor: int = 0,
    actor_user=None,
    request=None,
) -> PriceVersion:
    if amount_minor <= 0:
        raise ServiceError("amount_minor must be positive.")
    if interval_count <= 0:
        raise ServiceError("interval_count must be positive.")
    if interval_unit not in dict(PriceVersion.IntervalUnit.choices):
        raise ServiceError("Unsupported interval_unit.")
    currency = (currency or "").upper().strip()
    if len(currency) != 3:
        raise ServiceError("currency must be a 3-letter ISO code.")

    now = timezone.now()
    PriceVersion.objects.select_for_update().filter(
        plan=plan, active_to__isnull=True
    ).update(active_to=now)

    pv = PriceVersion.objects.create(
        plan=plan,
        amount_minor=amount_minor,
        currency=currency,
        interval_unit=interval_unit,
        interval_count=interval_count,
        setup_fee_minor=setup_fee_minor,
        active_from=now,
        active_to=None,
    )
    log_event(
        action="catalog.price_version_created",
        actor_user=actor_user,
        merchant=plan.merchant,
        environment=plan.environment,
        target_type="price_version",
        target_id=str(pv.id),
        metadata={
            "plan_id": str(plan.id),
            "amount_minor": amount_minor,
            "currency": currency,
            "interval": f"{interval_count}{interval_unit}",
        },
        request=request,
    )
    return pv
