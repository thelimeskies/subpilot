"""Auth views.

All responses follow the FE envelope: ``{ ok, ... }`` on success and
``{ ok: false, reason }`` on failure. Status code is always 200 for these
auth flows because the FE switches purely on ``ok`` and ``reason``.
"""
from __future__ import annotations

import logging
import math
import uuid

from django.contrib.auth import login as django_login
from django.contrib.auth import logout as django_logout
from django.contrib.sessions.models import Session
from django.conf import settings
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from drf_spectacular.utils import OpenApiTypes, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import viewsets
from rest_framework.decorators import action

from apps.audit.services.log_event import log_event
from apps.common.db import atomic_with_retry
from apps.common import time as t
from apps.common.permissions import HasTenantContext
from apps.accounts.permissions import HasCapability

from .serializers import (
    ApiKeySerializer,
    CloseWorkspaceSerializer,
    CompleteOnboardingSerializer,
    CreateApiKeySerializer,
    FRONTEND_TO_ROLE,
    InviteTeamMemberSerializer,
    NombaBankAccountLookupSerializer,
    NombaCredentialSerializer,
    NombaSubAccountSerializer,
    OnboardingDraftSerializer,
    RequestResetSerializer,
    ResetPasswordSerializer,
    RotateSigningKeySerializer,
    SignInSerializer,
    SignUpSerializer,
    TeamMemberSerializer,
    TransferWorkspaceOwnershipSerializer,
    UpdateTeamMemberSerializer,
    VerifyEmailSerializer,
    VerifyMfaSerializer,
    WorkspaceSettingsSerializer,
    merchant_user_payload,
)
from .models import ApiKey, Environment, Merchant, Role, TeamMember, User
from apps.catalog.models import Plan, PlanFeature, PriceVersion, Product
from apps.catalog.services.create_price_version import create_price_version
from apps.catalog.services.plan_lifecycle import activate_plan
from apps.dunning.models import DunningPolicy
from apps.dunning.services import update_dunning_policy
from .services import auth as auth_service
from .services.api_keys import (
    create_api_key,
    ensure_publishable_key,
    revoke_api_key,
    rotate_publishable_key,
)
from .services.features import feature_payload
from .services import mfa as mfa_service
from .services.signing_keys import rotate_signing_key, signing_key_payload
from .tasks import send_invitation_email, send_password_reset_email, send_verification_email
from apps.payments.services.nomba import (
    activate_nomba_environment,
    list_nomba_banks,
    lookup_nomba_bank_account,
    map_nomba_sub_account,
    nomba_sub_account_id_for_environment,
    sync_nomba_accounts,
    validate_nomba_credentials,
)
from apps.platform_admin.services.kyc_metadata import sync_merchant_kyc_review_from_metadata


logger = logging.getLogger(__name__)


def customer_portal_url(slug: str, path: str = "") -> str:
    base_url = settings.SUBPILOT_FRONTEND_URLS.get("customer", "https://portal.subpilot.kylodo.com").rstrip("/")
    cleaned_slug = slug.strip().strip("/") or "portal"
    cleaned_path = path.strip().lstrip("/")
    return f"{base_url}/{cleaned_slug}{f'/{cleaned_path}' if cleaned_path else ''}"


def _bad(reason: str, http_status: int = status.HTTP_200_OK):
    return Response({"ok": False, "reason": reason}, status=http_status)


def _serializer_first_error_reason(serializer) -> str:
    """Extract a single human-friendly reason string from DRF errors."""
    for _field, errs in serializer.errors.items():
        if isinstance(errs, list) and errs:
            return str(errs[0])
    return "Invalid request."


class SignUpView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []
    serializer_class = SignUpSerializer

    def post(self, request):
        s = SignUpSerializer(data=request.data)
        if not s.is_valid():
            return _bad(_serializer_first_error_reason(s))
        d = s.validated_data
        result = auth_service.signup_merchant(
            full_name=d["fullName"],
            email=d["email"],
            password=d["password"],
            org_name=d["orgName"],
        )
        if not result.ok:
            return _bad(result.reason)

        # Fire the verification email asynchronously.
        send_verification_email.delay(email=d["email"], token=result.verify_token)
        return Response({"ok": True, "verifyToken": result.verify_token})


class SignInView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []
    serializer_class = SignInSerializer

    def post(self, request):
        s = SignInSerializer(data=request.data)
        if not s.is_valid():
            return _bad(_serializer_first_error_reason(s))
        d = s.validated_data

        result = auth_service.sign_in(email=d["email"], password=d["password"], request=request)
        if not result.ok:
            return _bad(result.reason)
        if result.requires_mfa:
            return Response({"ok": True, "requiresMfa": True, "challengeId": result.challenge_id})

        # Establish dashboard session.
        django_login(request, result.user)
        return Response({"ok": True, "user": merchant_user_payload(result.user)})


class VerifyEmailView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []
    serializer_class = VerifyEmailSerializer

    def post(self, request):
        s = VerifyEmailSerializer(data=request.data)
        if not s.is_valid():
            return _bad(_serializer_first_error_reason(s))
        result = auth_service.verify_email_and_create_account(s.validated_data["token"])
        if not result.ok:
            return _bad(result.reason)
        # Auto-sign-in the freshly-verified user (matches FE behaviour).
        django_login(request, result.user)
        return Response({"ok": True, "user": merchant_user_payload(result.user)})


class RequestResetView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []
    serializer_class = RequestResetSerializer

    def post(self, request):
        s = RequestResetSerializer(data=request.data)
        if not s.is_valid():
            return _bad(_serializer_first_error_reason(s))
        ok, reason, token = auth_service.request_password_reset(email=s.validated_data["email"])
        if not ok:
            return _bad(reason)
        send_password_reset_email.delay(email=s.validated_data["email"], token=token)
        return Response({"ok": True, "resetToken": token})


class ResetPasswordView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []
    serializer_class = ResetPasswordSerializer

    def post(self, request):
        s = ResetPasswordSerializer(data=request.data)
        if not s.is_valid():
            return _bad(_serializer_first_error_reason(s))
        ok, reason = auth_service.reset_password(
            token=s.validated_data["token"], new_password=s.validated_data["newPassword"]
        )
        if not ok:
            return _bad(reason)
        return Response({"ok": True})


