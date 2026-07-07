from __future__ import annotations

from django.contrib import admin

from .models import BalanceTransaction, PaymentAttempt, ProcessorEvent, ProcessorWebhookReceipt


@admin.register(PaymentAttempt)
class PaymentAttemptAdmin(admin.ModelAdmin):
    list_display = (
        "invoice",
        "merchant",
        "environment",
        "attempt_number",
        "status",
        "amount_minor",
        "currency",
        "processor_reference",
        "next_retry_at",
        "created_at",
    )
    list_filter = ("status", "currency", "environment__mode", "next_retry_at", "created_at")
    search_fields = ("invoice__number", "invoice__customer__email", "processor_reference", "idempotency_key", "merchant__name", "merchant__slug")
    autocomplete_fields = ("merchant", "environment", "invoice", "payment_method")
    list_select_related = ("merchant", "environment", "invoice", "invoice__customer", "payment_method")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(BalanceTransaction)
class BalanceTransactionAdmin(admin.ModelAdmin):
    list_display = ("type", "invoice", "merchant", "environment", "signed_amount_minor", "currency", "processor_reference", "created_at")
    list_filter = ("type", "currency", "environment__mode", "created_at")
    search_fields = ("invoice__number", "invoice__customer__email", "processor_reference", "idempotency_key", "merchant__name", "merchant__slug")
    autocomplete_fields = ("merchant", "environment", "invoice", "payment_attempt", "credit_note")
    list_select_related = ("merchant", "environment", "invoice", "invoice__customer", "payment_attempt", "credit_note")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(ProcessorEvent)
class ProcessorEventAdmin(admin.ModelAdmin):
    list_display = ("provider", "event_type", "merchant", "environment", "provider_event_id", "processor_reference", "received_at", "processed_at")
    list_filter = ("provider", "event_type", "environment__mode", "received_at", "processed_at")
    search_fields = ("provider_event_id", "processor_reference", "event_type", "merchant__name", "merchant__slug")
    autocomplete_fields = ("merchant", "environment")
    list_select_related = ("merchant", "environment")
    readonly_fields = ("id", "payload", "received_at", "created_at", "updated_at")


@admin.register(ProcessorWebhookReceipt)
class ProcessorWebhookReceiptAdmin(admin.ModelAdmin):
    list_display = (
        "provider",
        "outcome",
        "response_status_code",
        "event_type",
        "merchant",
        "environment",
        "provider_event_id",
        "processor_reference",
        "received_at",
    )
    list_filter = (
        "provider",
        "outcome",
        "failure_reason",
        "response_status_code",
        "event_type",
        "received_at",
    )
    search_fields = (
        "provider_event_id",
        "processor_reference",
        "event_type",
        "merchant__name",
        "merchant__slug",
        "path",
    )
    autocomplete_fields = ("merchant", "environment")
    list_select_related = ("merchant", "environment")
    readonly_fields = (
        "id",
        "payload",
        "response_body",
        "received_at",
        "created_at",
        "updated_at",
    )
