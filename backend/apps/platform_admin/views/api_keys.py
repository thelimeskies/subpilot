"""Cross-tenant API keys endpoints (S7).

- ``GET /api/v1/platform/api-keys`` — paginated cross-tenant list.
- ``POST /api/v1/platform/api-keys/<id>/revoke`` — flip status to revoked.

No create / rotate from the platform side; those remain merchant-only.
"""
from __future__ import annotations

from drf_spectacular.utils import OpenApiParameter, OpenApiTypes, extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from ..authentication import PlatformAdminAuthentication
from ..permissions import IsPlatformAdmin
from ..selectors.api_keys import (
    list_api_keys_cross_tenant,
    project_api_key,
)
from ..services.api_key_actions import (
    ApiKeyAlreadyRevokedError,
    ApiKeyNotFoundError,
    revoke_api_key_admin,
)


def _to_int(value: str | None, default: int) -> int:
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _not_found(reason: str = "API key not found.") -> Response:
    return Response({"ok": False, "reason": reason}, status=404)


def _bad(reason: str, code: int = 400) -> Response:
    return Response({"ok": False, "reason": reason}, status=code)


class PlatformApiKeysView(APIView):
    """Paginated cross-tenant API-keys list."""

    permission_classes = [IsPlatformAdmin]
    authentication_classes = [PlatformAdminAuthentication]

    @extend_schema(
        tags=["Platform Admin"],
        parameters=[
            OpenApiParameter("status", OpenApiTypes.STR, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("scope", OpenApiTypes.STR, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("merchant_id", OpenApiTypes.STR, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("environment_id", OpenApiTypes.STR, OpenApiParameter.QUERY, required=False),
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

        items, total = list_api_keys_cross_tenant(
            status=request.query_params.get("status") or None,
            scope=request.query_params.get("scope") or None,
            merchant_id=request.query_params.get("merchant_id") or None,
            environment_id=request.query_params.get("environment_id") or None,
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
                "results": [project_api_key(it) for it in items],
            }
        )


class PlatformApiKeyRevokeView(APIView):
    """Revoke an API key cross-tenant."""

    permission_classes = [IsPlatformAdmin]
    authentication_classes = [PlatformAdminAuthentication]

    @extend_schema(tags=["Platform Admin"], responses=OpenApiTypes.OBJECT)
    def post(self, request, api_key_id):
        try:
            result = revoke_api_key_admin(
                api_key_id=api_key_id,
                admin=getattr(request, "platform_admin", None),
                request=request,
            )
        except ApiKeyNotFoundError:
            return _not_found()
        except ApiKeyAlreadyRevokedError as exc:
            return _bad(str(exc), code=409)
        return Response(
            {
                "ok": True,
                "id": result.api_key_id,
                "status": result.status,
                "revokedAt": result.revoked_at,
            }
        )


__all__ = [
    "PlatformApiKeysView",
    "PlatformApiKeyRevokeView",
]
