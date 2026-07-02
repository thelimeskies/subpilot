from __future__ import annotations

from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("occurred_at", "action", "actor_label", "actor_role", "merchant", "environment", "target_type", "target_id", "ip_address")
    list_filter = ("action", "actor_role", "target_type", "occurred_at")
    search_fields = ("action", "actor_label", "target_type", "target_id", "merchant__name", "merchant__slug", "request_id", "ip_address")
    autocomplete_fields = ("actor_user", "merchant", "environment")
    list_select_related = ("actor_user", "merchant", "environment")
    readonly_fields = (
        "id",
        "actor_user",
        "actor_label",
        "actor_role",
        "merchant",
        "environment",
        "action",
        "target_type",
        "target_id",
        "metadata",
        "request_id",
        "ip_address",
        "user_agent",
        "occurred_at",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
