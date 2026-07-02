from __future__ import annotations

from django.contrib import admin

from .models import WebhookDelivery, WebhookEndpoint, WebhookEvent


class WebhookDeliveryInline(admin.TabularInline):
    model = WebhookDelivery
    extra = 0
    fields = ("endpoint", "status", "attempt_count", "last_status_code", "next_attempt_at", "delivered_at")
    autocomplete_fields = ("endpoint",)
    show_change_link = True


@admin.register(WebhookEndpoint)
class WebhookEndpointAdmin(admin.ModelAdmin):
    list_display = ("url", "merchant", "environment", "enabled", "description", "created_at")
    list_filter = ("enabled", "environment__mode", "created_at")
    search_fields = ("url", "description", "merchant__name", "merchant__slug")
    autocomplete_fields = ("merchant", "environment")
    list_select_related = ("merchant", "environment")
    readonly_fields = ("id", "secret_encrypted", "created_at", "updated_at")


@admin.register(WebhookEvent)
class WebhookEventAdmin(admin.ModelAdmin):
    list_display = ("event_type", "aggregate_type", "aggregate_id", "merchant", "environment", "occurred_at")
    list_filter = ("event_type", "aggregate_type", "environment__mode", "occurred_at")
    search_fields = ("event_type", "aggregate_type", "aggregate_id", "merchant__name", "merchant__slug")
    autocomplete_fields = ("merchant", "environment")
    list_select_related = ("merchant", "environment")
    readonly_fields = ("id", "payload", "occurred_at", "created_at", "updated_at")
    inlines = (WebhookDeliveryInline,)


@admin.register(WebhookDelivery)
class WebhookDeliveryAdmin(admin.ModelAdmin):
    list_display = ("webhook_event", "endpoint", "status", "attempt_count", "last_status_code", "next_attempt_at", "delivered_at")
    list_filter = ("status", "last_status_code", "next_attempt_at", "delivered_at", "created_at")
    search_fields = ("webhook_event__event_type", "endpoint__url", "last_response_body")
    autocomplete_fields = ("webhook_event", "endpoint")
    list_select_related = ("webhook_event", "endpoint")
    readonly_fields = ("id", "created_at", "updated_at")
