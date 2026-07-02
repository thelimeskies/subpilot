"""DRF serializers for the auth flow.

These deliberately do NOT mirror Django's standard ``ValidationError`` JSON
shape — the FE expects a flat ``{ ok: bool, reason: string }`` envelope (see
[apps/merchant-dashboard/src/auth/AuthContext.tsx](file:///Users/mac/Desktop/Projects/HackathonxNomba/apps/merchant-dashboard/src/auth/AuthContext.tsx#L51-L73)).
The views translate validation failures into that envelope manually.
"""
from __future__ import annotations

from rest_framework import serializers

from .models import INTERNAL_ROLE_TO_FE, ApiKey, Role, TeamMember, User
from .rbac import list_capabilities


ROLE_TO_FRONTEND = {
    Role.OWNER: "Owner",
    Role.BILLING_ADMIN: "Admin",
    Role.DEVELOPER: "Admin",
    Role.FINANCE: "Finance",
    Role.SUPPORT: "Support",
    Role.ANALYST: "Read-only",
}

FRONTEND_TO_ROLE = {
    "Admin": Role.BILLING_ADMIN,
    "Finance": Role.FINANCE,
    "Support": Role.SUPPORT,
    "Read-only": Role.ANALYST,
}


class SignUpSerializer(serializers.Serializer):
    fullName = serializers.CharField(max_length=128)
    email = serializers.EmailField()
    password = serializers.CharField(max_length=256)
    orgName = serializers.CharField(max_length=128)


class SignInSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(max_length=256)


class VerifyEmailSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=128)


class RequestResetSerializer(serializers.Serializer):
    email = serializers.EmailField()


class ResetPasswordSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=128)
    newPassword = serializers.CharField(max_length=256)


class VerifyMfaSerializer(serializers.Serializer):
    challengeId = serializers.CharField(max_length=128)
    code = serializers.CharField(max_length=12)


class OnboardingBusinessSerializer(serializers.Serializer):
    legalName = serializers.CharField(max_length=128)
    tradingName = serializers.CharField(max_length=128, required=False, allow_blank=True)
    country = serializers.CharField(max_length=64)
    industry = serializers.CharField(max_length=64)
    website = serializers.URLField(required=False, allow_blank=True)
    description = serializers.CharField(max_length=500, required=False, allow_blank=True)


class OnboardingKycSerializer(serializers.Serializer):
    rcNumber = serializers.CharField(max_length=64)
    directorIdName = serializers.CharField(max_length=256)
    directorIdData = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    addressProofName = serializers.CharField(max_length=256)
    addressProofData = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class OnboardingPayoutSerializer(serializers.Serializer):
    bank = serializers.CharField(max_length=128)
    accountNumber = serializers.RegexField(regex=r"^\d{6,12}$")
    accountName = serializers.CharField(max_length=128)
    resolved = serializers.BooleanField()
    settlementFrequency = serializers.ChoiceField(choices=("daily", "weekly", "monthly"))


class OnboardingBrandingSerializer(serializers.Serializer):
    primaryColor = serializers.RegexField(regex=r"^#[0-9A-Fa-f]{6}$")
    logoData = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    subdomain = serializers.RegexField(regex=r"^[a-z0-9-]{3,64}$")


class OnboardingPlansSerializer(serializers.Serializer):
    mode = serializers.ChoiceField(choices=("import", "skip"))


class OnboardingMfaSerializer(serializers.Serializer):
    secret = serializers.CharField(max_length=64, required=False, allow_blank=True)
    enabled = serializers.BooleanField(default=False)


class OnboardingTeamInviteSerializer(serializers.Serializer):
    email = serializers.EmailField()
    role = serializers.ChoiceField(choices=("Admin", "Finance", "Support", "Read-only"))


