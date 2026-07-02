from __future__ import annotations

from django.contrib import admin

from .models import Subscription, SubscriptionEvent, SubscriptionItem


class SubscriptionItemInline(admin.TabularInline):
    model = SubscriptionItem
    extra = 0
    fields = ("price_version", "quantity", "status")
    autocomplete_fields = ("price_version",)
    show_change_link = True


class SubscriptionEventInline(admin.TabularInline):
    model = SubscriptionEvent
    extra = 0
    fields = ("event_type", "from_status", "to_status", "actor_label", "occurred_at")
    readonly_fields = ("occurred_at",)
    can_delete = False
    show_change_link = True

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ("customer", "plan", "merchant", "environment", "status", "current_period_end", "cancel_at_period_end", "created_at")
    list_filter = ("status", "cancel_at_period_end", "environment__mode", "current_period_end", "created_at")
    search_fields = ("customer__email", "customer__name", "plan__name", "merchant__name", "merchant__slug")
    autocomplete_fields = ("merchant", "environment", "customer", "plan", "default_payment_method", "dunning_policy")
    list_select_related = ("merchant", "environment", "customer", "plan", "default_payment_method", "dunning_policy")
    readonly_fields = ("id", "created_at", "updated_at")
    inlines = (SubscriptionItemInline, SubscriptionEventInline)


@admin.register(SubscriptionItem)
class SubscriptionItemAdmin(admin.ModelAdmin):
    list_display = ("subscription", "price_version", "quantity", "status", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("subscription__customer__email", "subscription__plan__name", "price_version__plan__name")
    autocomplete_fields = ("subscription", "price_version")
    list_select_related = ("subscription", "subscription__customer", "subscription__plan", "price_version")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(SubscriptionEvent)
class SubscriptionEventAdmin(admin.ModelAdmin):
    list_display = ("subscription", "event_type", "from_status", "to_status", "actor_label", "occurred_at")
    list_filter = ("event_type", "from_status", "to_status", "occurred_at")
    search_fields = ("subscription__customer__email", "subscription__plan__name", "event_type", "actor_label")
    autocomplete_fields = ("subscription",)
    list_select_related = ("subscription", "subscription__customer", "subscription__plan")
    readonly_fields = ("id", "created_at", "updated_at", "occurred_at")
