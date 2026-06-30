"""Catalog DRF serializers."""
from __future__ import annotations

from rest_framework import serializers

from .models import Plan, PlanFeature, PriceVersion, Product
from .selectors import active_price_version


class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ("id", "name", "description", "status", "metadata", "created_at", "updated_at")
        read_only_fields = ("id", "status", "created_at", "updated_at")


class PriceVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PriceVersion
        fields = (
            "id",
            "amount_minor",
            "currency",
            "interval_unit",
            "interval_count",
            "setup_fee_minor",
            "active_from",
            "active_to",
        )
        read_only_fields = ("id", "active_from", "active_to")


class PlanFeatureSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlanFeature
        fields = ("id", "label", "detail", "sort_order")
        read_only_fields = ("id",)


class PlanSerializer(serializers.ModelSerializer):
    product_id = serializers.UUIDField(source="product.id", read_only=True)
    product_name = serializers.CharField(source="product.name", read_only=True)
    features = PlanFeatureSerializer(many=True, read_only=True)
    active_price = serializers.SerializerMethodField()

    class Meta:
        model = Plan
        fields = (
            "id",
            "product_id",
            "product_name",
            "name",
            "description",
            "status",
            "trial_days",
            "proration_policy",
            "cancellation_policy",
            "tokenized_renewal",
            "metadata",
            "features",
            "active_price",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "product_id",
            "product_name",
            "status",
            "features",
            "active_price",
            "created_at",
            "updated_at",
        )

    def get_active_price(self, plan: Plan) -> dict | None:
        pv = active_price_version(plan)
        if pv is None:
            return None
        return PriceVersionSerializer(pv).data


# --- Write payloads -----------------------------------------------------------


class CreateProductPayload(serializers.Serializer):
    name = serializers.CharField(max_length=200)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    metadata = serializers.JSONField(required=False, default=dict)


class CreatePlanPayload(serializers.Serializer):
    product_id = serializers.UUIDField()
    name = serializers.CharField(max_length=200)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    trial_days = serializers.IntegerField(min_value=0, default=0)
    proration_policy = serializers.ChoiceField(
        choices=Plan.ProrationPolicy.choices, default=Plan.ProrationPolicy.PRORATE
    )
    cancellation_policy = serializers.ChoiceField(
        choices=Plan.CancellationPolicy.choices,
        default=Plan.CancellationPolicy.AT_PERIOD_END,
    )
    tokenized_renewal = serializers.BooleanField(default=True)
    metadata = serializers.JSONField(required=False, default=dict)


class CreatePriceVersionPayload(serializers.Serializer):
    amount_minor = serializers.IntegerField(min_value=1)
    currency = serializers.CharField(max_length=3)
    interval_unit = serializers.ChoiceField(choices=PriceVersion.IntervalUnit.choices)
    interval_count = serializers.IntegerField(min_value=1, default=1)
    setup_fee_minor = serializers.IntegerField(min_value=0, default=0)


class ClonePlanPayload(serializers.Serializer):
    new_name = serializers.CharField(max_length=200)