class VerifyMfaView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []
    serializer_class = VerifyMfaSerializer

    def post(self, request):
        s = VerifyMfaSerializer(data=request.data)
        if not s.is_valid():
            return _bad(_serializer_first_error_reason(s))
        if not s.validated_data["code"].strip().isdigit():
            return _bad("Enter the 6-digit code from your authenticator.")
        user = mfa_service.consume_challenge(
            challenge_id=s.validated_data["challengeId"], code=s.validated_data["code"]
        )
        if user is None:
            return _bad("Code did not match. Try again or use the demo helper.")
        django_login(request, user)
        log_event(
            action="auth.mfa_verified",
            actor_user=user,
            actor_label=user.email,
            target_type="user",
            target_id=str(user.id),
            request=request,
        )
        return Response({"ok": True, "user": merchant_user_payload(user)})


class MeView(APIView):
    permission_classes = [AllowAny]

    @method_decorator(ensure_csrf_cookie)
    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request):
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return Response({"user": None})
        return Response({"user": merchant_user_payload(user)})


class MeFeaturesView(APIView):
    """Resolved feature-flag bundle for the current merchant session (S13).

    Shape: ``{flags: {key: bool}, catalog: [{key, label, description, default}]}``.
    The merchant FE consumes this to hide/disable controls for off flags; the
    server is still the gate (see enforcement in payments/customers views).
    """

    permission_classes = [IsAuthenticated, HasTenantContext]

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request):
        return Response(feature_payload(request.merchant))


class OnboardingDraftView(APIView):
    """Save and resume in-progress onboarding across devices."""

    permission_classes = [IsAuthenticated, HasTenantContext]
    serializer_class = OnboardingDraftSerializer

    def get(self, request):
        drafts = self._drafts(request.merchant)
        return Response({"draft": drafts.get(str(request.user.id))})

    def patch(self, request):
        s = OnboardingDraftSerializer(data=request.data)
        if not s.is_valid():
            return _bad(_serializer_first_error_reason(s), status.HTTP_400_BAD_REQUEST)
        draft = self._save(request, s.validated_data["draft"])
        return Response({"ok": True, "draft": draft})

    def delete(self, request):
        self._clear(request)
        return Response({"ok": True})

    def _drafts(self, merchant: Merchant) -> dict:
        metadata = merchant.metadata or {}
        drafts = metadata.get("onboarding_drafts")
        return drafts if isinstance(drafts, dict) else {}

    @atomic_with_retry
    def _save(self, request, draft: dict) -> dict:
        merchant = request.merchant
        metadata = dict(merchant.metadata or {})
        drafts = dict(metadata.get("onboarding_drafts") or {})
        stored = {
            **draft,
            "savedAt": t.utcnow().isoformat(),
            "savedBy": request.user.email,
        }
        drafts[str(request.user.id)] = stored
        metadata["onboarding_drafts"] = drafts
        merchant.metadata = metadata
        merchant.save(update_fields=["metadata", "updated_at"])
        return stored

    @atomic_with_retry
    def _clear(self, request) -> None:
        merchant = request.merchant
        metadata = dict(merchant.metadata or {})
        drafts = dict(metadata.get("onboarding_drafts") or {})
        drafts.pop(str(request.user.id), None)
        if drafts:
            metadata["onboarding_drafts"] = drafts
        else:
            metadata.pop("onboarding_drafts", None)
        merchant.metadata = metadata
        merchant.save(update_fields=["metadata", "updated_at"])


SAMPLE_ONBOARDING_PLANS = [
    {
        "name": "Starter",
        "amount_minor": 190000,
        "description": "5 seats, email support, and basic analytics.",
        "features": ["5 seats", "Email support", "Basic analytics"],
    },
    {
        "name": "Growth",
        "amount_minor": 790000,
        "description": "25 seats, priority support, and API access.",
        "features": ["25 seats", "Priority support", "API access"],
    },
    {
        "name": "Scale",
        "amount_minor": 2490000,
        "description": "Unlimited seats, advanced recovery, and custom dunning rules.",
        "features": ["Unlimited seats", "Advanced recovery", "Custom dunning rules"],
    },
]


