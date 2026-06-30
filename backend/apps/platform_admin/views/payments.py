"""Cross-tenant payments endpoints (S5).

- ``GET /api/v1/platform/payments`` — paginated, filterable list.
- ``POST /api/v1/platform/payments/<id>/refund`` — issue refund.

Returns FE-shape payloads matching
[seed.ts](file:///Users/mac/Desktop/Projects/HackathonxNomba/apps/subpilot-admin/src/data/seed.ts#L120-L131).
"""
from __future__ import annotations

from datetime import datetime, timezone

from drf_spectacular.utils import OpenApiParameter, OpenApiTypes, extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from ..authentication import PlatformAdminAuthentication
from ..permissions import IsPlatformAdmin
from ..selectors.payments import list_payments_cross_tenant, project_payment
from ..services.payment_actions import (
    PaymentNotFoundError,
    PaymentNotRefundableError,
    refund_payment,
)


def _to_int(value: str | None, default: int) -> int:
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    raw = value.strip()
    if not raw:
        return None
    try:
        # ``fromisoformat`` accepts trailing 'Z' from py3.11+.
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _not_found(reason: str = "Payment not found.") -> Response:
    return Response({"ok": False, "reason": reason}, status=404)


def _bad(reason: str, code: int = 400) -> Response:
    return Response({"ok": False, "reason": reason}, status=code)


class PlatformPaymentsListView(APIView):
    """Paginated cross-tenant payments list."""

    permission_classes = [IsPlatformAdmin]
    authentication_classes = [PlatformAdminAuthentication]

    @extend_schema(
        tags=["Platform Admin"],
        parameters=[
            OpenApiParameter("status", OpenApiTypes.STR, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("merchant_id", OpenApiTypes.STR, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("method", OpenApiTypes.STR, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("gateway", OpenApiTypes.STR, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("q", OpenApiTypes.STR, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("date_from", OpenApiTypes.STR, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("date_to", OpenApiTypes.STR, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("page", OpenApiTypes.INT, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("page_size", OpenApiTypes.INT, OpenApiParameter.QUERY, required=False),
        ],
        responses=OpenApiTypes.OBJECT,
    )
    def get(self, request):
        page = max(1, _to_int(request.query_params.get("page"), 1))
        page_size = min(100, max(1, _to_int(request.query_params.get("page_size"), 25)))
        offset = (page - 1) * page_size

        items, total = list_payments_cross_tenant(
            status=request.query_params.get("status") or None,
            merchant_id=request.query_params.get("merchant_id") or None,
            method=request.query_params.get("method") or None,
            gateway=request.query_params.get("gateway") or None,
            q=request.query_params.get("q") or None,
            date_from=_parse_iso(request.query_params.get("date_from")),
            date_to=_parse_iso(request.query_params.get("date_to")),
            limit=page_size,
            offset=offset,
        )
        return Response(
            {
                "ok": True,
                "page": page,
                "pageSize": page_size,
                "total": total,
                "results": [project_payment(it) for it in items],
            }
        )


class PlatformPaymentRefundView(APIView):
    """Issue a refund against a captured payment."""

    permission_classes = [IsPlatformAdmin]
    authentication_classes = [PlatformAdminAuthentication]

    @extend_schema(tags=["Platform Admin"], responses=OpenApiTypes.OBJECT)
    def post(self, request, payment_id):
        data = request.data if isinstance(request.data, dict) else {}
        reason = (data.get("reason") or "").strip()
        note = (data.get("note") or "").strip()
        try:
            result = refund_payment(
                payment_id=payment_id,
                admin=getattr(request, "platform_admin", None),
                reason=reason,
                note=note,
                request=request,
            )
        except PaymentNotFoundError:
            return _not_found()
        except PaymentNotRefundableError as exc:
            return _bad(str(exc), code=409)
        return Response(
            {
                "ok": True,
                "id": result.payment_id,
                "status": result.status,
                "refundedAt": result.refunded_at,
            }
        )


__all__ = ["PlatformPaymentsListView", "PlatformPaymentRefundView"]
