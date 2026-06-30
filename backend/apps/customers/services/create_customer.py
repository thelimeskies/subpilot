"""Service: create_customer."""
from __future__ import annotations

from django.db import IntegrityError

from apps.audit.services.log_event import log_event
from apps.common.db import atomic_with_retry
from apps.common.exceptions import ConflictError, ServiceError

from ..models import Customer


@atomic_with_retry
def create_customer(
    *,
    merchant,
    environment,
    email: str,
    name: str = "",
    phone: str = "",
    external_id: str = "",
    metadata: dict | None = None,
    actor_user=None,
    request=None,
) -> Customer:
    email = (email or "").strip().lower()
    if not email or "@" not in email:
        raise ServiceError("A valid email is required.")
    try:
        customer = Customer.objects.create(
            merchant=merchant,
            environment=environment,
            email=email,
            name=name,
            phone=phone,
            external_id=external_id,
            status=Customer.Status.ACTIVE,
            metadata=metadata or {},
        )
    except IntegrityError:
        raise ConflictError("A customer with that external_id already exists.")

    log_event(
        action="customers.customer_created",
        actor_user=actor_user,
        merchant=merchant,
        environment=environment,
        target_type="customer",
        target_id=str(customer.id),
        metadata={"email": customer.email, "external_id": customer.external_id},
        request=request,
    )
    return customer
