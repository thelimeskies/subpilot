"""Cross-tenant merchant list endpoint.

``GET /api/v1/platform/merchants?status=&plan=&region=&environment=&q=&page=&page_size=``

Returns the FE-shape Merchant rows defined in
[seed.ts](file:///Users/mac/Desktop/Projects/HackathonxNomba/apps/subpilot-admin/src/data/seed.ts).
"""
from __future__ import annotations

from drf_spectacular.utils import OpenApiParameter, OpenApiTypes, extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from ..authentication import PlatformAdminAuthentication
from ..permissions import IsPlatformAdmin
from ..selectors.merchants import MerchantListItem, list_merchants
from ..services.formatting import format_compact_money, format_pct


def _project(item: MerchantListItem) -> dict:
    return {
        "id": item.id,
        "name": item.name,
        "owner": item.owner,
        "ownerEmail": item.owner_email,
        "plan": item.plan,
        "mrr": format_compact_money(item.mrr_minor, item.currency),
        "status": item.status,
        "failedInvoices": item.failed_invoices,
        "recoveryRate": format_pct(item.recovery_rate_pct),
        "environment": item.environment,
        "createdAt": item.created_at,
        "region": item.region,
        "monthlyVolume": format_compact_money(item.monthly_volume_minor, item.currency),
        "activeSubscriptions": item.active_subscriptions,
        # Raw values for power callers / sorting.
        "raw": {
            "mrrMinor": item.mrr_minor,
            "monthlyVolumeMinor": item.monthly_volume_minor,
            "recoveryRatePct": item.recovery_rate_pct,
            "currency": item.currency,
        },
    }


class PlatformMerchantsView(APIView):
    """Paginated, filterable cross-tenant list."""

    permission_classes = [IsPlatformAdmin]
    authentication_classes = [PlatformAdminAuthentication]

    @extend_schema(
        tags=["Platform Admin"],
        parameters=[
            OpenApiParameter("status", OpenApiTypes.STR, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("plan", OpenApiTypes.STR, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("region", OpenApiTypes.STR, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("environment", OpenApiTypes.STR, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("q", OpenApiTypes.STR, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("page", OpenApiTypes.INT, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("page_size", OpenApiTypes.INT, OpenApiParameter.QUERY, required=False),
        ],
        responses=OpenApiTypes.OBJECT,
    )
    def get(self, request):
        page = max(1, _to_int(request.query_params.get("page"), 1))
        page_size = min(100, max(1, _to_int(request.query_params.get("page_size"), 25)))
        offset = (page - 1) * page_size

        items, total = list_merchants(
            status=request.query_params.get("status") or None,
            plan=request.query_params.get("plan") or None,
            region=request.query_params.get("region") or None,
            environment=request.query_params.get("environment") or None,
            q=request.query_params.get("q") or None,
            limit=page_size,
            offset=offset,
        )
        return Response(
            {
                "ok": True,
                "page": page,
                "pageSize": page_size,
                "total": total,
                "results": [_project(it) for it in items],
            }
        )


def _to_int(value: str | None, default: int) -> int:
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