class CompleteOnboardingView(APIView):
    """Persist the merchant setup wizard and mark the signed-in user onboarded."""

    permission_classes = [IsAuthenticated, HasTenantContext]
    serializer_class = CompleteOnboardingSerializer

    def post(self, request):
        s = CompleteOnboardingSerializer(data=request.data)
        if not s.is_valid():
            return _bad(_serializer_first_error_reason(s), status.HTTP_400_BAD_REQUEST)
        result = self._complete(request, s.validated_data)
        return Response(result)

    @atomic_with_retry
    def _complete(self, request, payload: dict) -> dict:
        merchant = request.merchant
        environment = request.environment
        user = request.user

        business = payload["business"]
        kyc = payload["kyc"]
        payout = payload["payout"]
        branding = payload["branding"]
        plans = payload["plans"]
        mfa = payload["mfa"]
        team = payload.get("team") or []

        metadata = dict(merchant.metadata or {})
        org_meta = dict(metadata.get("org") or {})
        trading_name = business.get("tradingName") or business["legalName"]
        org_meta.update(
            {
                "legal_name": business["legalName"],
                "trading_name": trading_name,
                "country": business["country"],
                "industry": business["industry"],
                "website": business.get("website") or "",
                "description": business.get("description") or "",
                "brand_color": branding["primaryColor"],
                "portal_subdomain": branding["subdomain"],
                "payout_bank": payout["bank"],
                "payout_account": payout["accountNumber"],
                "payout_account_name": payout["accountName"],
                "settlement_frequency": payout["settlementFrequency"],
                "statement_descriptor": trading_name[:22].upper(),
            }
        )
        metadata["org"] = org_meta

        settings_doc = WorkspaceSettingsView()._settings_document(request)
        settings_doc["branding"] = {
            **settings_doc.get("branding", {}),
            "primary_color": branding["primaryColor"],
            "portal_subdomain": branding["subdomain"],
            "logo_data": branding.get("logoData") or None,
        }
        settings_doc["payouts"] = {
            **settings_doc.get("payouts", {}),
            "bank": payout["bank"],
            "account_number": payout["accountNumber"],
            "account_name": payout["accountName"],
            "settlement_frequency": payout["settlementFrequency"],
            "descriptor": trading_name[:22].upper(),
            "paused": False,
        }
        settings_doc["security"] = {
            **settings_doc.get("security", {}),
            "require_mfa": bool(mfa.get("enabled")),
        }
        settings_doc["portal"] = {
            **settings_doc.get("portal", {}),
            "success_url": customer_portal_url(branding["subdomain"], "success"),
            "cancel_url": customer_portal_url(branding["subdomain"], "cancel"),
        }
        metadata["settings"] = settings_doc
        metadata["kyc"] = {
            "status": "pending_review",
            "rc_number": kyc["rcNumber"],
            "director_id_name": kyc["directorIdName"],
            "director_id_data": kyc.get("directorIdData") or "",
            "director_id_uploaded": bool(kyc.get("directorIdData")),
            "address_proof_name": kyc["addressProofName"],
            "address_proof_data": kyc.get("addressProofData") or "",
            "address_proof_uploaded": bool(kyc.get("addressProofData")),
            "submitted_at": t.utcnow().isoformat(),
        }
        metadata["onboarding"] = {
            "completed_at": t.utcnow().isoformat(),
            "completed_by": user.email,
            "plans_mode": plans["mode"],
            "team_invites": len(team),
        }
        drafts = dict(metadata.get("onboarding_drafts") or {})
        drafts.pop(str(user.id), None)
        if drafts:
            metadata["onboarding_drafts"] = drafts
        else:
            metadata.pop("onboarding_drafts", None)

        merchant.name = trading_name
        merchant.industry = business["industry"]
        merchant.metadata = metadata
        merchant.save(update_fields=["name", "industry", "metadata", "updated_at"])
        sync_merchant_kyc_review_from_metadata(merchant, replace_documents=True)

        if mfa.get("enabled"):
            if mfa.get("secret"):
                user.mfa_secret = mfa["secret"]
            user.mfa_enabled = True
        user.onboarding_complete = True
        user.save(update_fields=["mfa_secret_encrypted", "mfa_enabled", "onboarding_complete"])

        imported_plans = []
        if plans["mode"] == "import":
            imported_plans = self._ensure_sample_plans(
                merchant=merchant,
                environment=environment,
                actor_user=user,
                request=request,
            )

        invited = self._ensure_team_invites(
            merchant=merchant,
            actor_user=user,
            team=team,
            request=request,
        )

        log_event(
            action="accounts.onboarding_completed",
            actor_user=user,
            merchant=merchant,
            environment=environment,
            target_type="Merchant",
            target_id=str(merchant.id),
            metadata={
                "plans_mode": plans["mode"],
                "imported_plans": imported_plans,
                "invited_team": invited,
                "mfa_enabled": bool(mfa.get("enabled")),
            },
            request=request,
        )

        return {
            "ok": True,
            "user": merchant_user_payload(user),
            "workspace": WorkspaceSettingsView()._payload(request),
            "importedPlans": imported_plans,
            "invitedTeam": invited,
        }

    def _ensure_sample_plans(self, *, merchant, environment, actor_user, request) -> list[str]:
        product, _ = Product.objects.get_or_create(
            merchant=merchant,
            environment=environment,
            name=f"{merchant.name} Subscriptions",
            defaults={
                "description": "Starter subscription catalog imported during onboarding.",
                "status": Product.Status.ACTIVE,
                "metadata": {"source": "merchant_onboarding"},
            },
        )

        imported = []
        currency = merchant.default_currency or "NGN"
        for index, spec in enumerate(SAMPLE_ONBOARDING_PLANS):
            plan, _ = Plan.objects.get_or_create(
                merchant=merchant,
                environment=environment,
                product=product,
                name=spec["name"],
                defaults={
                    "description": spec["description"],
                    "trial_days": 14 if spec["name"] != "Scale" else 0,
                    "metadata": {"source": "merchant_onboarding", "sort_order": index},
                },
            )
            if not PriceVersion.objects.filter(plan=plan, active_to__isnull=True).exists():
                create_price_version(
                    plan=plan,
                    amount_minor=spec["amount_minor"],
                    currency=currency,
                    interval_unit=PriceVersion.IntervalUnit.MONTH,
                    interval_count=1,
                    actor_user=actor_user,
                    request=request,
                )
            for sort_order, label in enumerate(spec["features"]):
                PlanFeature.objects.get_or_create(
                    plan=plan,
                    label=label,
                    defaults={"sort_order": sort_order},
                )
            activate_plan(plan=plan, actor_user=actor_user, request=request)
            imported.append(plan.name)
        return imported

    def _ensure_team_invites(self, *, merchant, actor_user, team: list[dict], request) -> list[str]:
        invited = []
        seen: set[str] = set()
        for invite in team:
            email = invite["email"].strip().lower()
            if not email or email == actor_user.email.lower() or email in seen:
                continue
            seen.add(email)
            invite_user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    "username": email,
                    "display_name": email.split("@", 1)[0].replace(".", " ").title(),
                    "is_active": True,
                    "email_verified": False,
                    "onboarding_complete": False,
                },
            )
            if created:
                invite_user.set_unusable_password()
                invite_user.save(update_fields=["password"])

            existing = TeamMember.objects.filter(merchant=merchant, user=invite_user).first()
            if existing and existing.status == TeamMember.Status.ACTIVE:
                continue

            role = FRONTEND_TO_ROLE[invite["role"]]
            member, _ = TeamMember.objects.update_or_create(
                merchant=merchant,
                user=invite_user,
                defaults={
                    "role": role,
                    "status": TeamMember.Status.INVITED,
                    "invited_by": actor_user,
                    "invited_at": t.utcnow(),
                },
            )
            self._send_onboarding_invite(member, request)
            invited.append(email)
        return invited

    def _send_onboarding_invite(self, member: TeamMember, request) -> None:
        log_event(
            action="accounts.team_member_invited",
            actor_user=request.user,
            merchant=member.merchant,
            environment=getattr(request, "environment", None),
            target_type="TeamMember",
            target_id=str(member.id),
            metadata={"email": member.user.email, "source": "merchant_onboarding"},
            request=request,
        )
        TeamMemberViewSet()._send_invite(member)


class SignOutView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=None, responses=OpenApiTypes.OBJECT)
    def post(self, request):
        if request.user.is_authenticated:
            log_event(
                action="auth.signout",
                actor_user=request.user,
                actor_label=request.user.email,
                target_type="user",
                target_id=str(request.user.id),
                request=request,
            )
        django_logout(request)
        return Response({"ok": True})


