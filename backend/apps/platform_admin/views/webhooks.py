"""Cross-tenant webhook deliveries endpoints (S6).

- ``GET /api/v1/platform/webhooks/deliveries`` — paginated cross-tenant list.
- ``POST /api/v1/platform/webhooks/deliveries/<id>/retry`` — re-queue.
- ``GET /api/v1/platform/webhooks/health`` — last-24h aggregate.
"""
from __future__ import annotations

from datetime import datetime, timezone

from drf_spectacular.utils import OpenApiParameter, OpenApiTypes, extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from ..authentication import PlatformAdminAuthentication
from ..permissions import IsPlatformAdmin
from ..selectors.webhooks import (
    aggregate_health,
    list_deliveries_cross_tenant,
    project_delivery,
)
from ..services.webhook_actions import (
    DeliveryNotFoundError,
    DeliveryNotRetriableError,
    OwnerRequiredError,
    retry_delivery_admin,
    rotate_platform_signing_key,
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
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _not_found(reason: str = "Delivery not found.") -> Response:
    return Response({"ok": False, "reason": reason}, status=404)


def _bad(reason: str, code: int = 400) -> Response:
    return Response({"ok": False, "reason": reason}, status=code)


class PlatformWebhookDeliveriesView(APIView):
    """Paginated cross-tenant webhook deliveries list."""

    permission_classes = [IsPlatformAdmin]
    authentication_classes = [PlatformAdminAuthentication]

    @extend_schema(
        tags=["Platform Admin"],
        parameters=[
            OpenApiParameter("status", OpenApiTypes.STR, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("merchant_id", OpenApiTypes.STR, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("event_type", OpenApiTypes.STR, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("endpoint_id", OpenApiTypes.STR, OpenApiParameter.QUERY, required=False),
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

        items, total = list_deliveries_cross_tenant(
            status=request.query_params.get("status") or None,
            merchant_id=request.query_params.get("merchant_id") or None,
            event_type=request.query_params.get("event_type") or None,
            endpoint_id=request.query_params.get("endpoint_id") or None,
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
                "results": [project_delivery(it) for it in items],
            }
        )


class PlatformWebhookRetryView(APIView):
    """Re-queue a failed delivery for retry."""

    permission_classes = [IsPlatformAdmin]
    authentication_classes = [PlatformAdminAuthentication]

    @extend_schema(tags=["Platform Admin"], responses=OpenApiTypes.OBJECT)
    def post(self, request, delivery_id):
        try:
            result = retry_delivery_admin(
                delivery_id=delivery_id,
                admin=getattr(request, "platform_admin", None),
                request=request,
            )
        except DeliveryNotFoundError:
            return _not_found()
        except DeliveryNotRetriableError as exc:
            return _bad(str(exc), code=409)
        return Response(
            {
                "ok": True,
                "id": result.delivery_id,
                "status": result.status,
                "nextAttemptAt": result.next_attempt_at,
                "attempts": result.attempts,
            }
        )


class PlatformWebhookHealthView(APIView):
    """Aggregate health counters for the last 24h."""

    permission_classes = [IsPlatformAdmin]
    authentication_classes = [PlatformAdminAuthentication]

    @extend_schema(
        tags=["Platform Admin"],
        parameters=[
            OpenApiParameter("window_hours", OpenApiTypes.INT, OpenApiParameter.QUERY, required=False),
        ],
        responses=OpenApiTypes.OBJECT,
    )
    def get(self, request):
        window = max(1, min(24 * 30, _to_int(request.query_params.get("window_hours"), 24)))
        data = aggregate_health(window_hours=window)
        return Response({"ok": True, **data})


class PlatformWebhookRotateKeyView(APIView):
    """Rotate the platform-wide outbound webhook signing key (Owner-only)."""

    permission_classes = [IsPlatformAdmin]
    authentication_classes = [PlatformAdminAuthentication]

    @extend_schema(tags=["Platform Admin"], request=OpenApiTypes.OBJECT, responses=OpenApiTypes.OBJECT)
    def post(self, request):
        body = request.data if isinstance(request.data, dict) else {}
        grace = str(body.get("grace_period") or body.get("gracePeriod") or "24h")
        channel = str(body.get("notify_channel") or body.get("notifyChannel") or "email-webhook")
        try:
            result = rotate_platform_signing_key(
                admin=getattr(request, "platform_admin", None) or getattr(request, "user", None),
                grace_period=grace,
                notify_channel=channel,
                request=request,
            )
        except OwnerRequiredError as exc:
            return Response({"ok": False, "reason": str(exc)}, status=403)
        return Response(
            {
                "ok": True,
                "fingerprint": result.fingerprint,
                "rotatedAt": result.rotated_at,
                "gracePeriod": result.grace_period,
            }
        )


__all__ = [
    "PlatformWebhookDeliveriesView",
    "PlatformWebhookRetryView",
    "PlatformWebhookHealthView",
    "PlatformWebhookRotateKeyView",
]
