from __future__ import annotations

from django.contrib import admin

from .models import DunningPolicy, DunningRun, NotificationLog


class NotificationLogInline(admin.TabularInline):
    model = NotificationLog
    extra = 0
    fields = ("channel", "status", "template_key", "sent_at", "failure_message")
    show_change_link = True


@admin.register(DunningPolicy)
class DunningPolicyAdmin(admin.ModelAdmin):
    list_display = ("name", "merchant", "environment", "final_action", "grace_period_days", "notify_email", "notify_sms", "notify_webhook")
    list_filter = ("final_action", "hard_failure_behavior", "notify_email", "notify_sms", "notify_webhook", "environment__mode")
    search_fields = ("name", "merchant__name", "merchant__slug")
    autocomplete_fields = ("merchant", "environment")
    list_select_related = ("merchant", "environment")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(DunningRun)
class DunningRunAdmin(admin.ModelAdmin):
    list_display = ("invoice", "merchant", "environment", "policy", "status", "attempt_count", "next_retry_at", "recovered_at", "exhausted_at")
    list_filter = ("status", "environment__mode", "next_retry_at", "recovered_at", "exhausted_at", "created_at")
    search_fields = ("invoice__number", "invoice__customer__email", "policy__name", "merchant__name", "merchant__slug")
    autocomplete_fields = ("merchant", "environment", "invoice", "subscription", "policy")
    list_select_related = ("merchant", "environment", "invoice", "invoice__customer", "subscription", "policy")
    readonly_fields = ("id", "started_at", "created_at", "updated_at")
    inlines = (NotificationLogInline,)


@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    list_display = ("dunning_run", "merchant", "environment", "channel", "status", "template_key", "sent_at", "created_at")
    list_filter = ("channel", "status", "template_key", "environment__mode", "sent_at", "created_at")
    search_fields = ("dunning_run__invoice__number", "dunning_run__invoice__customer__email", "template_key", "failure_message")
    autocomplete_fields = ("merchant", "environment", "dunning_run")
    list_select_related = ("merchant", "environment", "dunning_run", "dunning_run__invoice")
    readonly_fields = ("id", "created_at", "updated_at")
