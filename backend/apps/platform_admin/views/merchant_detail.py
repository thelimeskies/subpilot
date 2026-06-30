"""Cross-tenant merchant detail + write actions (S4).

Endpoints:
* ``GET    /api/v1/platform/merchants/<id>``           — full nested detail
* ``POST   /api/v1/platform/merchants/<id>/suspend``    — set status=SUSPENDED
* ``POST   /api/v1/platform/merchants/<id>/reactivate`` — restore status=ACTIVE
* ``POST   /api/v1/platform/merchants/<id>/notes``      — append PlatformMerchantNote
"""
from __future__ import annotations

from drf_spectacular.utils import OpenApiTypes, extend_schema
from rest_framework import status as http_status
from rest_framework.response import Response
from rest_framework.views import APIView

from ..authentication import PlatformAdminAuthentication
from ..permissions import IsPlatformAdmin
from ..selectors.merchant_detail import get_merchant_detail
from ..services.merchant_actions import (
    InvalidStatusTransitionError,
    MerchantNotFoundError,
    OwnerRequiredError,
    add_merchant_note,
    force_close_merchant,
    reactivate_merchant,
    rotate_merchant_webhook_secret,
    suspend_merchant,
)


def _not_found() -> Response:
    return Response({"ok": False, "reason": "Merchant not found."}, status=http_status.HTTP_404_NOT_FOUND)


def _bad(reason: str, code: int = http_status.HTTP_400_BAD_REQUEST) -> Response:
    return Response({"ok": False, "reason": reason}, status=code)


class PlatformMerchantDetailView(APIView):
    permission_classes = [IsPlatformAdmin]
    authentication_classes = [PlatformAdminAuthentication]

    @extend_schema(tags=["Platform Admin"], responses=OpenApiTypes.OBJECT)
    def get(self, request, merchant_id: str):
        payload = get_merchant_detail(merchant_id)
        if payload is None:
            return _not_found()
        return Response({"ok": True, "merchant": payload})


class PlatformMerchantSuspendView(APIView):
    permission_classes = [IsPlatformAdmin]
    authentication_classes = [PlatformAdminAuthentication]

    @extend_schema(tags=["Platform Admin"], request=OpenApiTypes.OBJECT, responses=OpenApiTypes.OBJECT)
    def post(self, request, merchant_id: str):
        body = request.data if isinstance(request.data, dict) else {}
        try:
            result = suspend_merchant(
                merchant_id=merchant_id,
                admin=getattr(request, "user", None),
                reason=str(body.get("reason") or ""),
                note=str(body.get("note") or ""),
                request=request,
            )
        except MerchantNotFoundError:
            return _not_found()
        return Response({"ok": True, "id": result.merchant_id, "status": result.status})


class PlatformMerchantReactivateView(APIView):
    permission_classes = [IsPlatformAdmin]
    authentication_classes = [PlatformAdminAuthentication]

    @extend_schema(tags=["Platform Admin"], request=OpenApiTypes.OBJECT, responses=OpenApiTypes.OBJECT)
    def post(self, request, merchant_id: str):
        body = request.data if isinstance(request.data, dict) else {}
        try:
            result = reactivate_merchant(
                merchant_id=merchant_id,
                admin=getattr(request, "user", None),
                note=str(body.get("note") or ""),
                request=request,
            )
        except MerchantNotFoundError:
            return _not_found()
        except InvalidStatusTransitionError as exc:
            return _bad(str(exc), code=http_status.HTTP_409_CONFLICT)
        return Response({"ok": True, "id": result.merchant_id, "status": result.status})


class PlatformMerchantNoteView(APIView):
    permission_classes = [IsPlatformAdmin]
    authentication_classes = [PlatformAdminAuthentication]

    @extend_schema(tags=["Platform Admin"], request=OpenApiTypes.OBJECT, responses=OpenApiTypes.OBJECT)
    def post(self, request, merchant_id: str):
        body = request.data if isinstance(request.data, dict) else {}
        text = str(body.get("body") or body.get("note") or "").strip()
        if not text:
            return _bad("Note body is required.")
        try:
            result = add_merchant_note(
                merchant_id=merchant_id,
                admin=getattr(request, "user", None),
                body=text,
                visibility=str(body.get("visibility") or "ops"),
                request=request,
            )
        except MerchantNotFoundError:
            return _not_found()
        return Response(
            {"ok": True, "id": result.merchant_id, "noteId": result.note_id},
            status=http_status.HTTP_201_CREATED,
        )


class PlatformMerchantRotateSecretView(APIView):
    """Rotate the per-merchant webhook signing secret (Owner-only)."""

    permission_classes = [IsPlatformAdmin]
    authentication_classes = [PlatformAdminAuthentication]

    @extend_schema(tags=["Platform Admin"], request=OpenApiTypes.OBJECT, responses=OpenApiTypes.OBJECT)
    def post(self, request, merchant_id: str):
        body = request.data if isinstance(request.data, dict) else {}
        grace = str(body.get("grace_period") or body.get("gracePeriod") or "24h")
        try:
            result = rotate_merchant_webhook_secret(
                merchant_id=merchant_id,
                admin=getattr(request, "user", None),
                grace_period=grace,
                request=request,
            )
        except MerchantNotFoundError:
            return _not_found()
        except OwnerRequiredError as exc:
            return Response({"ok": False, "reason": str(exc)}, status=http_status.HTTP_403_FORBIDDEN)
        return Response(
            {
                "ok": True,
                "id": result.merchant_id,
                "fingerprint": result.fingerprint,
                "rotatedAt": result.rotated_at,
                "gracePeriod": result.grace_period,
            }
        )


class PlatformMerchantForceCloseView(APIView):
    """Force-close a merchant (Owner-only). Terminal state."""

    permission_classes = [IsPlatformAdmin]
    authentication_classes = [PlatformAdminAuthentication]

    @extend_schema(tags=["Platform Admin"], request=OpenApiTypes.OBJECT, responses=OpenApiTypes.OBJECT)
    def post(self, request, merchant_id: str):
        body = request.data if isinstance(request.data, dict) else {}
        try:
            result = force_close_merchant(
                merchant_id=merchant_id,
                admin=getattr(request, "user", None),
                note=str(body.get("note") or ""),
                request=request,
            )
        except MerchantNotFoundError:
            return _not_found()
        except OwnerRequiredError as exc:
            return Response({"ok": False, "reason": str(exc)}, status=http_status.HTTP_403_FORBIDDEN)
        return Response({"ok": True, "id": result.merchant_id, "status": result.status})
