"""POST endpoint for issuing a one-time merchant impersonation token.

The actual consumption (session login) happens in
``apps.accounts.views.ImpersonateConsumeView`` so that the Django
session cookie is set on the same backend host the merchant
dashboard talks to.
"""
from __future__ import annotations

from drf_spectacular.utils import OpenApiTypes, extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from ..authentication import PlatformAdminAuthentication
from ..permissions import IsPlatformAdmin
from ..services.impersonation import (
    ImpersonationError,
    MerchantNotImpersonableError,
    issue_impersonation_token,
)


class PlatformMerchantImpersonateView(APIView):
    """Issue a short-lived "Open as merchant" link.

    Body: ``{}`` (no fields required). Returns
    ``{ ok, redirectUrl, userId, userEmail, userName, expiresIn }``.
    """

    permission_classes = [IsPlatformAdmin]
    authentication_classes = [PlatformAdminAuthentication]

    @extend_schema(tags=["Platform Admin"], responses=OpenApiTypes.OBJECT)
    def post(self, request, merchant_id):
        admin = getattr(request, "platform_admin", None) or getattr(request, "user", None)
        try:
            result = issue_impersonation_token(
                merchant_id=str(merchant_id),
                admin=admin,
                request=request,
            )
        except MerchantNotImpersonableError as exc:
            return Response({"ok": False, "reason": str(exc)}, status=409)
        except ImpersonationError as exc:
            return Response({"ok": False, "reason": str(exc)}, status=400)
        from ..services.impersonation import IMPERSONATION_TTL_SECONDS

        return Response(
            {
                "ok": True,
                "redirectUrl": result.redirect_url,
                "userId": result.user_id,
                "userEmail": result.user_email,
                "userName": result.user_name,
                "expiresIn": IMPERSONATION_TTL_SECONDS,
            }
        )


__all__ = ["PlatformMerchantImpersonateView"]
