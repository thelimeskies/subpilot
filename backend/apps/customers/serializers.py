"""Customers DRF serializers.

The ``token`` / ``token_encrypted`` fields are NEVER exposed in any
serializer. The portal session plaintext token is returned only at creation
time as a top-level ``token`` field (see ``PortalSessionCreateResponse``).
"""
from __future__ import annotations

from rest_framework import serializers

from .models import Customer, PaymentMethod, PortalSession


class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = (
            "id",
            "external_id",
            "email",
            "name",
            "phone",
            "status",
            "metadata",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "status", "created_at", "updated_at")


class PaymentMethodSerializer(serializers.ModelSerializer):
    """Serializer for ``PaymentMethod``. NEVER exposes the token."""

    class Meta:
        model = PaymentMethod
        fields = (
            "id",
            "customer",
            "provider",
            "brand",
            "last4",
            "exp_month",
            "exp_year",
            "status",
            "is_default",
            "fingerprint",
            "metadata",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "customer",
            "status",
            "is_default",
            "fingerprint",
            "created_at",
            "updated_at",
        )


class PortalSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PortalSession
        fields = (
            "id",
            "customer",
            "subscription",
            "invoice",
            "allowed_actions",
            "return_url",
            "expires_at",
            "used_at",
            "created_at",
        )
        read_only_fields = (
            "id",
            "customer",
            "expires_at",
            "used_at",
            "created_at",
        )


# --- Write payloads -----------------------------------------------------------


class CreateCustomerPayload(serializers.Serializer):
    email = serializers.EmailField()
    name = serializers.CharField(required=False, allow_blank=True, default="", max_length=200)
    phone = serializers.CharField(required=False, allow_blank=True, default="", max_length=32)
    external_id = serializers.CharField(
        required=False, allow_blank=True, default="", max_length=128
    )
    metadata = serializers.JSONField(required=False, default=dict)


class UpdateCustomerPayload(serializers.Serializer):
    email = serializers.EmailField(required=False)
    name = serializers.CharField(required=False, allow_blank=True, max_length=200)
    phone = serializers.CharField(required=False, allow_blank=True, max_length=32)
    external_id = serializers.CharField(required=False, allow_blank=True, max_length=128)
    status = serializers.ChoiceField(choices=Customer.Status.choices, required=False)
    metadata = serializers.JSONField(required=False)


class MergeCustomerPayload(serializers.Serializer):
    target_customer_id = serializers.UUIDField()


class AttachPaymentMethodPayload(serializers.Serializer):
    provider = serializers.ChoiceField(choices=PaymentMethod.Provider.choices)
    token = serializers.CharField(write_only=True, max_length=512)
    brand = serializers.CharField(required=False, allow_blank=True, default="", max_length=32)
    last4 = serializers.CharField(required=False, allow_blank=True, default="", max_length=4)
    exp_month = serializers.IntegerField(required=False, allow_null=True, min_value=1, max_value=12)
    exp_year = serializers.IntegerField(required=False, allow_null=True, min_value=2000)
    fingerprint = serializers.CharField(
        required=False, allow_blank=True, default="", max_length=128
    )
    set_default = serializers.BooleanField(default=False)
    metadata = serializers.JSONField(required=False, default=dict)


class CreatePortalSessionPayload(serializers.Serializer):
    subscription_id = serializers.UUIDField(required=False, allow_null=True)
    invoice_id = serializers.UUIDField(required=False, allow_null=True)
    send_email = serializers.BooleanField(required=False, default=False)
    allowed_actions = serializers.ListField(
        child=serializers.CharField(max_length=64), required=False, allow_empty=True
    )
    return_url = serializers.URLField(required=False, allow_blank=True, default="", max_length=500)
    ttl_minutes = serializers.IntegerField(required=False, min_value=1, max_value=24 * 60)


class PortalSessionCreateResponseSerializer(serializers.Serializer):
    """Response shape returned exactly once at portal-session creation."""

    session = PortalSessionSerializer()
    token = serializers.CharField()
    url = serializers.URLField()
    email_queued = serializers.BooleanField()
