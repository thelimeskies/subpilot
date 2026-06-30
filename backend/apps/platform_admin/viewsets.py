"""Base viewset for platform admin endpoints.

All `/api/v1/platform/*` viewsets MUST inherit from
``PlatformAdminViewSet`` rather than ``TenantScopedViewSet`` so cross-
tenant queries are explicit and auth is locked to the platform admin
domain.
"""
from __future__ import annotations

from rest_framework import viewsets

from .authentication import PlatformAdminAuthentication
from .permissions import IsPlatformAdmin


class PlatformAdminViewSet(viewsets.GenericViewSet):
    authentication_classes = [PlatformAdminAuthentication]
    permission_classes = [IsPlatformAdmin]
