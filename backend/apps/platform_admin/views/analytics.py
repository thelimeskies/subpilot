"""Cross-tenant analytics endpoint for the Platform Admin → Analytics page (S11).

``GET /api/v1/platform/analytics?range=3m|6m|12m``

Returns the bundled FE-shape snapshot covering revenueSeries, planRevenue,
regionRevenue, retentionCohorts, acquisitionFunnel, paymentMethodMix,
recoveryFunnel and topMerchantsByRevenue. Each ``range`` value is cached
independently under ``platform:analytics:<range>`` for 15 minutes.

Pass ``?refresh=true`` to force a recompute (audited as
``platform.analytics.refreshed``).
"""
from __future__ import annotations

from drf_spectacular.utils import OpenApiParameter, OpenApiTypes, extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from ..authentication import PlatformAdminAuthentication
from ..permissions import IsPlatformAdmin
from ..selectors.analytics import DEFAULT_RANGE, RANGE_KEYS
from ..services.analytics import (
    get_or_refresh_analytics,
    refresh_platform_analytics,
)


def _truthy(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _coerce_range(value: str | None) -> str:
    if value is None:
        return DEFAULT_RANGE
    cleaned = value.strip().lower()
    return cleaned if cleaned in RANGE_KEYS else DEFAULT_RANGE


class PlatformAnalyticsView(APIView):
    """Cross-tenant analytics snapshot. Authenticated platform admins only."""

    permission_classes = [IsPlatformAdmin]
    authentication_classes = [PlatformAdminAuthentication]

    @extend_schema(
        tags=["Platform Admin"],
        parameters=[
            OpenApiParameter(
                name="range",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Trailing window: '3m', '6m', or '12m' (default).",
            ),
            OpenApiParameter(
                name="refresh",
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
                required=False,
                description="If true, bypass cache and recompute the snapshot.",
            ),
        ],
        responses=OpenApiTypes.OBJECT,
    )
    def get(self, request):
        range_key = _coerce_range(request.query_params.get("range"))
        force = _truthy(request.query_params.get("refresh"))
        admin = getattr(request, "platform_admin", None)
        actor_label = (
            getattr(admin, "display_name", None)
            or getattr(admin, "email", None)
            or "platform_admin"
        )
        if force:
            payload = refresh_platform_analytics(
                range_key=range_key, actor_label=actor_label, request=request
            )
        else:
            payload = get_or_refresh_analytics(
                range_key=range_key, actor_label=actor_label, request=request
            )
        return Response({"ok": True, "analytics": payload})
