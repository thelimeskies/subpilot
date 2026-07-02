from __future__ import annotations

from django.contrib import admin

from .models import CreditNote, Invoice, InvoiceLineItem


class InvoiceLineItemInline(admin.TabularInline):
    model = InvoiceLineItem
    extra = 0
    fields = ("type", "description", "amount_minor", "quantity", "currency")
    show_change_link = True


class CreditNoteInline(admin.TabularInline):
    model = CreditNote
    extra = 0
    fields = ("amount_minor", "currency", "reason", "note", "created_at")
    readonly_fields = ("created_at",)
    show_change_link = True


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("number", "customer", "merchant", "environment", "status", "total_minor", "amount_due_minor", "currency", "due_at", "paid_at")
    list_filter = ("status", "currency", "environment__mode", "due_at", "paid_at", "created_at")
    search_fields = ("number", "customer__email", "customer__name", "merchant__name", "merchant__slug")
    autocomplete_fields = ("merchant", "environment", "customer", "subscription")
    list_select_related = ("merchant", "environment", "customer", "subscription")
    readonly_fields = ("id", "created_at", "updated_at")
    inlines = (InvoiceLineItemInline, CreditNoteInline)


@admin.register(InvoiceLineItem)
class InvoiceLineItemAdmin(admin.ModelAdmin):
    list_display = ("invoice", "type", "description", "amount_minor", "quantity", "currency", "created_at")
    list_filter = ("type", "currency", "created_at")
    search_fields = ("invoice__number", "description", "invoice__customer__email")
    autocomplete_fields = ("invoice",)
    list_select_related = ("invoice", "invoice__customer")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(CreditNote)
class CreditNoteAdmin(admin.ModelAdmin):
    list_display = ("invoice", "merchant", "environment", "amount_minor", "currency", "reason", "created_at")
    list_filter = ("reason", "currency", "environment__mode", "created_at")
    search_fields = ("invoice__number", "invoice__customer__email", "merchant__name", "merchant__slug")
    autocomplete_fields = ("merchant", "environment", "invoice")
    list_select_related = ("merchant", "environment", "invoice", "invoice__customer")
    readonly_fields = ("id", "created_at", "updated_at")
