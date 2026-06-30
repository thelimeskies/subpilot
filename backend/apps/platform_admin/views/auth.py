"""Platform admin auth endpoints under ``/api/v1/platform/auth/``.

Response envelope mirrors the merchant flow at
[apps/accounts/views.py](file:///Users/mac/Desktop/Projects/HackathonxNomba/backend/apps/accounts/views.py)
for FE consistency: ``{ok: true, ...}`` or ``{ok: false, reason}``.
"""
from __future__ import annotations

from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from drf_spectacular.utils import OpenApiTypes, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from ..authentication import PlatformAdminAuthentication
from ..models import PlatformAdmin
from ..permissions import IsPlatformAdmin
from ..serializers import SignInSerializer, admin_payload
from ..services.auth import (
    InvalidCredentialsError,
    ProfileUpdateError,
    SuspendedAdminError,
    sign_in,
    sign_out,
    update_profile,
)


def _bad(reason: str) -> Response:
    return Response({"ok": False, "reason": reason}, status=status.HTTP_200_OK)


def _first_error(serializer) -> str:
    for _f, errs in serializer.errors.items():
        if isinstance(errs, list) and errs:
            return str(errs[0])
    return "Invalid request."


class PlatformSignInView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []
    serializer_class = SignInSerializer

    @extend_schema(tags=["Platform Admin"], request=SignInSerializer, responses=OpenApiTypes.OBJECT)
    def post(self, request):
        s = SignInSerializer(data=request.data)
        if not s.is_valid():
            return _bad(_first_error(s))
        try:
            result = sign_in(
                email=s.validated_data["email"],
                password=s.validated_data["password"],
                request=request,
            )
        except InvalidCredentialsError as exc:
            return _bad(str(exc))
        except SuspendedAdminError as exc:
            return _bad(str(exc))
        return Response({"ok": True, "user": admin_payload(result.admin)})


class PlatformSignOutView(APIView):
    """Sign-out is path-driven: even if the cookie is missing we clear
    state and return ok."""

    permission_classes = [AllowAny]
    authentication_classes = [PlatformAdminAuthentication]

    @extend_schema(tags=["Platform Admin"], request=None, responses=OpenApiTypes.OBJECT)
    def post(self, request):
        sign_out(request=request)
        return Response({"ok": True})


class PlatformMeView(APIView):
    """Returns the current platform admin or ``{user: null}`` if anonymous.

    Always sets the CSRF cookie so the FE can issue subsequent writes.
    """

    permission_classes = [AllowAny]
    authentication_classes = [PlatformAdminAuthentication]

    @method_decorator(ensure_csrf_cookie)
    @extend_schema(tags=["Platform Admin"], responses=OpenApiTypes.OBJECT)
    def get(self, request):
        user = getattr(request, "user", None)
        if isinstance(user, PlatformAdmin):
            return Response({"ok": True, "user": admin_payload(user)})
        return Response({"ok": True, "user": None})

    @extend_schema(tags=["Platform Admin"], request=OpenApiTypes.OBJECT, responses=OpenApiTypes.OBJECT)
    def patch(self, request):
        """Update the signed-in admin's display name / email.

        Returns the same shape as ``GET /me`` so the FE can swap the
        cached AdminUser in one call. ``role`` and ``status`` are
        intentionally not editable here — those are managed via the
        Team management endpoints in :mod:`views.team`.
        """
        user = getattr(request, "user", None)
        if not isinstance(user, PlatformAdmin):
            return Response({"ok": False, "reason": "Authentication required."}, status=status.HTTP_401_UNAUTHORIZED)

        data = request.data if isinstance(request.data, dict) else {}
        display_name = data.get("display_name", data.get("displayName", data.get("name")))
        email = data.get("email")

        try:
            updated = update_profile(
                admin=user,
                display_name=display_name,
                email=email,
                request=request,
            )
        except ProfileUpdateError as exc:
            return Response({"ok": False, "reason": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"ok": True, "user": admin_payload(updated)})


class PlatformForgotPasswordView(APIView):
    """Stub. Always returns 202 to avoid email enumeration."""

    permission_classes = [AllowAny]
    authentication_classes: list = []

    @extend_schema(tags=["Platform Admin"], request=OpenApiTypes.OBJECT, responses=OpenApiTypes.OBJECT)
    def post(self, request):
        # In a full deployment this would mint a PlatformInviteToken-style
        # reset row and email it. For S1 we keep it as a no-op stub so the
        # FE flow is unblocked.
        return Response({"ok": True}, status=status.HTTP_202_ACCEPTED)


# IsPlatformAdmin-protected probe used by E2E tests to verify isolation.
class PlatformPingView(APIView):
    permission_classes = [IsPlatformAdmin]
    authentication_classes = [PlatformAdminAuthentication]

    @extend_schema(tags=["Platform Admin"], responses=OpenApiTypes.OBJECT)
    def get(self, request):
        return Response({"ok": True, "service": "platform-admin"})