class OnboardingDraftSerializer(serializers.Serializer):
    draft = serializers.JSONField()

    def validate_draft(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("Draft must be an object.")
        if value.get("version") != 1:
            raise serializers.ValidationError("Unsupported onboarding draft version.")
        valid_steps = {"business", "kyc", "payout", "branding", "plans", "mfa", "team", "finish"}
        if value.get("currentStepId") not in valid_steps:
            raise serializers.ValidationError("Draft has an invalid current step.")
        completed = value.get("completedSteps", [])
        if not isinstance(completed, list) or any(step not in valid_steps for step in completed):
            raise serializers.ValidationError("Draft has invalid completed steps.")
        return value


class CompleteOnboardingSerializer(serializers.Serializer):
    business = OnboardingBusinessSerializer()
    kyc = OnboardingKycSerializer()
    payout = OnboardingPayoutSerializer()
    branding = OnboardingBrandingSerializer()
    plans = OnboardingPlansSerializer()
    mfa = OnboardingMfaSerializer()
    team = OnboardingTeamInviteSerializer(many=True, required=False)

    def validate_payout(self, value):
        if not value.get("resolved"):
            raise serializers.ValidationError("Resolve the payout account before completing onboarding.")
        return value


class ApiKeySerializer(serializers.ModelSerializer):
    prefix = serializers.CharField(source="key_prefix", read_only=True)
    environment = serializers.CharField(source="environment.mode", read_only=True)

    class Meta:
        model = ApiKey
        fields = (
            "id",
            "name",
            "prefix",
            "environment",
            "scopes",
            "status",
            "last_used_at",
            "created_at",
            "revoked_at",
        )
        read_only_fields = fields


class CreateApiKeySerializer(serializers.Serializer):
    name = serializers.CharField(max_length=128)
    scopes = serializers.ListField(
        child=serializers.ChoiceField(choices=("read", "write", "admin")),
        allow_empty=False,
    )
    environment_mode = serializers.ChoiceField(
        choices=("test", "live"), required=False, allow_null=True
    )


class TeamMemberSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    email = serializers.EmailField(source="user.email", read_only=True)
    role = serializers.SerializerMethodField()
    mfa_enabled = serializers.BooleanField(source="user.mfa_enabled", read_only=True)
    last_seen_at = serializers.DateTimeField(source="user.last_login", read_only=True, allow_null=True)

    class Meta:
        model = TeamMember
        fields = (
            "id",
            "name",
            "email",
            "role",
            "mfa_enabled",
            "status",
            "last_seen_at",
            "invited_at",
            "created_at",
        )
        read_only_fields = fields

    def get_name(self, obj: TeamMember) -> str:
        return obj.user.display_name or obj.user.get_full_name() or obj.user.email

    def get_role(self, obj: TeamMember) -> str:
        return ROLE_TO_FRONTEND.get(obj.role, "Read-only")


class InviteTeamMemberSerializer(serializers.Serializer):
    email = serializers.EmailField()
    role = serializers.ChoiceField(choices=tuple(FRONTEND_TO_ROLE.keys()))
    name = serializers.CharField(max_length=128, required=False, allow_blank=True)
    message = serializers.CharField(max_length=500, required=False, allow_blank=True)


class UpdateTeamMemberSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=tuple(FRONTEND_TO_ROLE.keys()), required=False)


class WorkspaceOrgSerializer(serializers.Serializer):
    legal_name = serializers.CharField(max_length=128, required=False, allow_blank=True)
    trading_name = serializers.CharField(max_length=128, required=False, allow_blank=True)
    country = serializers.CharField(max_length=64, required=False, allow_blank=True)
    timezone = serializers.CharField(max_length=64, required=False, allow_blank=True)
    currency = serializers.ChoiceField(choices=("NGN", "USD", "GBP", "KES"), required=False)
    tax_id = serializers.CharField(max_length=64, required=False, allow_blank=True)
    statement_descriptor = serializers.CharField(max_length=22, required=False, allow_blank=True)


class WorkspaceDunningSerializer(serializers.Serializer):
    schedule = serializers.ListField(
        child=serializers.IntegerField(min_value=0, max_value=8760),
        required=False,
        allow_empty=False,
    )
    max_attempts = serializers.IntegerField(min_value=1, max_value=10, required=False)
    grace_days = serializers.IntegerField(min_value=0, max_value=90, required=False)
    final_action = serializers.ChoiceField(choices=("cancel", "uncollectible"), required=False)


class WorkspaceBrandingSerializer(serializers.Serializer):
    primary_color = serializers.RegexField(
        regex=r"^#[0-9A-Fa-f]{6}$", required=False
    )
    logo_url = serializers.URLField(required=False, allow_blank=True, allow_null=True)
    portal_subdomain = serializers.RegexField(
        regex=r"^[a-z0-9-]+$", max_length=64, required=False
    )


class WorkspacePayoutsSerializer(serializers.Serializer):
    bank = serializers.CharField(max_length=128, required=False, allow_blank=True)
    account_number = serializers.CharField(max_length=32, required=False, allow_blank=True)
    settlement_frequency = serializers.ChoiceField(
        choices=("daily", "weekly", "monthly"), required=False
    )
    descriptor = serializers.CharField(max_length=22, required=False, allow_blank=True)
    paused = serializers.BooleanField(required=False)


class WorkspacePlanDefaultsSerializer(serializers.Serializer):
    trial_days = serializers.IntegerField(min_value=0, max_value=365, required=False)
    proration = serializers.ChoiceField(choices=("create_proration", "none"), required=False)
    currency = serializers.ChoiceField(choices=("NGN", "USD", "GBP", "KES"), required=False)
    tax_behavior = serializers.ChoiceField(choices=("exclusive", "inclusive"), required=False)


