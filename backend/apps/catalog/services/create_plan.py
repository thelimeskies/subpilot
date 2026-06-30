"""Service: create_plan (in DRAFT status; activated separately)."""
from __future__ import annotations

from django.db import IntegrityError

from apps.audit.services.log_event import log_event
from apps.common.db import atomic_with_retry
from apps.common.exceptions import ConflictError, ServiceError

from ..models import Plan, Product


@atomic_with_retry
def create_plan(
    *,
    merchant,
    environment,
    product: Product,
    name: str,
    description: str = "",
    trial_days: int = 0,
    proration_policy: str = Plan.ProrationPolicy.PRORATE,
    cancellation_policy: str = Plan.CancellationPolicy.AT_PERIOD_END,
    tokenized_renewal: bool = True,
    dunning_policy=None,
    metadata: dict | None = None,
    actor_user=None,
    request=None,
) -> Plan:
    """Create a draft Plan under ``product``. Validate cross-tenant boundary."""
    if product.merchant_id != merchant.id or product.environment_id != environment.id:
        raise ServiceError("Product does not belong to this merchant/environment.")
    if not name or not name.strip():
        raise ServiceError("Plan name is required.")
    if trial_days < 0:
        raise ServiceError("trial_days must be non-negative.")

    try:
        plan = Plan.objects.create(
            merchant=merchant,
            environment=environment,
            product=product,
            name=name.strip(),
            description=description,
            status=Plan.Status.DRAFT,
            trial_days=trial_days,
            proration_policy=proration_policy,
            cancellation_policy=cancellation_policy,
            tokenized_renewal=tokenized_renewal,
            dunning_policy=dunning_policy,
            metadata=metadata or {},
        )
    except IntegrityError:
        raise ConflictError("A plan with that name already exists for this product.")

    log_event(
        action="catalog.plan_created",
        actor_user=actor_user,
        merchant=merchant,
        environment=environment,
        target_type="plan",
        target_id=str(plan.id),
        metadata={"name": plan.name, "product_id": str(product.id)},
        request=request,
    )
    return plan
