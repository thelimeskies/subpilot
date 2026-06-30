"""Invoice DRF serializers."""
from __future__ import annotations

from rest_framework import serializers

from .models import CreditNote, Invoice, InvoiceLineItem


class InvoiceLineItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceLineItem
        fields = (
            "id",
            "type",
            "description",
            "amount_minor",
            "quantity",
            "currency",
            "metadata",
            "created_at",
        )
        read_only_fields = fields


class InvoiceSerializer(serializers.ModelSerializer):
    customer_id = serializers.UUIDField(source="customer.id", read_only=True)
    subscription_id = serializers.UUIDField(source="subscription.id", read_only=True, allow_null=True)
    line_items = InvoiceLineItemSerializer(many=True, read_only=True)

    class Meta:
        model = Invoice
        fields = (
            "id",
            "number",
            "customer_id",
            "subscription_id",
            "status",
            "subtotal_minor",
            "discount_minor",
            "tax_minor",
            "total_minor",
            "amount_due_minor",
            "currency",
            "due_at",
            "paid_at",
            "hosted_payment_url",
            "metadata",
            "line_items",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class CreditNoteSerializer(serializers.ModelSerializer):
    invoice_id = serializers.UUIDField(source="invoice.id", read_only=True)

    class Meta:
        model = CreditNote
        fields = (
            "id",
            "invoice_id",
            "amount_minor",
            "currency",
            "reason",
            "note",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


# --- Write payloads -----------------------------------------------------------


class InvoiceLinePayload(serializers.Serializer):
    type = serializers.ChoiceField(choices=InvoiceLineItem.Type.choices)
    description = serializers.CharField(
        required=False, allow_blank=True, default="", max_length=400
    )
    amount_minor = serializers.IntegerField(min_value=0)
    quantity = serializers.IntegerField(min_value=1, default=1)
    currency = serializers.CharField(required=False, allow_blank=True, default="", max_length=3)
    metadata = serializers.JSONField(required=False, default=dict)


class CreateInvoicePayload(serializers.Serializer):
    customer_id = serializers.UUIDField()
    subscription_id = serializers.UUIDField(required=False, allow_null=True)
    currency = serializers.CharField(max_length=3)
    line_items = InvoiceLinePayload(many=True)
    due_at = serializers.DateTimeField(required=False, allow_null=True)
    metadata = serializers.JSONField(required=False, default=dict)


class VoidInvoicePayload(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, default="", max_length=400)


class MarkUncollectiblePayload(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, default="", max_length=400)


class MarkPaidPayload(serializers.Serializer):
    paid_amount_minor = serializers.IntegerField(required=False, min_value=1)
    paid_at = serializers.DateTimeField(required=False, allow_null=True)


class ApplyCreditPayload(serializers.Serializer):
    amount_minor = serializers.IntegerField(min_value=1)
    reason = serializers.ChoiceField(
        choices=CreditNote.Reason.choices, required=False, default=CreditNote.Reason.OTHER
    )
    note = serializers.CharField(required=False, allow_blank=True, default="", max_length=1000)


class ApplyCreditResponseSerializer(serializers.Serializer):
    invoice = InvoiceSerializer()
    credit_note = CreditNoteSerializer()


class SendInvoiceReminderPayload(serializers.Serializer):
    channel = serializers.ChoiceField(choices=("email", "sms"), default="email")
    message = serializers.CharField(max_length=1000)