class WorkspaceDunningTemplateSerializer(serializers.Serializer):
    id = serializers.CharField(max_length=64)
    label = serializers.CharField(max_length=128)
    body = serializers.CharField(max_length=2000)


class WorkspaceSecuritySerializer(serializers.Serializer):
    require_mfa = serializers.BooleanField(required=False)
    ip_allowlist = serializers.ListField(
        child=serializers.CharField(max_length=64),
        required=False,
    )
    session_timeout_minutes = serializers.IntegerField(min_value=5, max_value=1440, required=False)


class WorkspacePortalSerializer(serializers.Serializer):
    allow_cancel = serializers.BooleanField(required=False)
    allow_pause = serializers.BooleanField(required=False)
    allow_change_plan = serializers.BooleanField(required=False)
    success_url = serializers.URLField(required=False, allow_blank=True)
    cancel_url = serializers.URLField(required=False, allow_blank=True)


class WorkspaceSettingsSerializer(serializers.Serializer):
    org = WorkspaceOrgSerializer(required=False)
    dunning = WorkspaceDunningSerializer(required=False)
    branding = WorkspaceBrandingSerializer(required=False)
    payouts = WorkspacePayoutsSerializer(required=False)
    plan_defaults = WorkspacePlanDefaultsSerializer(required=False)
    dunning_templates = WorkspaceDunningTemplateSerializer(many=True, required=False)
    notifications = serializers.DictField(
        child=serializers.DictField(child=serializers.BooleanField()),
        required=False,
    )
    security = WorkspaceSecuritySerializer(required=False)
    portal = WorkspacePortalSerializer(required=False)


class TransferWorkspaceOwnershipSerializer(serializers.Serializer):
    new_owner_email = serializers.EmailField()


class CloseWorkspaceSerializer(serializers.Serializer):
    confirm_trading_name = serializers.CharField(max_length=128)


class RotateSigningKeySerializer(serializers.Serializer):
    grace_hours = serializers.IntegerField(min_value=0, max_value=168)


class NombaCredentialSerializer(serializers.Serializer):
    integration_mode = serializers.ChoiceField(choices=("platform", "byok"), required=False)
    account_id = serializers.CharField(max_length=128, required=False, allow_blank=True)
    client_id = serializers.CharField(max_length=128, required=False, allow_blank=True)
    client_secret = serializers.CharField(max_length=256, required=False, allow_blank=True, trim_whitespace=False)
    webhook_secret = serializers.CharField(max_length=256, required=False, allow_blank=True, trim_whitespace=False)
    sub_account_id = serializers.CharField(max_length=128, required=False, allow_blank=True)


class NombaSubAccountSerializer(serializers.Serializer):
    sub_account_id = serializers.CharField(max_length=128, allow_blank=True)


class NombaBankAccountLookupSerializer(serializers.Serializer):
    bank = serializers.CharField(max_length=128)
    accountNumber = serializers.RegexField(regex=r"^\d{10,12}$")


# ---------------------------------------------------------------------------
# MerchantUser shape (matches AuthContext.tsx#L13-L23 exactly)
# ---------------------------------------------------------------------------


def merchant_user_payload(user: User) -> dict:
    """Serialize a User + their primary TeamMember into the FE's MerchantUser shape."""
    tm = (
        TeamMember.objects.select_related("merchant")
        .filter(user=user, status=TeamMember.Status.ACTIVE)
        .order_by("created_at")
        .first()
    )
    role_internal = tm.role if tm else None
    role_fe = INTERNAL_ROLE_TO_FE.get(role_internal, "Read-only") if role_internal else "Owner"
    org_id = str(tm.merchant.id) if tm else ""
    org_name = tm.merchant.name if tm else ""
    # Authoritative list of capabilities the FE can use to gate UI controls.
    # The backend remains the source of truth: any action still re-checks via
    # HasCapability. The list is sourced from rbac.CAPABILITIES.
    capabilities = list_capabilities(role_internal) if role_internal else (
        # User without an active TeamMember row (rare bootstrap state) is
        # treated as a workspace owner so onboarding flows aren't blocked.
        list_capabilities(Role.OWNER)
    )

    return {
        "id": str(user.id),
        "name": user.display_name or user.get_full_name() or user.email,
        "email": user.email,
        "role": role_fe,
        "initials": user.initials,
        "orgId": org_id,
        "orgName": org_name,
        "mfaEnabled": bool(user.mfa_enabled),
        "onboardingComplete": bool(user.onboarding_complete),
        "capabilities": capabilities,
    }