class ImpersonateConsumeView(APIView):
    """Consume a platform-admin impersonation token and start a merchant session.

    Mounted at ``GET /api/v1/auth/impersonate?token=<signed>``.
    The view verifies the signed token (issued by
    ``POST /api/v1/platform/merchants/<id>/impersonate``), establishes a
    Django auth session for the impersonated user, preserves the
    platform admin's own session key so the admin tab stays signed in,
    and redirects to the merchant dashboard root.
    """

    permission_classes = [AllowAny]
    authentication_classes: list = []

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request):
        # Local import to avoid a hard dependency cycle at import time.
        from apps.platform_admin.authentication import SESSION_KEY as PLATFORM_ADMIN_SESSION_KEY
        from apps.platform_admin.services.impersonation import (
            ImpersonationError,
            consume_impersonation_token,
            merchant_dashboard_url,
        )

        token = request.GET.get("token", "").strip()
        try:
            consumed = consume_impersonation_token(token)
        except ImpersonationError as exc:
            return _bad(str(exc))

        # Preserve the platform admin's session identity across the
        # ``django_login`` call (which cycles the session key).
        preserved_admin_id = None
        try:
            preserved_admin_id = request.session.get(PLATFORM_ADMIN_SESSION_KEY)
        except Exception:
            preserved_admin_id = None

        django_login(request, consumed.user)

        if preserved_admin_id:
            request.session[PLATFORM_ADMIN_SESSION_KEY] = preserved_admin_id
            request.session.modified = True

        log_event(
            action="platform.merchant.impersonate.consume",
            actor_user=consumed.user,
            actor_label=consumed.user.email,
            actor_role="platform_admin_impersonation",
            target_type="user",
            target_id=str(consumed.user.id),
            metadata={"admin_id": consumed.admin_id},
            request=request,
        )

        return redirect(merchant_dashboard_url())


