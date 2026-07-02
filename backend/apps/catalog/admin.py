from __future__ import annotations

from django.contrib import admin

from .models import Plan, PlanFeature, PriceVersion, Product


class PriceVersionInline(admin.TabularInline):
    model = PriceVersion
    extra = 0
    fields = ("amount_minor", "currency", "interval_unit", "interval_count", "setup_fee_minor", "active_from", "active_to")
    show_change_link = True


class PlanFeatureInline(admin.TabularInline):
    model = PlanFeature
    extra = 0
    fields = ("label", "detail", "sort_order")


class PlanInline(admin.TabularInline):
    model = Plan
    extra = 0
    fields = ("name", "status", "trial_days", "proration_policy", "cancellation_policy", "tokenized_renewal")
    show_change_link = True


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "merchant", "environment", "status", "created_at")
    list_filter = ("status", "environment__mode", "created_at")
    search_fields = ("name", "description", "merchant__name", "merchant__slug")
    autocomplete_fields = ("merchant", "environment")
    list_select_related = ("merchant", "environment")
    readonly_fields = ("id", "created_at", "updated_at")
    inlines = (PlanInline,)


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ("name", "product", "merchant", "environment", "status", "trial_days", "tokenized_renewal", "created_at")
    list_filter = ("status", "environment__mode", "proration_policy", "cancellation_policy", "tokenized_renewal", "created_at")
    search_fields = ("name", "description", "product__name", "merchant__name", "merchant__slug")
    autocomplete_fields = ("merchant", "environment", "product", "dunning_policy")
    list_select_related = ("merchant", "environment", "product", "dunning_policy")
    readonly_fields = ("id", "created_at", "updated_at")
    inlines = (PriceVersionInline, PlanFeatureInline)


@admin.register(PriceVersion)
class PriceVersionAdmin(admin.ModelAdmin):
    list_display = ("plan", "amount_minor", "currency", "interval_unit", "interval_count", "active_from", "active_to")
    list_filter = ("currency", "interval_unit", "active_from", "active_to")
    search_fields = ("plan__name", "plan__product__name", "plan__merchant__name", "plan__merchant__slug")
    autocomplete_fields = ("plan",)
    list_select_related = ("plan", "plan__product", "plan__merchant", "plan__environment")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(PlanFeature)
class PlanFeatureAdmin(admin.ModelAdmin):
    list_display = ("label", "plan", "sort_order", "created_at")
    list_filter = ("created_at",)
    search_fields = ("label", "detail", "plan__name", "plan__product__name")
    autocomplete_fields = ("plan",)
    list_select_related = ("plan", "plan__product")
    readonly_fields = ("id", "created_at", "updated_at")
