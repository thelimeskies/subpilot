from __future__ import annotations

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import (
    ApiKey,
    EmailVerificationToken,
    Environment,
    Merchant,
    MfaChallenge,
    PasswordResetToken,
    TeamMember,
    User,
)


class EnvironmentInline(admin.TabularInline):
    model = Environment
    extra = 0
    fields = (
        "mode",
        "nomba_integration_mode",
        "nomba_account_id",
        "nomba_sub_account_id",
        "nomba_client_id",
        "nomba_credentials_validated_at",
        "nomba_live_active",
        "publishable_key",
        "created_at",
    )
    readonly_fields = ("created_at",)
    show_change_link = True


class TeamMemberInline(admin.TabularInline):
    model = TeamMember
    extra = 0
    fields = ("user", "role", "status", "invited_by", "invited_at", "activated_at")
    autocomplete_fields = ("user", "invited_by")
    show_change_link = True


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    ordering = ("email",)
    list_display = (
        "email",
        "display_name",
        "is_staff",
        "is_superuser",
        "email_verified",
        "mfa_enabled",
        "onboarding_complete",
        "last_login",
    )
    list_filter = (
        "is_staff",
        "is_superuser",
        "is_active",
        "email_verified",
        "mfa_enabled",
        "onboarding_complete",
    )
    search_fields = ("email", "display_name", "first_name", "last_name")
    readonly_fields = ("id", "date_joined", "last_login", "mfa_secret_encrypted")
    fieldsets = (
        (None, {"fields": ("id", "email", "username", "password")}),
        ("Profile", {"fields": ("display_name", "first_name", "last_name")}),
        ("Auth state", {"fields": ("email_verified", "onboarding_complete", "mfa_enabled", "mfa_secret_encrypted")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "display_name", "password1", "password2", "is_staff", "is_superuser"),
            },
        ),
    )


@admin.register(Merchant)
class MerchantAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "status", "default_currency", "industry", "created_at")
    list_filter = ("status", "default_currency", "industry", "created_at")
    search_fields = ("name", "slug", "nomba_account_id")
    readonly_fields = ("id", "created_at", "updated_at")
    inlines = (EnvironmentInline, TeamMemberInline)


@admin.register(Environment)
class EnvironmentAdmin(admin.ModelAdmin):
    list_display = (
        "merchant",
        "mode",
        "nomba_integration_mode",
        "nomba_account_id",
        "nomba_sub_account_id",
        "nomba_credentials_validated_at",
        "nomba_live_active",
    )
    list_filter = ("mode", "nomba_integration_mode", "nomba_live_active", "created_at")
    search_fields = ("merchant__name", "merchant__slug", "nomba_account_id", "nomba_sub_account_id", "publishable_key")
    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
        "has_nomba_client_secret",
        "has_nomba_access_token",
        "has_nomba_refresh_token",
        "has_webhook_secret",
    )
    list_select_related = ("merchant",)
    fieldsets = (
        (None, {"fields": ("id", "merchant", "mode", "publishable_key", "created_at", "updated_at")}),
        (
            "Nomba",
            {
                "fields": (
                    "nomba_integration_mode",
                    "nomba_account_id",
                    "nomba_sub_account_id",
                    "nomba_client_id",
                    "nomba_credentials_validated_at",
                    "nomba_token_expires_at",
                    "nomba_live_active",
                    "nomba_last_validation",
                    "has_nomba_client_secret",
                    "has_nomba_access_token",
                    "has_nomba_refresh_token",
                    "has_webhook_secret",
                )
            },
        ),
    )

    @admin.display(boolean=True, description="Client secret")
    def has_nomba_client_secret(self, obj: Environment) -> bool:
        return bool(obj.nomba_client_secret_encrypted)

    @admin.display(boolean=True, description="Access token")
    def has_nomba_access_token(self, obj: Environment) -> bool:
        return bool(obj.nomba_access_token_encrypted)

    @admin.display(boolean=True, description="Refresh token")
    def has_nomba_refresh_token(self, obj: Environment) -> bool:
        return bool(obj.nomba_refresh_token_encrypted)

    @admin.display(boolean=True, description="Webhook secret")
    def has_webhook_secret(self, obj: Environment) -> bool:
        return bool(obj.webhook_secret_encrypted)


@admin.register(TeamMember)
class TeamMemberAdmin(admin.ModelAdmin):
    list_display = ("user", "merchant", "role", "status", "invited_by", "activated_at", "created_at")
    list_filter = ("role", "status", "created_at")
    search_fields = ("user__email", "user__display_name", "merchant__name", "merchant__slug")
    autocomplete_fields = ("merchant", "user", "invited_by")
    list_select_related = ("merchant", "user", "invited_by")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(ApiKey)
class ApiKeyAdmin(admin.ModelAdmin):
    list_display = ("name", "merchant", "environment", "key_prefix", "status", "last_used_at", "created_at")
    list_filter = ("status", "environment__mode", "created_at", "last_used_at")
    search_fields = ("name", "key_prefix", "merchant__name", "merchant__slug")
    autocomplete_fields = ("merchant", "environment", "created_by")
    list_select_related = ("merchant", "environment", "created_by")
    readonly_fields = ("id", "key_hash", "created_at", "updated_at", "last_used_at", "revoked_at")


@admin.register(EmailVerificationToken)
class EmailVerificationTokenAdmin(admin.ModelAdmin):
    list_display = ("email", "user", "expires_at", "used_at", "created_at")
    list_filter = ("used_at", "expires_at", "created_at")
    search_fields = ("email", "user__email")
    autocomplete_fields = ("user",)
    readonly_fields = ("id", "token", "pending_payload", "created_at", "updated_at")


@admin.register(PasswordResetToken)
class PasswordResetTokenAdmin(admin.ModelAdmin):
    list_display = ("user", "expires_at", "used_at", "created_at")
    list_filter = ("used_at", "expires_at", "created_at")
    search_fields = ("user__email",)
    autocomplete_fields = ("user",)
    readonly_fields = ("id", "token", "created_at", "updated_at")


@admin.register(MfaChallenge)
class MfaChallengeAdmin(admin.ModelAdmin):
    list_display = ("user", "expires_at", "consumed_at", "created_at")
    list_filter = ("consumed_at", "expires_at", "created_at")
    search_fields = ("user__email",)
    autocomplete_fields = ("user",)
    readonly_fields = ("id", "challenge_id", "created_at", "updated_at")
