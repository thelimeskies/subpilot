"""Catalog selectors: read-only query composition."""
from __future__ import annotations

from django.db.models import QuerySet

from .models import Plan, PriceVersion, Product


def products_for(merchant, environment) -> QuerySet[Product]:
    return Product.objects.filter(merchant=merchant, environment=environment)


def plans_for(merchant, environment) -> QuerySet[Plan]:
    return (
        Plan.objects.filter(merchant=merchant, environment=environment)
        .select_related("product", "dunning_policy")
        .prefetch_related("features", "price_versions")
    )


def active_price_version(plan: Plan) -> PriceVersion | None:
    return (
        PriceVersion.objects.filter(plan=plan, active_to__isnull=True)
        .order_by("-active_from")
        .first()
    )
