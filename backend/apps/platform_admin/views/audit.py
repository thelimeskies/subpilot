"""Platform-wide audit log endpoint.

Backs the Settings → Audit tab and any future cross-tenant audit views.
Read-only: any active platform admin role can list entries; the table
itself is append-only at the model layer (see
[apps/audit/models.py](file:///Users/mac/Desktop/Projects/HackathonxNomba/backend/apps/audit/models.py)).
"""
from __future__ import annotations

from drf_spectacular.utils import OpenApiTypes, extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from ..authentication import PlatformAdminAuthentication
from ..permissions import IsPlatformAdmin
from ..selectors.audit import list_platform_audit


def _int_param(request, key: str, default: int) -> int:
    raw = request.query_params.get(key)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


def _str_param(request, key: str) -> str | None:
    raw = request.query_params.get(key)
    if raw is None:
        return None
    val = str(raw).strip()
    return val or None


class PlatformAuditLogView(APIView):
    """``GET /api/v1/platform/audit-log`` — paginated platform audit feed."""

    permission_classes = [IsPlatformAdmin]
    authentication_classes = [PlatformAdminAuthentication]

    @extend_schema(tags=["Platform Admin"], responses=OpenApiTypes.OBJECT)
    def get(self, request):
        payload = list_platform_audit(
            page=_int_param(request, "page", 1),
            page_size=_int_param(request, "pageSize", 50),
            category=_str_param(request, "category"),
            search=_str_param(request, "search"),
        )
        return Response({"ok": True, **payload})


__all__ = ["PlatformAuditLogView"]
