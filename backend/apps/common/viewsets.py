"""Tenant-scoped DRF base viewset.

Forces every queryset to filter by the request's resolved merchant and
environment so views can never accidentally leak across tenants.
"""
from __future__ import annotations

from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from .exceptions import TenantMismatch
from .permissions import HasTenantContext


class TenantScopedViewSet(viewsets.ModelViewSet):
    """Base class for tenant-scoped CRUD viewsets.

    Subclasses set ``queryset`` (or override ``get_base_queryset``) and
    ``serializer_class``. The viewset filters by ``request.merchant`` and
    ``request.environment`` automatically.
    """

    permission_classes = [IsAuthenticated, HasTenantContext]

    # Subclasses MUST set this so DRF's introspection works for OpenAPI.
    queryset = None  # type: ignore[assignment]

    def get_base_queryset(self):
        if self.queryset is None:
            raise NotImplementedError(
                f"{type(self).__name__} must set ``queryset`` or override ``get_base_queryset``."
            )
        return self.queryset.all()

    def get_queryset(self):
        request = self.request
        merchant = getattr(request, "merchant", None)
        environment = getattr(request, "environment", None)
        if merchant is None or environment is None:
            return self.get_base_queryset().none()
        return self.get_base_queryset().filter(merchant=merchant, environment=environment)

    def get_object(self):
        obj = super().get_object()
        # Defensive: confirm the resolved object really is in this tenant.
        if (
            getattr(obj, "merchant_id", None) != self.request.merchant.id
            or getattr(obj, "environment_id", None) != self.request.environment.id
        ):
            raise TenantMismatch()
        return obj
