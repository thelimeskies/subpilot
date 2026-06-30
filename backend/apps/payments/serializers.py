"""Payments serializers."""
from __future__ import annotations

from django.db.models import Sum
from rest_framework import serializers

from .models import BalanceTransaction, PaymentAttempt, ProcessorEvent


class PaymentAttemptSerializer(serializers.ModelSerializer):
    failure_category = serializers.SerializerMethodField()
    refunded_at = serializers.SerializerMethodField()
    refunded_amount_minor = serializers.SerializerMethodField()
    refund_reason = serializers.SerializerMethodField()

    class Meta:
        model = PaymentAttempt
        fields = [
            "id",
            "invoice",
            "payment_method",
            "attempt_number",
            "status",
            "amount_minor",
            "currency",
            "failure_code",
            "failure_message",
            "failure_category",
            "refunded_at",
            "refunded_amount_minor",
            "refund_reason",
            "processor_reference",
            "next_retry_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_failure_category(self, obj: PaymentAttempt) -> str:
        from .adapters import classify_failure
        if obj.status != PaymentAttempt.Status.FAILED or not obj.failure_code:
            return ""
        return classify_failure(obj.failure_code)

    def _refund_metadata(self, obj: PaymentAttempt) -> dict:
        refund_qs = obj.balance_transactions.filter(type=BalanceTransaction.Type.REFUND)
        refunded_minor = abs(refund_qs.aggregate(total=Sum("signed_amount_minor"))["total"] or 0)
        if refunded_minor <= 0:
            return {}
        latest = refund_qs.order_by("-created_at").first()
        latest_metadata = latest.metadata if latest else {}
        return {
            "refunded_at": latest.created_at.isoformat() if latest else None,
            "refunded_amount_minor": refunded_minor,
            "refund_reason": latest_metadata.get("reason", "") if isinstance(latest_metadata, dict) else "",
        }

    def get_refunded_at(self, obj: PaymentAttempt) -> str | None:
        return self._refund_metadata(obj).get("refunded_at")

    def get_refunded_amount_minor(self, obj: PaymentAttempt) -> int:
        value = self._refund_metadata(obj).get("refunded_amount_minor")
        return int(value or 0)

    def get_refund_reason(self, obj: PaymentAttempt) -> str:
        return str(self._refund_metadata(obj).get("refund_reason") or "")


class ProcessorEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProcessorEvent
        fields = [
            "id",
            "provider",
            "provider_event_id",
            "processor_reference",
            "event_type",
            "payload",
            "received_at",
            "processed_at",
        ]
        read_only_fields = fields


class ChargeInvoicePayloadSerializer(serializers.Serializer):
    payment_method_id = serializers.UUIDField(required=False, allow_null=True)
    adapter = serializers.CharField(required=False, allow_blank=True)


class RefundPaymentPayloadSerializer(serializers.Serializer):
    amount_minor = serializers.IntegerField(required=False, min_value=1)
    reason = serializers.CharField(required=False, allow_blank=True, default="", max_length=400)
    full = serializers.BooleanField(required=False, default=True)


class WebhookAckSerializer(serializers.Serializer):
    received = serializers.BooleanField()
    event_id = serializers.CharField(allow_blank=True)
