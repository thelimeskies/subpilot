"""Tenant-scoped account resource routes mounted at ``/api/v1/``."""
from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    ApiKeyViewSet,
    CompleteOnboardingView,
    MeFeaturesView,
    OnboardingDraftView,
    SigningKeysView,
    TeamMemberViewSet,
    WorkspaceCloseView,
    WorkspaceExportView,
    WorkspaceForceSignOutView,
    WorkspaceSettingsView,
    WorkspaceTransferOwnershipView,
)

router = DefaultRouter(trailing_slash=True)
router.register(r"api-keys", ApiKeyViewSet, basename="api-key")
router.register(r"team-members", TeamMemberViewSet, basename="team-member")

urlpatterns = [
    path("me/features", MeFeaturesView.as_view(), name="me-features"),
    path("onboarding/draft/", OnboardingDraftView.as_view(), name="onboarding-draft"),
    path("onboarding/complete/", CompleteOnboardingView.as_view(), name="onboarding-complete"),
    path("workspace-settings/", WorkspaceSettingsView.as_view(), name="workspace-settings"),
    path("workspace-settings/export/", WorkspaceExportView.as_view(), name="workspace-settings-export"),
    path("workspace-settings/force-sign-out/", WorkspaceForceSignOutView.as_view(), name="workspace-settings-force-sign-out"),
    path("workspace-settings/transfer-ownership/", WorkspaceTransferOwnershipView.as_view(), name="workspace-settings-transfer-ownership"),
    path("workspace-settings/close/", WorkspaceCloseView.as_view(), name="workspace-settings-close"),
    path("signing-keys/", SigningKeysView.as_view(), name="signing-keys"),
    path("signing-keys/rotate/", SigningKeysView.as_view(), name="signing-keys-rotate"),
    *router.urls,
]
