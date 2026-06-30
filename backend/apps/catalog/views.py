"""Catalog REST views: Products, Plans, PriceVersions."""
from __future__ import annotations

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.permissions import HasCapability
from apps.common.exceptions import TenantMismatch
from apps.common.permissions import HasTenantContext
from apps.common.viewsets import TenantScopedViewSet

from .models import Plan, PriceVersion, Product
from .selectors import plans_for, products_for
from .serializers import (
    ClonePlanPayload,
    CreatePlanPayload,
    CreatePriceVersionPayload,
    CreateProductPayload,
    PlanSerializer,
    PriceVersionSerializer,
    ProductSerializer,
)
from .services.create_plan import create_plan
from .services.create_price_version import create_price_version
from .services.create_product import create_product
from .services.plan_lifecycle import activate_plan, archive_plan, clone_plan


class ProductViewSet(TenantScopedViewSet):
    serializer_class = ProductSerializer
    queryset = Product.objects.all()

    def get_base_queryset(self):
        return products_for(self.request.merchant, self.request.environment)

    def get_permissions(self):
        if self.action in {"list", "retrieve"}:
            return [IsAuthenticated(), HasTenantContext()]
        return [IsAuthenticated(), HasTenantContext(), HasCapability("create_product")()]

    def create(self, request, *args, **kwargs):
        s = CreateProductPayload(data=request.data)
        s.is_valid(raise_exception=True)
        product = create_product(
            merchant=request.merchant,
            environment=request.environment,
            name=s.validated_data["name"],
            description=s.validated_data.get("description", ""),
            metadata=s.validated_data.get("metadata") or {},
            actor_user=request.user,
            request=request,
        )
        return Response(ProductSerializer(product).data, status=status.HTTP_201_CREATED)


class PlanViewSet(TenantScopedViewSet):
    serializer_class = PlanSerializer
    queryset = Plan.objects.all()

    def get_base_queryset(self):
        return plans_for(self.request.merchant, self.request.environment)

    def get_permissions(self):
        if self.action in {"list", "retrieve"}:
            return [IsAuthenticated(), HasTenantContext()]
        if self.action in {"activate", "archive"}:
            return [IsAuthenticated(), HasTenantContext(), HasCapability("activate_archive_plan")()]
        return [IsAuthenticated(), HasTenantContext(), HasCapability("create_plan")()]

    def create(self, request, *args, **kwargs):
        s = CreatePlanPayload(data=request.data)
        s.is_valid(raise_exception=True)
        product = get_object_or_404(
            Product,
            id=s.validated_data["product_id"],
            merchant=request.merchant,
            environment=request.environment,
        )
        plan = create_plan(
            merchant=request.merchant,
            environment=request.environment,
            product=product,
            name=s.validated_data["name"],
            description=s.validated_data.get("description", ""),
            trial_days=s.validated_data.get("trial_days", 0),
            proration_policy=s.validated_data.get("proration_policy"),
            cancellation_policy=s.validated_data.get("cancellation_policy"),
            tokenized_renewal=s.validated_data.get("tokenized_renewal", True),
            metadata=s.validated_data.get("metadata") or {},
            actor_user=request.user,
            request=request,
        )
        return Response(PlanSerializer(plan).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def activate(self, request, pk=None):
        plan = self.get_object()
        plan = activate_plan(plan=plan, actor_user=request.user, request=request)
        return Response(PlanSerializer(plan).data)

    @action(detail=True, methods=["post"])
    def archive(self, request, pk=None):
        plan = self.get_object()
        plan = archive_plan(plan=plan, actor_user=request.user, request=request)
        return Response(PlanSerializer(plan).data)

    @action(detail=True, methods=["post"])
    def clone(self, request, pk=None):
        plan = self.get_object()
        s = ClonePlanPayload(data=request.data)
        s.is_valid(raise_exception=True)
        cloned = clone_plan(
            plan=plan,
            new_name=s.validated_data["new_name"],
            actor_user=request.user,
            request=request,
        )
        return Response(PlanSerializer(cloned).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="price-versions")
    def add_price_version(self, request, pk=None):
        plan = self.get_object()
        s = CreatePriceVersionPayload(data=request.data)
        s.is_valid(raise_exception=True)
        pv = create_price_version(
            plan=plan,
            amount_minor=s.validated_data["amount_minor"],
            currency=s.validated_data["currency"],
            interval_unit=s.validated_data["interval_unit"],
            interval_count=s.validated_data.get("interval_count", 1),
            setup_fee_minor=s.validated_data.get("setup_fee_minor", 0),
            actor_user=request.user,
            request=request,
        )
        return Response(PriceVersionSerializer(pv).data, status=status.HTTP_201_CREATED)


class PriceVersionListView(TenantScopedViewSet):
    """Read-only listing of all price versions for the tenant (debugging aid)."""

    serializer_class = PriceVersionSerializer
    queryset = PriceVersion.objects.all()
    http_method_names = ["get", "head", "options"]

    def get_base_queryset(self):
        return PriceVersion.objects.filter(
            plan__merchant=self.request.merchant,
            plan__environment=self.request.environment,
        ).select_related("plan")

    def get_queryset(self):
        request = self.request
        if getattr(request, "merchant", None) is None or getattr(request, "environment", None) is None:
            return PriceVersion.objects.none()
        return self.get_base_queryset()

    def get_object(self):
        obj = super(TenantScopedViewSet, self).get_object()
        if (
            obj.plan.merchant_id != self.request.merchant.id
            or obj.plan.environment_id != self.request.environment.id
        ):
            raise TenantMismatch()
        return obj
