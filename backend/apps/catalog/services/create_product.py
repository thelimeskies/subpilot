"""Service: create_product."""
from __future__ import annotations

from django.db import IntegrityError

from apps.audit.services.log_event import log_event
from apps.common.db import atomic_with_retry
from apps.common.exceptions import ConflictError, ServiceError

from ..models import Product


@atomic_with_retry
def create_product(
    *,
    merchant,
    environment,
    name: str,
    description: str = "",
    metadata: dict | None = None,
    actor_user=None,
    request=None,
) -> Product:
    """Create a new active Product. Idempotent on (merchant, environment, name)."""
    if not name or not name.strip():
        raise ServiceError("Product name is required.")
    try:
        product = Product.objects.create(
            merchant=merchant,
            environment=environment,
            name=name.strip(),
            description=description,
            status=Product.Status.ACTIVE,
            metadata=metadata or {},
        )
    except IntegrityError:
        raise ConflictError("A product with that name already exists in this environment.")

    log_event(
        action="catalog.product_created",
        actor_user=actor_user,
        merchant=merchant,
        environment=environment,
        target_type="product",
        target_id=str(product.id),
        metadata={"name": product.name},
        request=request,
    )
    return product
