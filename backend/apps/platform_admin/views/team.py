"""Platform-admin team management endpoints (S9).

Routes:
- ``GET   /api/v1/platform/team`` — list admins (filterable by role/status/q).
- ``POST  /api/v1/platform/team/invite`` — Owner invites a new teammate.
- ``GET   /api/v1/platform/team/<id>`` — admin detail.
- ``PATCH /api/v1/platform/team/<id>`` — Owner updates role/status/display_name.
- ``POST  /api/v1/platform/team/<id>/suspend`` — Owner suspends teammate.
- ``POST  /api/v1/platform/team/<id>/reactivate`` — Owner reactivates teammate.
- ``POST  /api/v1/platform/team/accept-invite`` — public; sets password via token.
"""
from __future__ import annotations

from drf_spectacular.utils import OpenApiParameter, OpenApiTypes, extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from ..authentication import PlatformAdminAuthentication
from ..permissions import IsPlatformAdmin
from ..selectors.team import (
    get_admin,
    list_admins,
    project_admin,
)
from ..services.team import (
    InviteTokenError,
    TeamFieldError,
    TeamNotFoundError,
    accept_invite,
    invite_admin,
    reactivate_admin,
    suspend_admin,
    update_admin,
)


def _to_int(value, default: int) -> int:
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _bad(reason: str, code: int = 400) -> Response:
    return Response({"ok": False, "reason": reason}, status=code)


def _not_found(reason: str = "Not found.") -> Response:
    return Response({"ok": False, "reason": reason}, status=404)


def _forbidden(reason: str) -> Response:
    return Response({"ok": False, "reason": reason}, status=403)


class PlatformTeamView(APIView):
    """List admins + invite (Owner-only for POST)."""

    permission_classes = [IsPlatformAdmin]
    authentication_classes = [PlatformAdminAuthentication]

    @extend_schema(
        tags=["Platform Admin"],
        parameters=[
            OpenApiParameter("role", OpenApiTypes.STR, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("status", OpenApiTypes.STR, OpenApiParameter.QUERY, required=False),
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
        rows, total = list_admins(
            role=request.query_params.get("role") or None,
            status=request.query_params.get("status") or None,
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
                "results": [project_admin(a) for a in rows],
            }
        )


class PlatformTeamInviteView(APIView):
    """POST-only endpoint to invite a new teammate. Owner-only."""

    permission_classes = [IsPlatformAdmin]
    authentication_classes = [PlatformAdminAuthentication]

    @extend_schema(tags=["Platform Admin"], responses=OpenApiTypes.OBJECT)
    def post(self, request):
        actor = getattr(request, "platform_admin", None) or getattr(request, "user", None)
        data = request.data if isinstance(request.data, dict) else {}
        try:
            result = invite_admin(
                email=data.get("email") or "",
                display_name=data.get("display_name") or data.get("displayName") or data.get("name") or "",
                role=data.get("role") or "operator",
                invited_by=actor,
                request=request,
            )
        except TeamFieldError as exc:
            # Owner-gating bubbles up as TeamFieldError; map to 403 when message says so.
            msg = str(exc)
            if "Owner" in msg:
                return _forbidden(msg)
            return _bad(msg)
        return Response(
            {
                "ok": True,
                "admin": project_admin(result.admin, invited_by=(actor.display_name or actor.email)),
                "invite": {
                    "token": result.token.token,
                    "expiresAt": result.token.expires_at.isoformat(),
                    "url": result.invite_url,
                },
            },
            status=201,
        )


class PlatformTeamDetailView(APIView):
    """GET admin detail; PATCH role/status/display_name (Owner-only)."""

    permission_classes = [IsPlatformAdmin]
    authentication_classes = [PlatformAdminAuthentication]

    @extend_schema(tags=["Platform Admin"], responses=OpenApiTypes.OBJECT)
    def get(self, request, admin_id):
        admin = get_admin(admin_id)
        if admin is None:
            return _not_found("Admin not found.")
        return Response({"ok": True, "admin": project_admin(admin)})

    @extend_schema(tags=["Platform Admin"], responses=OpenApiTypes.OBJECT)
    def patch(self, request, admin_id):
        actor = getattr(request, "platform_admin", None) or getattr(request, "user", None)
        data = request.data if isinstance(request.data, dict) else {}
        try:
            target = update_admin(
                admin_id=str(admin_id),
                actor=actor,
                request=request,
                role=data.get("role"),
                status=data.get("status"),
                display_name=data.get("display_name") or data.get("displayName"),
                mfa_enabled=(
                    data.get("mfa_enabled")
                    if "mfa_enabled" in data
                    else data.get("mfaEnabled")
                    if "mfaEnabled" in data
                    else None
                ),
            )
        except TeamNotFoundError:
            return _not_found("Admin not found.")
        except TeamFieldError as exc:
            msg = str(exc)
            if "Owner" in msg and "Only platform Owners" in msg:
                return _forbidden(msg)
            return _bad(msg)
        return Response({"ok": True, "admin": project_admin(target)})


class PlatformTeamSuspendView(APIView):
    """POST-only suspend endpoint."""

    permission_classes = [IsPlatformAdmin]
    authentication_classes = [PlatformAdminAuthentication]

    @extend_schema(tags=["Platform Admin"], responses=OpenApiTypes.OBJECT)
    def post(self, request, admin_id):
        actor = getattr(request, "platform_admin", None) or getattr(request, "user", None)
        try:
            target = suspend_admin(admin_id=str(admin_id), actor=actor, request=request)
        except TeamNotFoundError:
            return _not_found("Admin not found.")
        except TeamFieldError as exc:
            msg = str(exc)
            if "Only platform Owners" in msg:
                return _forbidden(msg)
            return _bad(msg)
        return Response({"ok": True, "admin": project_admin(target)})


class PlatformTeamReactivateView(APIView):
    """POST-only reactivate endpoint."""

    permission_classes = [IsPlatformAdmin]
    authentication_classes = [PlatformAdminAuthentication]

    @extend_schema(tags=["Platform Admin"], responses=OpenApiTypes.OBJECT)
    def post(self, request, admin_id):
        actor = getattr(request, "platform_admin", None) or getattr(request, "user", None)
        try:
            target = reactivate_admin(admin_id=str(admin_id), actor=actor, request=request)
        except TeamNotFoundError:
            return _not_found("Admin not found.")
        except TeamFieldError as exc:
            msg = str(exc)
            if "Only platform Owners" in msg:
                return _forbidden(msg)
            return _bad(msg)
        return Response({"ok": True, "admin": project_admin(target)})


class PlatformTeamAcceptInviteView(APIView):
    """Public endpoint that consumes an invite token to set a password."""

    permission_classes = [AllowAny]
    authentication_classes: list = []

    @extend_schema(tags=["Platform Admin"], responses=OpenApiTypes.OBJECT)
    def post(self, request):
        data = request.data if isinstance(request.data, dict) else {}
        try:
            admin = accept_invite(
                token_value=data.get("token") or "",
                password=data.get("password") or "",
                display_name=data.get("display_name") or data.get("displayName"),
                request=request,
            )
        except InviteTokenError as exc:
            return _bad(str(exc))
        return Response({"ok": True, "admin": project_admin(admin)})


__all__ = [
    "PlatformTeamView",
    "PlatformTeamInviteView",
    "PlatformTeamDetailView",
    "PlatformTeamSuspendView",
    "PlatformTeamReactivateView",
    "PlatformTeamAcceptInviteView",
]