class ApiKeyViewSet(viewsets.ModelViewSet):
    serializer_class = ApiKeySerializer
    queryset = ApiKey.objects.all()
    http_method_names = ["get", "head", "options", "post", "delete"]

    def get_queryset(self):
        merchant = getattr(self.request, "merchant", None)
        if merchant is None:
            return ApiKey.objects.none()
        return (
            ApiKey.objects.select_related("environment", "created_by")
            .filter(merchant=merchant)
            .order_by("-created_at")
        )

    def get_permissions(self):
        return [IsAuthenticated(), HasTenantContext(), HasCapability("manage_api_keys")()]

    def create(self, request, *args, **kwargs):
        s = CreateApiKeySerializer(data=request.data)
        s.is_valid(raise_exception=True)
        mode = s.validated_data.get("environment_mode")
        environment = request.environment
        if mode:
            environment = Environment.objects.filter(
                merchant=request.merchant, mode=mode
            ).first()
        if environment is None:
            return Response(
                {"detail": "No environment is available for this merchant."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        issued = create_api_key(
            merchant=request.merchant,
            environment=environment,
            name=s.validated_data["name"],
            scopes=s.validated_data["scopes"],
            created_by=request.user,
        )
        log_event(
            action="accounts.api_key_created",
            actor_user=request.user,
            merchant=request.merchant,
            environment=environment,
            target_type="ApiKey",
            target_id=str(issued.api_key.id),
            metadata={"name": issued.api_key.name, "scopes": issued.api_key.scopes},
            request=request,
        )
        return Response(
            {
                "api_key": ApiKeySerializer(issued.api_key).data,
                "secret": issued.plaintext,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=["get", "post"], url_path="publishable-key")
    def publishable_key(self, request):
        mode = request.query_params.get("mode") if request.method == "GET" else request.data.get("mode")
        if mode not in (Environment.Mode.TEST, Environment.Mode.LIVE, None, ""):
            return Response({"detail": "Mode must be test or live."}, status=status.HTTP_400_BAD_REQUEST)

        environments = Environment.objects.filter(merchant=request.merchant)
        if mode:
            environments = environments.filter(mode=mode)

        if request.method == "POST":
            target_mode = mode or getattr(request.environment, "mode", Environment.Mode.TEST)
            environment = Environment.objects.filter(merchant=request.merchant, mode=target_mode).first()
            if environment is None:
                return Response({"detail": "No environment is available for this merchant."}, status=status.HTTP_400_BAD_REQUEST)
            key = rotate_publishable_key(environment)
            log_event(
                action="accounts.publishable_key_rotated",
                actor_user=request.user,
                merchant=request.merchant,
                environment=environment,
                target_type="Environment",
                target_id=str(environment.id),
                metadata={"mode": environment.mode},
                request=request,
            )
            return Response({"mode": environment.mode, "publishable_key": key})

        keys = [
            {"mode": environment.mode, "publishable_key": ensure_publishable_key(environment)}
            for environment in environments.order_by("mode")
        ]
        return Response({"keys": keys})

    @action(detail=True, methods=["post"])
    def revoke(self, request, pk=None):
        api_key = self.get_object()
        api_key = revoke_api_key(api_key)
        log_event(
            action="accounts.api_key_revoked",
            actor_user=request.user,
            merchant=request.merchant,
            environment=api_key.environment,
            target_type="ApiKey",
            target_id=str(api_key.id),
            metadata={"name": api_key.name},
            request=request,
        )
        return Response(ApiKeySerializer(api_key).data)

    def destroy(self, request, *args, **kwargs):
        self.revoke(request, pk=kwargs.get("pk"))
        return Response(status=status.HTTP_204_NO_CONTENT)


class TeamMemberViewSet(viewsets.ModelViewSet):
    serializer_class = TeamMemberSerializer
    queryset = TeamMember.objects.all()
    http_method_names = ["get", "head", "options", "post", "patch", "delete"]

    def get_queryset(self):
        merchant = getattr(self.request, "merchant", None)
        if merchant is None:
            return TeamMember.objects.none()
        return (
            TeamMember.objects.select_related("user", "merchant", "invited_by")
            .filter(merchant=merchant)
            .order_by("status", "created_at")
        )

    def get_permissions(self):
        return [IsAuthenticated(), HasTenantContext(), HasCapability("manage_team_roles")()]

    def create(self, request, *args, **kwargs):
        s = InviteTeamMemberSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        email = s.validated_data["email"].strip().lower()
        role = FRONTEND_TO_ROLE[s.validated_data["role"]]
        name = s.validated_data.get("name", "").strip() or email.split("@", 1)[0]

        existing = TeamMember.objects.filter(
            merchant=request.merchant, user__email=email
        ).select_related("user").first()
        if existing and existing.status != TeamMember.Status.SUSPENDED:
            return Response(
                {"detail": "This user is already on the team."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user, user_created = User.objects.get_or_create(
            email=email,
            defaults={
                "username": email,
                "display_name": name,
                "email_verified": False,
                "onboarding_complete": False,
                "mfa_enabled": False,
            },
        )
        if not user.display_name:
            user.display_name = name
        update_fields = ["display_name"]
        if user_created:
            user.set_unusable_password()
            update_fields.append("password")
        user.save(update_fields=update_fields)

        member, _ = TeamMember.objects.update_or_create(
            merchant=request.merchant,
            user=user,
            defaults={
                "role": role,
                "status": TeamMember.Status.INVITED,
                "invited_by": request.user,
                "invited_at": t.utcnow(),
            },
        )
        self._send_invite(member)
        log_event(
            action="accounts.team_member_invited",
            actor_user=request.user,
            merchant=request.merchant,
            environment=request.environment,
            target_type="TeamMember",
            target_id=str(member.id),
            metadata={"email": email, "role": s.validated_data["role"]},
            request=request,
        )
        return Response(TeamMemberSerializer(member).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        member = self.get_object()
        if member.role == Role.OWNER:
            return Response(
                {"detail": "Owner role cannot be changed from this endpoint."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        s = UpdateTeamMemberSerializer(data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        role_label = s.validated_data.get("role")
        if role_label:
            member.role = FRONTEND_TO_ROLE[role_label]
            member.save(update_fields=["role", "updated_at"])
            log_event(
                action="accounts.team_member_role_updated",
                actor_user=request.user,
                merchant=request.merchant,
                environment=request.environment,
                target_type="TeamMember",
                target_id=str(member.id),
                metadata={"email": member.user.email, "role": role_label},
                request=request,
            )
        return Response(TeamMemberSerializer(member).data)

    @action(detail=True, methods=["post"], url_path="resend-invite")
    def resend_invite(self, request, pk=None):
        member = self.get_object()
        if member.status != TeamMember.Status.INVITED:
            return Response(
                {"detail": "Only pending invites can be resent."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        self._send_invite(member)
        log_event(
            action="accounts.team_invite_resent",
            actor_user=request.user,
            merchant=request.merchant,
            environment=request.environment,
            target_type="TeamMember",
            target_id=str(member.id),
            metadata={"email": member.user.email},
            request=request,
        )
        return Response(TeamMemberSerializer(member).data)

    @action(detail=True, methods=["post"], url_path="reset-mfa")
    def reset_mfa(self, request, pk=None):
        member = self.get_object()
        if member.role == Role.OWNER and member.user_id == request.user.id:
            return Response(
                {"detail": "You cannot reset your own owner MFA from Team."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        member.user.mfa_enabled = False
        member.user.mfa_secret = ""
        member.user.save(update_fields=["mfa_enabled", "mfa_secret_encrypted"])
        log_event(
            action="accounts.team_member_mfa_reset",
            actor_user=request.user,
            merchant=request.merchant,
            environment=request.environment,
            target_type="TeamMember",
            target_id=str(member.id),
            metadata={"email": member.user.email},
            request=request,
        )
        return Response(TeamMemberSerializer(member).data)

    def destroy(self, request, *args, **kwargs):
        member = self.get_object()
        if member.role == Role.OWNER:
            return Response(
                {"detail": "Owner cannot be removed."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        member.status = TeamMember.Status.SUSPENDED
        member.save(update_fields=["status", "updated_at"])
        log_event(
            action="accounts.team_member_removed",
            actor_user=request.user,
            merchant=request.merchant,
            environment=request.environment,
            target_type="TeamMember",
            target_id=str(member.id),
            metadata={"email": member.user.email},
            request=request,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    def _send_invite(self, member: TeamMember) -> None:
        invite_base = settings.SUBPILOT_FRONTEND_URLS.get("merchant", "http://localhost:5174")
        invite_link = f"{invite_base}/sign-up?email={member.user.email}"
        send_invitation_email.delay(
            email=member.user.email,
            org_name=member.merchant.name,
            invite_link=invite_link,
        )


class WorkspaceSettingsView(APIView):
    permission_classes = [IsAuthenticated, HasTenantContext, HasCapability("manage_dunning_policies")]

    def get(self, request):
        return Response(self._payload(request))

    def patch(self, request):
        s = WorkspaceSettingsSerializer(data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        merchant = request.merchant
        metadata = dict(merchant.metadata or {})

        if "org" in s.validated_data:
            org_patch = s.validated_data["org"]
            org_meta = dict(metadata.get("org") or {})
            org_meta.update(org_patch)
            metadata["org"] = org_meta
            if org_patch.get("trading_name"):
                merchant.name = org_patch["trading_name"]
            if org_patch.get("currency"):
                merchant.default_currency = org_patch["currency"]

        if "dunning" in s.validated_data:
            dunning_patch = s.validated_data["dunning"]
            current = self._dunning_settings(request)
            current.update(dunning_patch)
            metadata["dunning"] = current
            self._sync_dunning_policy(request, current)

        settings_sections = (
            "branding",
            "payouts",
            "plan_defaults",
            "dunning_templates",
            "notifications",
            "security",
            "portal",
        )
        settings_doc = self._settings_document(request)
        for section in settings_sections:
            if section not in s.validated_data:
                continue
            patch = s.validated_data[section]
            if section == "dunning_templates":
                settings_doc[section] = patch
                continue
            current_section = dict(settings_doc.get(section) or {})
            current_section.update(patch)
            settings_doc[section] = current_section
            if section == "branding":
                org_meta = dict(metadata.get("org") or {})
                if patch.get("primary_color"):
                    org_meta["brand_color"] = patch["primary_color"]
                if patch.get("portal_subdomain"):
                    org_meta["portal_subdomain"] = patch["portal_subdomain"]
                metadata["org"] = org_meta
            if section == "payouts":
                org_meta = dict(metadata.get("org") or {})
                if patch.get("descriptor"):
                    org_meta["statement_descriptor"] = patch["descriptor"]
                metadata["org"] = org_meta
            if section == "plan_defaults" and patch.get("currency"):
                merchant.default_currency = patch["currency"]
        metadata["settings"] = settings_doc

        merchant.metadata = metadata
        merchant.save(update_fields=["name", "default_currency", "metadata", "updated_at"])
        log_event(
            action="accounts.workspace_settings_updated",
            actor_user=request.user,
            merchant=merchant,
            environment=request.environment,
            target_type="Merchant",
            target_id=str(merchant.id),
            metadata={"sections": sorted(s.validated_data.keys())},
            request=request,
        )
        return Response(self._payload(request))

    def _payload(self, request) -> dict:
        merchant = request.merchant
        metadata = merchant.metadata or {}
        org_meta = metadata.get("org") or {}
        return {
            "org": {
                "id": str(merchant.id),
                "legal_name": org_meta.get("legal_name") or merchant.name,
                "trading_name": org_meta.get("trading_name") or merchant.name,
                "country": org_meta.get("country") or "Nigeria",
                "timezone": org_meta.get("timezone") or "Africa/Lagos",
                "currency": org_meta.get("currency") or merchant.default_currency,
                "tax_id": org_meta.get("tax_id") or "",
                "statement_descriptor": org_meta.get("statement_descriptor") or merchant.name[:22].upper(),
                "brand_color": org_meta.get("brand_color") or self._settings_document(request)["branding"]["primary_color"],
                "portal_subdomain": org_meta.get("portal_subdomain") or self._settings_document(request)["branding"]["portal_subdomain"],
                "created_at": merchant.created_at,
            },
            "dunning": self._dunning_settings(request),
            "settings": self._settings_document(request),
        }

    def _settings_document(self, request) -> dict:
        merchant = request.merchant
        metadata = merchant.metadata or {}
        stored = metadata.get("settings") if isinstance(metadata.get("settings"), dict) else {}
        org_meta = metadata.get("org") or {}
        defaults = {
            "branding": {
                "primary_color": org_meta.get("brand_color") or "#056058",
                "logo_url": None,
                "portal_subdomain": org_meta.get("portal_subdomain") or merchant.slug,
            },
            "payouts": {
                "bank": org_meta.get("payout_bank") or "GTBank",
                "account_number": org_meta.get("payout_account") or "0123456789",
                "settlement_frequency": org_meta.get("settlement_frequency") or "daily",
                "descriptor": org_meta.get("statement_descriptor") or merchant.name[:22].upper(),
                "paused": False,
            },
            "plan_defaults": {
                "trial_days": 14,
                "proration": "create_proration",
                "currency": merchant.default_currency,
                "tax_behavior": "exclusive",
            },
            "dunning_templates": [
                {
                    "id": "first",
                    "label": "First reminder (12h)",
                    "body": "Hi {{name}}, your last payment didn't go through. Update your card to keep service active.",
                },
                {
                    "id": "second",
                    "label": "Second reminder (24h)",
                    "body": "Hi {{name}}, second attempt failed. Visit your portal to retry payment.",
                },
                {
                    "id": "final",
                    "label": "Final notice (72h)",
                    "body": "Hi {{name}}, this is the final attempt. Service will pause if payment isn't completed today.",
                },
            ],
            "notifications": {
                "invoice": {"email": True, "sms": False, "slack": True},
                "failure": {"email": True, "sms": True, "slack": True},
                "cancellation": {"email": True, "sms": False, "slack": False},
            },
            "security": {
                "require_mfa": True,
                "ip_allowlist": [],
                "session_timeout_minutes": 60,
            },
            "portal": {
                "allow_cancel": True,
                "allow_pause": True,
                "allow_change_plan": True,
                "success_url": customer_portal_url(merchant.slug, "success"),
                "cancel_url": customer_portal_url(merchant.slug, "cancel"),
            },
        }
        merged = {}
        for key, default_value in defaults.items():
            if key == "dunning_templates":
                stored_value = stored.get(key)
                merged[key] = stored_value if isinstance(stored_value, list) and stored_value else default_value
                continue
            stored_value = stored.get(key) if isinstance(stored.get(key), dict) else {}
            merged[key] = {**default_value, **stored_value}
        return merged

    def _dunning_settings(self, request) -> dict:
        metadata = request.merchant.metadata or {}
        existing = metadata.get("dunning")
        if isinstance(existing, dict):
            return {
                "schedule": existing.get("schedule") or [12, 24, 72],
                "max_attempts": existing.get("max_attempts") or len(existing.get("schedule") or [12, 24, 72]),
                "grace_days": existing.get("grace_days") or 3,
                "final_action": existing.get("final_action") or "uncollectible",
            }
        policy = (
            DunningPolicy.objects.filter(
                merchant=request.merchant,
                environment=request.environment,
            )
            .order_by("created_at")
            .first()
        )
        if policy is None:
            return {
                "schedule": [12, 24, 72],
                "max_attempts": 4,
                "grace_days": 3,
                "final_action": "uncollectible",
            }
        schedule = [int(day) * 24 for day in policy.retry_offsets_days]
        return {
            "schedule": schedule or [12, 24, 72],
            "max_attempts": len(policy.retry_offsets_days) or 4,
            "grace_days": policy.grace_period_days,
            "final_action": "uncollectible"
            if policy.final_action == DunningPolicy.FinalAction.MARK_UNCOLLECTIBLE
            else "cancel",
        }

    def _sync_dunning_policy(self, request, settings_payload: dict) -> None:
        policy = (
            DunningPolicy.objects.filter(
                merchant=request.merchant,
                environment=request.environment,
            )
            .order_by("created_at")
            .first()
        )
        if policy is None:
            return
        hours = settings_payload.get("schedule") or [12, 24, 72]
        retry_days = sorted({0 if hour == 0 else max(1, math.ceil(hour / 24)) for hour in hours})
        if not retry_days:
            retry_days = [1]
        update_dunning_policy(
            policy=policy,
            actor_user=request.user,
            request=request,
            retry_offsets_days=retry_days,
            grace_period_days=settings_payload.get("grace_days", policy.grace_period_days),
            final_action=(
                DunningPolicy.FinalAction.MARK_UNCOLLECTIBLE
                if settings_payload.get("final_action") == "uncollectible"
                else DunningPolicy.FinalAction.CANCEL
            ),
        )


class WorkspaceExportView(APIView):
    permission_classes = [IsAuthenticated, HasTenantContext, HasCapability("export_workspace_data")]

    @extend_schema(request=None, responses=OpenApiTypes.OBJECT)
    def post(self, request):
        export = self._queue_export(request)
        return Response(export, status=status.HTTP_202_ACCEPTED)

    @atomic_with_retry
    def _queue_export(self, request) -> dict:
        merchant = request.merchant
        metadata = dict(merchant.metadata or {})
        exports = list(metadata.get("workspace_exports") or [])
        requested_at = t.utcnow()
        export = {
            "id": f"wexp_{uuid.uuid4().hex[:12]}",
            "status": "queued",
            "requested_at": requested_at.isoformat(),
            "estimated_ready_at": (requested_at + t.timedelta(minutes=10)).isoformat(),
            "delivery_email": request.user.email,
        }
        metadata["workspace_exports"] = [export, *exports][:10]
        merchant.metadata = metadata
        merchant.save(update_fields=["metadata", "updated_at"])
        log_event(
            action="accounts.workspace_export_requested",
            actor_user=request.user,
            merchant=merchant,
            environment=request.environment,
            target_type="Merchant",
            target_id=str(merchant.id),
            metadata={"export_id": export["id"], "delivery_email": export["delivery_email"]},
            request=request,
        )
        return export


class WorkspaceForceSignOutView(APIView):
    permission_classes = [IsAuthenticated, HasTenantContext, HasCapability("force_workspace_signout")]

    @extend_schema(request=None, responses=OpenApiTypes.OBJECT)
    def post(self, request):
        result = self._invalidate_sessions(request)
        return Response(result, status=status.HTTP_202_ACCEPTED)

    @atomic_with_retry
    def _invalidate_sessions(self, request) -> dict:
        user_ids = {
            str(user_id)
            for user_id in TeamMember.objects.filter(
                merchant=request.merchant,
                status=TeamMember.Status.ACTIVE,
            ).values_list("user_id", flat=True)
        }
        deleted = 0
        session_keys: list[str] = []

        for session in Session.objects.filter(expire_date__gte=t.utcnow()).iterator():
            data = session.get_decoded()
            if str(data.get("_auth_user_id", "")) in user_ids:
                session_keys.append(session.session_key)

        if session_keys:
            deleted, _ = Session.objects.filter(session_key__in=session_keys).delete()

        log_event(
            action="accounts.workspace_sessions_invalidated",
            actor_user=request.user,
            merchant=request.merchant,
            environment=request.environment,
            target_type="Merchant",
            target_id=str(request.merchant.id),
            metadata={"sessions_invalidated": deleted},
            request=request,
        )
        return {"ok": True, "sessionsInvalidated": deleted}


class WorkspaceTransferOwnershipView(APIView):
    permission_classes = [IsAuthenticated, HasTenantContext, HasCapability("transfer_workspace_ownership")]

    def post(self, request):
        s = TransferWorkspaceOwnershipSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        result = self._transfer(request, s.validated_data["new_owner_email"].strip().lower())
        if isinstance(result, Response):
            return result
        return Response(result)

    @atomic_with_retry
    def _transfer(self, request, new_owner_email: str):
        current_owner = TeamMember.objects.select_related("user").filter(
            merchant=request.merchant,
            user=request.user,
            role=Role.OWNER,
            status=TeamMember.Status.ACTIVE,
        ).first()
        if current_owner is None:
            return Response(
                {"detail": "Only the active workspace owner can transfer ownership."},
                status=status.HTTP_403_FORBIDDEN,
            )

        new_owner = TeamMember.objects.select_related("user").filter(
            merchant=request.merchant,
            user__email=new_owner_email,
            status=TeamMember.Status.ACTIVE,
        ).first()
        if new_owner is None:
            return Response(
                {"detail": "New owner must be an active teammate in this workspace."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if new_owner.user_id == request.user.id:
            return Response(
                {"detail": "Choose a different teammate to receive ownership."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        TeamMember.objects.filter(
            merchant=request.merchant,
            role=Role.OWNER,
            status=TeamMember.Status.ACTIVE,
        ).update(role=Role.BILLING_ADMIN, updated_at=t.utcnow())
        new_owner.role = Role.OWNER
        new_owner.save(update_fields=["role", "updated_at"])

        current_owner.refresh_from_db()
        log_event(
            action="accounts.workspace_ownership_transferred",
            actor_user=request.user,
            merchant=request.merchant,
            environment=request.environment,
            target_type="TeamMember",
            target_id=str(new_owner.id),
            metadata={
                "new_owner_email": new_owner.user.email,
                "previous_owner_email": request.user.email,
            },
            request=request,
        )
        return {
            "ok": True,
            "new_owner": TeamMemberSerializer(new_owner).data,
            "previous_owner": TeamMemberSerializer(current_owner).data,
        }


class WorkspaceCloseView(APIView):
    permission_classes = [IsAuthenticated, HasTenantContext, HasCapability("close_workspace")]

    def post(self, request):
        s = CloseWorkspaceSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        result = self._close(request, s.validated_data["confirm_trading_name"])
        if isinstance(result, Response):
            return result
        return Response(result, status=status.HTTP_202_ACCEPTED)

    @atomic_with_retry
    def _close(self, request, confirm_trading_name: str):
        merchant = request.merchant
        expected_name = WorkspaceSettingsView()._payload(request)["org"]["trading_name"]
        if confirm_trading_name != expected_name:
            return Response(
                {"detail": f'Type "{expected_name}" exactly to confirm.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        closed_at = t.utcnow()
        metadata = dict(merchant.metadata or {})
        metadata["workspace_closure"] = {
            "status": "closed",
            "closed_at": closed_at.isoformat(),
            "closed_by": request.user.email,
        }
        merchant.status = Merchant.Status.CLOSED
        merchant.metadata = metadata
        merchant.save(update_fields=["status", "metadata", "updated_at"])

        ApiKey.objects.filter(merchant=merchant, status=ApiKey.Status.ACTIVE).update(
            status=ApiKey.Status.REVOKED,
            revoked_at=closed_at,
            updated_at=closed_at,
        )
        sessions_invalidated = WorkspaceForceSignOutView()._invalidate_sessions(request)["sessionsInvalidated"]
        TeamMember.objects.filter(merchant=merchant).update(
            status=TeamMember.Status.SUSPENDED,
            updated_at=closed_at,
        )

        log_event(
            action="accounts.workspace_closed",
            actor_user=request.user,
            merchant=merchant,
            environment=request.environment,
            target_type="Merchant",
            target_id=str(merchant.id),
            metadata={
                "closed_by": request.user.email,
                "sessions_invalidated": sessions_invalidated,
            },
            request=request,
        )
        return {"ok": True, "status": "closed", "sessionsInvalidated": sessions_invalidated}


class SigningKeysView(APIView):
    permission_classes = [
        IsAuthenticated,
        HasTenantContext,
        HasCapability("manage_webhook_endpoints"),
    ]

    def get(self, request):
        return Response(signing_key_payload(request.environment))

    def post(self, request):
        s = RotateSigningKeySerializer(data=request.data or {})
        s.is_valid(raise_exception=True)
        payload = rotate_signing_key(
            environment=request.environment,
            grace_hours=s.validated_data["grace_hours"],
            actor_user=request.user,
            request=request,
        )
        return Response(payload)


class NombaIntegrationView(APIView):
    permission_classes = [
        IsAuthenticated,
        HasTenantContext,
        HasCapability("manage_payment_integrations"),
    ]

    def get(self, request):
        env = request.environment
        return Response(self._payload(env))

    def post(self, request):
        s = NombaCredentialSerializer(data=request.data or {})
        s.is_valid(raise_exception=True)
        data = s.validated_data
        env = request.environment
        if "integration_mode" in data:
            env.nomba_integration_mode = data["integration_mode"]
        if "account_id" in data:
            env.nomba_account_id = data["account_id"]
        if "client_id" in data:
            env.nomba_client_id = data["client_id"]
        if data.get("client_secret"):
            env.nomba_client_secret = data["client_secret"]
        if data.get("webhook_secret"):
            env.webhook_secret = data["webhook_secret"]
        if "sub_account_id" in data:
            env.nomba_sub_account_id = data["sub_account_id"]
        env.nomba_access_token = ""
        env.nomba_refresh_token = ""
        env.nomba_token_expires_at = None
        env.nomba_credentials_validated_at = None
        env.nomba_last_validation = {}
        env.save(
            update_fields=[
                "nomba_integration_mode",
                "nomba_account_id",
                "nomba_client_id",
                "nomba_client_secret_encrypted",
                "webhook_secret_encrypted",
                "nomba_sub_account_id",
                "nomba_access_token_encrypted",
                "nomba_refresh_token_encrypted",
                "nomba_token_expires_at",
                "nomba_credentials_validated_at",
                "nomba_last_validation",
                "updated_at",
            ]
        )
        log_event(
            action="payments.nomba_credentials_updated",
            actor_user=request.user,
            merchant=request.merchant,
            environment=env,
            target_type="environment",
            target_id=str(env.id),
            metadata={
                "integration_mode": env.nomba_integration_mode,
                "mode": env.mode,
                "has_client_id": bool(env.nomba_client_id),
                "has_sub_account_id": bool(env.nomba_sub_account_id),
            },
            request=request,
        )
        return Response(self._payload(env))

    def _payload(self, env):
        return {
            "mode": env.mode,
            "integrationMode": env.nomba_integration_mode,
            "accountId": env.nomba_account_id,
            "clientId": env.nomba_client_id,
            "hasClientSecret": bool(env.nomba_client_secret_encrypted),
            "hasWebhookSecret": bool(env.webhook_secret_encrypted),
            "subAccountId": env.nomba_sub_account_id,
            "effectiveSubAccountId": nomba_sub_account_id_for_environment(env),
            "credentialsValidatedAt": env.nomba_credentials_validated_at,
            "liveActive": env.nomba_live_active,
            "lastValidation": env.nomba_last_validation or {},
            "tokenExpiresAt": env.nomba_token_expires_at,
        }


class NombaValidateView(APIView):
    permission_classes = [
        IsAuthenticated,
        HasTenantContext,
        HasCapability("manage_payment_integrations"),
    ]

    def post(self, request):
        try:
            result = validate_nomba_credentials(
                request.environment,
                actor_user=request.user,
                request=request,
            )
        except Exception as exc:
            return Response({"ok": False, "reason": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"ok": True, "validatedAt": result["validated_at"]})


class NombaActivateView(APIView):
    permission_classes = [
        IsAuthenticated,
        HasTenantContext,
        HasCapability("manage_payment_integrations"),
    ]

    def post(self, request):
        try:
            return Response(
                activate_nomba_environment(
                    request.environment,
                    mode=request.environment.mode,
                    actor_user=request.user,
                    request=request,
                )
            )
        except Exception as exc:
            return Response({"ok": False, "reason": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class NombaAccountsSyncView(APIView):
    permission_classes = [
        IsAuthenticated,
        HasTenantContext,
        HasCapability("manage_payment_integrations"),
    ]

    def post(self, request):
        try:
            return Response(sync_nomba_accounts(request.environment, actor_user=request.user, request=request))
        except Exception as exc:
            return Response({"ok": False, "reason": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class NombaSubAccountMapView(APIView):
    permission_classes = [
        IsAuthenticated,
        HasTenantContext,
        HasCapability("manage_payment_integrations"),
    ]

    def post(self, request):
        s = NombaSubAccountSerializer(data=request.data or {})
        s.is_valid(raise_exception=True)
        return Response(
            map_nomba_sub_account(
                request.environment,
                sub_account_id=s.validated_data["sub_account_id"],
                actor_user=request.user,
                request=request,
            )
        )


class NombaBankAccountLookupView(APIView):
    permission_classes = [IsAuthenticated, HasTenantContext]

    def post(self, request):
        serializer = NombaBankAccountLookupSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            result = lookup_nomba_bank_account(
                request.environment,
                bank=data["bank"],
                account_number=data["accountNumber"],
                actor_user=request.user,
                request=request,
            )
        except Exception as exc:
            logger.warning(
                "accounts.nomba_bank_account_lookup_failed",
                extra={
                    "merchant_id": str(request.merchant.id),
                    "environment_id": str(request.environment.id),
                    "bank": data["bank"],
                    "reason": str(exc),
                },
            )
            return Response({"ok": False, "reason": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {
                "ok": True,
                "accountName": result["account_name"],
                "bankName": result["bank_name"],
                "bankCode": result["bank_code"],
                "raw": result["raw"],
            }
        )


class NombaBanksView(APIView):
    permission_classes = [IsAuthenticated, HasTenantContext]

    def get(self, request):
        try:
            result = list_nomba_banks(request.environment)
        except Exception as exc:
            logger.warning(
                "accounts.nomba_banks_fetch_failed",
                extra={
                    "merchant_id": str(request.merchant.id),
                    "environment_id": str(request.environment.id),
                    "reason": str(exc),
                },
            )
            return Response({"ok": False, "reason": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"ok": True, "banks": result["banks"]})
