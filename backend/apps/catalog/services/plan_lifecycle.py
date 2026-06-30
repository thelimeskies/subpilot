"""Services: activate_plan, archive_plan, clone_plan."""
from __future__ import annotations

from apps.audit.services.log_event import log_event
from apps.common.db import atomic_with_retry
from apps.common.exceptions import ServiceError

from ..models import Plan, PlanFeature, PriceVersion


@atomic_with_retry
def activate_plan(*, plan: Plan, actor_user=None, request=None) -> Plan:
    """Activate a draft plan; require at least one open-ended PriceVersion."""
    if plan.status == Plan.Status.ACTIVE:
        return plan
    if plan.status == Plan.Status.ARCHIVED:
        raise ServiceError("Archived plans cannot be re-activated. Clone the plan instead.")
    has_active_price = PriceVersion.objects.filter(plan=plan, active_to__isnull=True).exists()
    if not has_active_price:
        raise ServiceError("Plan needs an active price version before activation.")

    plan.status = Plan.Status.ACTIVE
    plan.save(update_fields=["status", "updated_at"])
    log_event(
        action="catalog.plan_activated",
        actor_user=actor_user,
        merchant=plan.merchant,
        environment=plan.environment,
        target_type="plan",
        target_id=str(plan.id),
        request=request,
    )
    return plan


@atomic_with_retry
def archive_plan(*, plan: Plan, actor_user=None, request=None) -> Plan:
    """Archive a plan. Existing subscriptions on this plan are unaffected."""
    if plan.status == Plan.Status.ARCHIVED:
        return plan
    plan.status = Plan.Status.ARCHIVED
    plan.save(update_fields=["status", "updated_at"])
    log_event(
        action="catalog.plan_archived",
        actor_user=actor_user,
        merchant=plan.merchant,
        environment=plan.environment,
        target_type="plan",
        target_id=str(plan.id),
        request=request,
    )
    return plan


@atomic_with_retry
def clone_plan(
    *,
    plan: Plan,
    new_name: str,
    actor_user=None,
    request=None,
) -> Plan:
    """Clone a plan including features and the currently-active price version."""
    if not new_name or not new_name.strip():
        raise ServiceError("new_name is required.")

    cloned = Plan.objects.create(
        merchant=plan.merchant,
        environment=plan.environment,
        product=plan.product,
        name=new_name.strip(),
        description=plan.description,
        status=Plan.Status.DRAFT,
        trial_days=plan.trial_days,
        proration_policy=plan.proration_policy,
        cancellation_policy=plan.cancellation_policy,
        tokenized_renewal=plan.tokenized_renewal,
        dunning_policy=plan.dunning_policy,
        metadata={**(plan.metadata or {}), "cloned_from": str(plan.id)},
    )

    # Copy features (sort_order preserved).
    for feat in plan.features.all():
        PlanFeature.objects.create(
            plan=cloned,
            label=feat.label,
            detail=feat.detail,
            sort_order=feat.sort_order,
        )

    # Copy the currently-active price version (if any).
    active_pv = PriceVersion.objects.filter(plan=plan, active_to__isnull=True).first()
    if active_pv:
        from .create_price_version import create_price_version

        create_price_version(
            plan=cloned,
            amount_minor=active_pv.amount_minor,
            currency=active_pv.currency,
            interval_unit=active_pv.interval_unit,
            interval_count=active_pv.interval_count,
            setup_fee_minor=active_pv.setup_fee_minor,
            actor_user=actor_user,
            request=request,
        )

    log_event(
        action="catalog.plan_cloned",
        actor_user=actor_user,
        merchant=plan.merchant,
        environment=plan.environment,
        target_type="plan",
        target_id=str(cloned.id),
        metadata={"source_plan_id": str(plan.id)},
        request=request,
    )
    return cloned
