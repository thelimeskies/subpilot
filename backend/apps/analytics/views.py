"""Analytics REST views.

[`DashboardOverviewView`](file:///Users/mac/Desktop/Projects/HackathonxNomba/backend/apps/analytics/views.py)
returns the cached merchant + environment metrics snapshot used by the
"Overview" page on the merchant dashboard. ``?refresh=true`` recomputes
on-demand. All capabilities live in
[`apps/accounts/rbac.py`](file:///Users/mac/Desktop/Projects/HackathonxNomba/backend/apps/accounts/rbac.py).
"""
from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import HasCapability
from apps.common.permissions import HasTenantContext

from .selectors import dashboard_overview
from .serializers import DashboardOverviewSerializer
from .services.refresh_metrics import get_cached_overview, refresh_metrics


@extend_schema(responses=DashboardOverviewSerializer)
class DashboardOverviewView(APIView):
    """``GET /api/v1/analytics/overview`` -> :class:`DashboardOverviewSerializer`.

    Reads from cache when available, falls back to on-demand recompute.
    Pass ``?refresh=true`` to force a recomputation + cache write.
    """

    permission_classes = [IsAuthenticated, HasTenantContext, HasCapability("view_dashboard")]

    def get(self, request, *args, **kwargs):
        force = request.query_params.get("refresh", "").lower() in {"1", "true", "yes"}
        if force:
            payload = refresh_metrics(
                merchant=request.merchant,
                environment=request.environment,
                actor_user=request.user,
                request=request,
            )
        else:
            payload = get_cached_overview(
                merchant=request.merchant, environment=request.environment
            )
            if payload is None:
                # First hit: compute synchronously, then cache via refresh_metrics.
                payload = refresh_metrics(
                    merchant=request.merchant,
                    environment=request.environment,
                    actor_user=request.user,
                    request=request,
                )
        return Response(DashboardOverviewSerializer(payload).data)


class DashboardLiveView(APIView):
    """Always-recompute variant — useful for tests + dev panels."""

    permission_classes = [IsAuthenticated, HasTenantContext, HasCapability("view_dashboard")]

    @extend_schema(responses=DashboardOverviewSerializer)
    def get(self, request, *args, **kwargs):
        overview = dashboard_overview(
            merchant=request.merchant, environment=request.environment
        )
        return Response(DashboardOverviewSerializer(overview.as_dict()).data)
