"""URL routes for the platform admin app.

Mounted by [config/urls.py](file:///Users/mac/Desktop/Projects/HackathonxNomba/backend/config/urls.py)
under ``/api/v1/platform/``.
"""
from __future__ import annotations

from django.urls import path

from .views.auth import (
    PlatformForgotPasswordView,
    PlatformMeView,
    PlatformPingView,
    PlatformSignInView,
    PlatformSignOutView,
)
from .views.overview import PlatformOverviewView
from .views.merchants import PlatformMerchantsView
from .views.merchant_detail import (
    PlatformMerchantDetailView,
    PlatformMerchantForceCloseView,
    PlatformMerchantNoteView,
    PlatformMerchantReactivateView,
    PlatformMerchantRotateSecretView,
    PlatformMerchantSuspendView,
)
from .views.impersonation import PlatformMerchantImpersonateView
from .views.merchant_tabs import (
    PlatformMerchantAuditView,
    PlatformMerchantConfigView,
    PlatformMerchantPaymentsView,
    PlatformMerchantSubscriptionsView,
    PlatformMerchantWebhooksView,
)
from .views.payments import (
    PlatformPaymentRefundView,
    PlatformPaymentsListView,
)
from .views.webhooks import (
    PlatformWebhookDeliveriesView,
    PlatformWebhookHealthView,
    PlatformWebhookRetryView,
    PlatformWebhookRotateKeyView,
)
from .views.api_keys import (
    PlatformApiKeyRevokeView,
    PlatformApiKeysView,
)
from .views.support import (
    PlatformKycView,
    PlatformTicketDetailView,
    PlatformTicketRepliesView,
    PlatformTicketsView,
)
from .views.team import (
    PlatformTeamAcceptInviteView,
    PlatformTeamDetailView,
    PlatformTeamInviteView,
    PlatformTeamReactivateView,
    PlatformTeamSuspendView,
    PlatformTeamView,
)
from .views.settings import PlatformSettingsView
from .views.analytics import PlatformAnalyticsView
from .views.audit import PlatformAuditLogView

urlpatterns = [
    # Auth
    path("auth/sign-in", PlatformSignInView.as_view(), name="platform-sign-in"),
    path("auth/sign-out", PlatformSignOutView.as_view(), name="platform-sign-out"),
    path("auth/me", PlatformMeView.as_view(), name="platform-me"),
    path("auth/forgot", PlatformForgotPasswordView.as_view(), name="platform-forgot"),
    # Health probe (also used as the canonical isolation negative-test target).
    path("ping", PlatformPingView.as_view(), name="platform-ping"),
    # Dashboard
    path("overview", PlatformOverviewView.as_view(), name="platform-overview"),
    # Merchants
    path("merchants", PlatformMerchantsView.as_view(), name="platform-merchants"),
    path("merchants/<uuid:merchant_id>", PlatformMerchantDetailView.as_view(), name="platform-merchant-detail"),
    path("merchants/<uuid:merchant_id>/suspend", PlatformMerchantSuspendView.as_view(), name="platform-merchant-suspend"),
    path("merchants/<uuid:merchant_id>/reactivate", PlatformMerchantReactivateView.as_view(), name="platform-merchant-reactivate"),
    path("merchants/<uuid:merchant_id>/notes", PlatformMerchantNoteView.as_view(), name="platform-merchant-notes"),
    path("merchants/<uuid:merchant_id>/webhooks/rotate-secret", PlatformMerchantRotateSecretView.as_view(), name="platform-merchant-rotate-secret"),
    path("merchants/<uuid:merchant_id>/force-close", PlatformMerchantForceCloseView.as_view(), name="platform-merchant-force-close"),
    path("merchants/<uuid:merchant_id>/impersonate", PlatformMerchantImpersonateView.as_view(), name="platform-merchant-impersonate"),
    # Per-tab merchant detail endpoints (S13)
    path("merchants/<uuid:merchant_id>/subscriptions", PlatformMerchantSubscriptionsView.as_view(), name="platform-merchant-subscriptions"),
    path("merchants/<uuid:merchant_id>/payments", PlatformMerchantPaymentsView.as_view(), name="platform-merchant-payments"),
    path("merchants/<uuid:merchant_id>/webhooks", PlatformMerchantWebhooksView.as_view(), name="platform-merchant-webhooks"),
    path("merchants/<uuid:merchant_id>/audit", PlatformMerchantAuditView.as_view(), name="platform-merchant-audit"),
    path("merchants/<uuid:merchant_id>/config", PlatformMerchantConfigView.as_view(), name="platform-merchant-config"),
    # Payments
    path("payments", PlatformPaymentsListView.as_view(), name="platform-payments"),
    path("payments/<uuid:payment_id>/refund", PlatformPaymentRefundView.as_view(), name="platform-payment-refund"),
    # Webhooks
    path("webhooks/deliveries", PlatformWebhookDeliveriesView.as_view(), name="platform-webhook-deliveries"),
    path("webhooks/deliveries/<uuid:delivery_id>/retry", PlatformWebhookRetryView.as_view(), name="platform-webhook-retry"),
    path("webhooks/health", PlatformWebhookHealthView.as_view(), name="platform-webhook-health"),
    path("webhooks/rotate-key", PlatformWebhookRotateKeyView.as_view(), name="platform-webhook-rotate-key"),
    # API keys
    path("api-keys", PlatformApiKeysView.as_view(), name="platform-api-keys"),
    path("api-keys/<uuid:api_key_id>/revoke", PlatformApiKeyRevokeView.as_view(), name="platform-api-key-revoke"),
    # Support tickets
    path("tickets", PlatformTicketsView.as_view(), name="platform-tickets"),
    path("tickets/<uuid:ticket_id>", PlatformTicketDetailView.as_view(), name="platform-ticket-detail"),
    path("tickets/<uuid:ticket_id>/replies", PlatformTicketRepliesView.as_view(), name="platform-ticket-replies"),
    # KYC reviews
    path("kyc/<uuid:merchant_id>", PlatformKycView.as_view(), name="platform-kyc"),
    # Team / Admin management (S9)
    path("team", PlatformTeamView.as_view(), name="platform-team"),
    path("team/invite", PlatformTeamInviteView.as_view(), name="platform-team-invite"),
    path("team/accept-invite", PlatformTeamAcceptInviteView.as_view(), name="platform-team-accept-invite"),
    path("team/<uuid:admin_id>", PlatformTeamDetailView.as_view(), name="platform-team-detail"),
    path("team/<uuid:admin_id>/suspend", PlatformTeamSuspendView.as_view(), name="platform-team-suspend"),
    path("team/<uuid:admin_id>/reactivate", PlatformTeamReactivateView.as_view(), name="platform-team-reactivate"),
    # Settings (S10)
    path("settings", PlatformSettingsView.as_view(), name="platform-settings"),
    # Analytics (S11)
    path("analytics", PlatformAnalyticsView.as_view(), name="platform-analytics"),
    # Cross-tenant audit log (Settings → Audit tab)
    path("audit-log", PlatformAuditLogView.as_view(), name="platform-audit-log"),
]
