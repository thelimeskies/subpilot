"""Subscriptions DRF serializers."""
from __future__ import annotations

from rest_framework import serializers

from .models import Subscription, SubscriptionEvent, SubscriptionItem


class SubscriptionItemSerializer(serializers.ModelSerializer):
    price_version_id = serializers.UUIDField(source="price_version.id", read_only=True)
    amount_minor = serializers.IntegerField(source="price_version.amount_minor", read_only=True)
    currency = serializers.CharField(source="price_version.currency", read_only=True)
    interval_unit = serializers.CharField(
        source="price_version.interval_unit", read_only=True
    )
    interval_count = serializers.IntegerField(
        source="price_version.interval_count", read_only=True
    )

    class Meta:
        model = SubscriptionItem
        fields = (
            "id",
            "price_version_id",
            "amount_minor",
            "currency",
            "interval_unit",
            "interval_count",
            "quantity",
            "status",
            "created_at",
        )
        read_only_fields = fields


class SubscriptionEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionEvent
        fields = (
            "id",
            "event_type",
            "from_status",
            "to_status",
            "actor_label",
            "metadata",
            "occurred_at",
        )
        read_only_fields = fields


class SubscriptionSerializer(serializers.ModelSerializer):
    customer_id = serializers.UUIDField(source="customer.id", read_only=True)
    plan_id = serializers.UUIDField(source="plan.id", read_only=True)
    plan_name = serializers.CharField(source="plan.name", read_only=True)
    default_payment_method_id = serializers.UUIDField(source="default_payment_method.id", read_only=True)
    items = SubscriptionItemSerializer(many=True, read_only=True)

    class Meta:
        model = Subscription
        fields = (
            "id",
            "customer_id",
            "plan_id",
            "plan_name",
            "status",
            "billing_anchor",
            "current_period_start",
            "current_period_end",
            "trial_end",
            "cancel_at_period_end",
            "canceled_at",
            "default_payment_method_id",
            "items",
            "metadata",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


# --- Write payloads -----------------------------------------------------------


class CreateSubscriptionPayload(serializers.Serializer):
    customer_id = serializers.UUIDField()
    plan_id = serializers.UUIDField()
    quantity = serializers.IntegerField(min_value=1, default=1)
    default_payment_method_id = serializers.UUIDField(required=False, allow_null=True)
    metadata = serializers.JSONField(required=False, default=dict)


class CancelSubscriptionPayload(serializers.Serializer):
    at_period_end = serializers.BooleanField(default=True)
    reason = serializers.CharField(required=False, allow_blank=True, default="", max_length=400)


class PauseSubscriptionPayload(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, default="", max_length=400)
    resume_at = serializers.DateField(required=False, allow_null=True)


class ChangePlanPayload(serializers.Serializer):
    new_plan_id = serializers.UUIDField()


class ActivateSubscriptionPayload(serializers.Serializer):
    with_trial = serializers.BooleanField(default=False)


class SetSubscriptionPaymentMethodPayload(serializers.Serializer):
    payment_method_id = serializers.UUIDField()


class AddSubscriptionNotePayload(serializers.Serializer):
    note = serializers.CharField(max_length=2000, trim_whitespace=True)


class ApplySubscriptionCreditPayload(serializers.Serializer):
    amount_minor = serializers.IntegerField(min_value=1)
    note = serializers.CharField(required=False, allow_blank=True, default="", max_length=500)
