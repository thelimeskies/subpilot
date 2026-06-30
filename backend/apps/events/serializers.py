"""Events DRF serializers (no plaintext secrets).

The endpoint ``secret`` plaintext is only returned at create / rotate time
and is delivered out-of-band via the response of those endpoints.
"""
from __future__ import annotations

from rest_framework import serializers

from .models import WebhookDelivery, WebhookEndpoint, WebhookEvent


class WebhookEndpointSerializer(serializers.ModelSerializer):
    class Meta:
        model = WebhookEndpoint
        fields = (
            "id",
            "url",
            "description",
            "enabled",
            "event_filters",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")


class CreateWebhookEndpointPayload(serializers.Serializer):
    url = serializers.URLField(max_length=500)
    description = serializers.CharField(
        required=False, allow_blank=True, default="", max_length=400
    )
    event_filters = serializers.ListField(
        child=serializers.CharField(max_length=64), required=False, default=list
    )
    enabled = serializers.BooleanField(default=True)


class UpdateWebhookEndpointPayload(serializers.Serializer):
    url = serializers.URLField(required=False, max_length=500)
    description = serializers.CharField(
        required=False, allow_blank=True, max_length=400
    )
    event_filters = serializers.ListField(
        child=serializers.CharField(max_length=64), required=False
    )
    enabled = serializers.BooleanField(required=False)


class WebhookEndpointCreateResponseSerializer(serializers.Serializer):
    """Response shape returned exactly once when creating / rotating secrets."""

    endpoint = WebhookEndpointSerializer()
    secret = serializers.CharField()


class WebhookEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = WebhookEvent
        fields = (
            "id",
            "event_type",
            "aggregate_type",
            "aggregate_id",
            "payload",
            "occurred_at",
            "created_at",
        )
        read_only_fields = fields


class WebhookDeliverySerializer(serializers.ModelSerializer):
    class Meta:
        model = WebhookDelivery
        fields = (
            "id",
            "webhook_event",
            "endpoint",
            "status",
            "attempt_count",
            "last_status_code",
            "last_response_body",
            "next_attempt_at",
            "delivered_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields
