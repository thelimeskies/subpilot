"""Platform-admin settings endpoint (S10).

Routes:
- ``GET   /api/v1/platform/settings`` — any platform admin can read.
- ``PATCH /api/v1/platform/settings`` — Owner-only update of policy / adapter status.
"""
from __future__ import annotations

from drf_spectacular.utils import OpenApiTypes, extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from ..authentication import PlatformAdminAuthentication
from ..permissions import IsPlatformAdmin
from ..selectors.settings import get_settings_row, project_settings
from ..services.settings import SettingFieldError, update_settings


def _bad(reason: str, code: int = 400) -> Response:
    return Response({"ok": False, "reason": reason}, status=code)


def _forbidden(reason: str) -> Response:
    return Response({"ok": False, "reason": reason}, status=403)


class PlatformSettingsView(APIView):
    """GET (any admin) + PATCH (Owner-only) for the singleton settings row."""

    permission_classes = [IsPlatformAdmin]
    authentication_classes = [PlatformAdminAuthentication]

    @extend_schema(tags=["Platform Admin"], responses=OpenApiTypes.OBJECT)
    def get(self, request):
        row = get_settings_row()
        return Response({"ok": True, "settings": project_settings(row)})

    @extend_schema(tags=["Platform Admin"], responses=OpenApiTypes.OBJECT)
    def patch(self, request):
        actor = getattr(request, "platform_admin", None) or getattr(request, "user", None)
        data = request.data if isinstance(request.data, dict) else {}

        # Accept either snake_case or camelCase from FE clients.
        adapter_status = data.get("adapter_status")
        if adapter_status is None:
            adapter_status = data.get("adapterStatus")
        nomba_platform = data.get("nomba_platform")
        if nomba_platform is None:
            nomba_platform = data.get("nombaPlatform")

        try:
            row = update_settings(
                actor=actor,
                request=request,
                policy=data.get("policy") if "policy" in data else None,
                adapter_status=adapter_status if adapter_status is not None else None,
                nomba_platform=nomba_platform if nomba_platform is not None else None,
            )
        except SettingFieldError as exc:
            msg = str(exc)
            if "Only platform Owners" in msg:
                return _forbidden(msg)
            return _bad(msg)
        return Response({"ok": True, "settings": project_settings(row)})


__all__ = ["PlatformSettingsView"]
