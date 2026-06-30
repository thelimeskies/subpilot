"""Cross-tenant overview endpoint for the platform admin dashboard.

``GET /api/v1/platform/overview`` — returns the cached snapshot, projecting
the cross-tenant aggregates into the camelCase ``platformStats`` shape the
FE seed expects.

Pass ``?refresh=true`` to force a recompute (audited as a separate
``platform.overview.refreshed`` event tagged with the actor).
"""
from __future__ import annotations

from drf_spectacular.utils import OpenApiParameter, OpenApiTypes, extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from ..authentication import PlatformAdminAuthentication
from ..permissions import IsPlatformAdmin
from ..services.overview import (
    get_or_refresh_overview,
    refresh_platform_overview,
)


def _truthy(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


class PlatformOverviewView(APIView):
    """Cross-tenant dashboard snapshot. Authenticated platform admins only."""

    permission_classes = [IsPlatformAdmin]
    authentication_classes = [PlatformAdminAuthentication]

    @extend_schema(
        tags=["Platform Admin"],
        parameters=[
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
        force = _truthy(request.query_params.get("refresh"))
        actor_label = getattr(request.user, "email", None) or "platform_admin"
        if force:
            payload = refresh_platform_overview(
                actor_label=actor_label, request=request
            )
        else:
            payload = get_or_refresh_overview(
                actor_label=actor_label, request=request
            )
        return Response({"ok": True, "stats": payload})
