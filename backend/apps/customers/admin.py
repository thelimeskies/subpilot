from __future__ import annotations

from django.contrib import admin

from .models import Customer, PaymentMethod, PortalSession


class PaymentMethodInline(admin.TabularInline):
    model = PaymentMethod
    extra = 0
    fields = ("provider", "brand", "last4", "exp_month", "exp_year", "status", "is_default", "fingerprint")
    readonly_fields = ("fingerprint",)
    show_change_link = True


class PortalSessionInline(admin.TabularInline):
    model = PortalSession
    extra = 0
    fields = ("subscription", "invoice", "allowed_actions", "return_url", "expires_at", "used_at")
    autocomplete_fields = ("subscription", "invoice")
    show_change_link = True


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("email", "name", "merchant", "environment", "status", "external_id", "created_at")
    list_filter = ("status", "environment__mode", "created_at")
    search_fields = ("email", "name", "phone", "external_id", "merchant__name", "merchant__slug")
    autocomplete_fields = ("merchant", "environment")
    list_select_related = ("merchant", "environment")
    readonly_fields = ("id", "created_at", "updated_at")
    inlines = (PaymentMethodInline, PortalSessionInline)


@admin.register(PaymentMethod)
class PaymentMethodAdmin(admin.ModelAdmin):
    list_display = ("customer", "provider", "brand", "last4", "status", "is_default", "created_at")
    list_filter = ("provider", "status", "is_default", "environment__mode", "created_at")
    search_fields = ("customer__email", "customer__name", "brand", "last4", "fingerprint", "merchant__name", "merchant__slug")
    autocomplete_fields = ("merchant", "environment", "customer")
    list_select_related = ("merchant", "environment", "customer")
    readonly_fields = ("id", "token_encrypted", "created_at", "updated_at")


@admin.register(PortalSession)
class PortalSessionAdmin(admin.ModelAdmin):
    list_display = ("customer", "merchant", "environment", "expires_at", "used_at", "created_at")
    list_filter = ("expires_at", "used_at", "environment__mode", "created_at")
    search_fields = ("customer__email", "customer__name", "merchant__name", "merchant__slug")
    autocomplete_fields = ("merchant", "environment", "customer", "subscription", "invoice")
    list_select_related = ("merchant", "environment", "customer", "subscription", "invoice")
    readonly_fields = ("id", "token_hash", "created_at", "updated_at")
