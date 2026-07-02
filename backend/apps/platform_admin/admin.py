from __future__ import annotations

from django.contrib import admin

from .models import (
    KycReview,
    MerchantConfig,
    PlatformAdmin,
    PlatformInviteToken,
    PlatformMerchantNote,
    PlatformSetting,
    SupportTicket,
    SupportTicketReply,
)


class SupportTicketReplyInline(admin.TabularInline):
    model = SupportTicketReply
    extra = 0
    fields = ("author", "body", "created_at")
    autocomplete_fields = ("author",)
    readonly_fields = ("created_at",)
    show_change_link = True


@admin.register(PlatformAdmin)
class PlatformAdminAdmin(admin.ModelAdmin):
    list_display = ("email", "display_name", "role", "status", "mfa_enabled", "last_login_at", "created_at")
    list_filter = ("role", "status", "mfa_enabled", "last_login_at", "created_at")
    search_fields = ("email", "display_name")
    readonly_fields = ("id", "password_hash", "mfa_secret_encrypted", "last_login_at", "created_at", "updated_at")
    fieldsets = (
        (None, {"fields": ("id", "email", "display_name", "role", "status")}),
        ("Security", {"fields": ("password_hash", "mfa_enabled", "mfa_secret_encrypted", "last_login_at")}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )


@admin.register(PlatformMerchantNote)
class PlatformMerchantNoteAdmin(admin.ModelAdmin):
    list_display = ("merchant", "author", "created_at")
    list_filter = ("created_at",)
    search_fields = ("merchant__name", "merchant__slug", "author__email", "body")
    autocomplete_fields = ("merchant", "author")
    list_select_related = ("merchant", "author")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = ("subject", "merchant", "priority", "status", "assignee", "requester_email", "created_at")
    list_filter = ("priority", "status", "created_at")
    search_fields = ("subject", "body", "requester_email", "merchant__name", "merchant__slug", "assignee__email")
    autocomplete_fields = ("merchant", "assignee")
    list_select_related = ("merchant", "assignee")
    readonly_fields = ("id", "created_at", "updated_at")
    inlines = (SupportTicketReplyInline,)


@admin.register(SupportTicketReply)
class SupportTicketReplyAdmin(admin.ModelAdmin):
    list_display = ("ticket", "author", "created_at")
    list_filter = ("created_at",)
    search_fields = ("ticket__subject", "author__email", "body")
    autocomplete_fields = ("ticket", "author")
    list_select_related = ("ticket", "author")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(KycReview)
class KycReviewAdmin(admin.ModelAdmin):
    list_display = ("merchant", "status", "level", "reviewer", "submitted_at", "reviewed_at", "created_at")
    list_filter = ("status", "level", "submitted_at", "reviewed_at", "created_at")
    search_fields = ("merchant__name", "merchant__slug", "reviewer__email", "notes")
    autocomplete_fields = ("merchant", "reviewer")
    list_select_related = ("merchant", "reviewer")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(PlatformInviteToken)
class PlatformInviteTokenAdmin(admin.ModelAdmin):
    list_display = ("admin", "expires_at", "accepted_at", "created_at")
    list_filter = ("expires_at", "accepted_at", "created_at")
    search_fields = ("admin__email", "admin__display_name")
    autocomplete_fields = ("admin",)
    list_select_related = ("admin",)
    readonly_fields = ("id", "token", "created_at", "updated_at")


@admin.register(PlatformSetting)
class PlatformSettingAdmin(admin.ModelAdmin):
    list_display = ("key", "created_at", "updated_at")
    search_fields = ("key",)
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(MerchantConfig)
class MerchantConfigAdmin(admin.ModelAdmin):
    list_display = ("merchant", "updated_by", "updated_at")
    search_fields = ("merchant__name", "merchant__slug", "updated_by__email")
    autocomplete_fields = ("merchant", "updated_by")
    list_select_related = ("merchant", "updated_by")
    readonly_fields = ("id", "created_at", "updated_at")
