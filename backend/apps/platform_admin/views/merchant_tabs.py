"""Per-merchant tab views (S13).

Each tab on the Merchant Detail page in the platform admin FE has its
own paginated endpoint here. The Overview tab keeps using
:class:`apps.platform_admin.views.merchant_detail.PlatformMerchantDetailView`;
this module covers Subscriptions, Payments, Webhooks, Audit, and Config
(GET + PATCH).

All views inherit the standard platform gate
(`IsPlatformAdmin` + ``PlatformAdminAuthentication``). The Config PATCH
adds an Owner-only check by routing through
:func:`services.merchant_config.update_merchant_config`, which raises
``OwnerRequiredError`` → 403 if the caller is not an Owner.
"""
from __future__ import annotations

from drf_spectacular.utils import OpenApiTypes, extend_schema
from rest_framework import status as http_status
from rest_framework.response import Response
from rest_framework.views import APIView

from ..authentication import PlatformAdminAuthentication
from ..permissions import IsPlatformAdmin
from ..selectors.merchant_tabs import (
    list_merchant_audit,
    list_merchant_payments,
    list_merchant_subscriptions,
    list_merchant_webhooks,
)
from ..services.merchant_config import (
    MerchantNotFoundError,
    OwnerRequiredError,
    UnknownFeatureFlagError,
    get_merchant_config_bundle,
    update_merchant_config,
)


# --- Helpers ---------------------------------------------------------------


def _not_found() -> Response:
    return Response(
        {"ok": False, "reason": "Merchant not found."},
        status=http_status.HTTP_404_NOT_FOUND,
    )


def _bad(reason: str, code: int = http_status.HTTP_400_BAD_REQUEST) -> Response:
    return Response({"ok": False, "reason": reason}, status=code)


def _forbidden(reason: str) -> Response:
    return Response({"ok": False, "reason": reason}, status=http_status.HTTP_403_FORBIDDEN)


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


# --- Subscriptions ---------------------------------------------------------


class PlatformMerchantSubscriptionsView(APIView):
    permission_classes = [IsPlatformAdmin]
    authentication_classes = [PlatformAdminAuthentication]

    @extend_schema(tags=["Platform Admin"], responses=OpenApiTypes.OBJECT)
    def get(self, request, merchant_id: str):
        payload = list_merchant_subscriptions(
            merchant_id=merchant_id,
            page=_int_param(request, "page", 1),
            page_size=_int_param(request, "pageSize", 25),
            status=_str_param(request, "status"),
        )
        if payload is None:
            return _not_found()
        return Response({"ok": True, **payload})


# --- Payments --------------------------------------------------------------


class PlatformMerchantPaymentsView(APIView):
    permission_classes = [IsPlatformAdmin]
    authentication_classes = [PlatformAdminAuthentication]

    @extend_schema(tags=["Platform Admin"], responses=OpenApiTypes.OBJECT)
    def get(self, request, merchant_id: str):
        payload = list_merchant_payments(
            merchant_id=merchant_id,
            page=_int_param(request, "page", 1),
            page_size=_int_param(request, "pageSize", 25),
            status=_str_param(request, "status"),
        )
        if payload is None:
            return _not_found()
        return Response({"ok": True, **payload})


# --- Webhooks --------------------------------------------------------------


class PlatformMerchantWebhooksView(APIView):
    permission_classes = [IsPlatformAdmin]
    authentication_classes = [PlatformAdminAuthentication]

    @extend_schema(tags=["Platform Admin"], responses=OpenApiTypes.OBJECT)
    def get(self, request, merchant_id: str):
        payload = list_merchant_webhooks(
            merchant_id=merchant_id,
            page=_int_param(request, "page", 1),
            page_size=_int_param(request, "pageSize", 25),
            status=_str_param(request, "status"),
            event_type=_str_param(request, "eventType"),
        )
        if payload is None:
            return _not_found()
        return Response({"ok": True, **payload})


# --- Audit -----------------------------------------------------------------


class PlatformMerchantAuditView(APIView):
    permission_classes = [IsPlatformAdmin]
    authentication_classes = [PlatformAdminAuthentication]

    @extend_schema(tags=["Platform Admin"], responses=OpenApiTypes.OBJECT)
    def get(self, request, merchant_id: str):
        payload = list_merchant_audit(
            merchant_id=merchant_id,
            page=_int_param(request, "page", 1),
            page_size=_int_param(request, "pageSize", 25),
            action=_str_param(request, "action"),
        )
        if payload is None:
            return _not_found()
        return Response({"ok": True, **payload})


# --- Config (GET + PATCH) --------------------------------------------------


class PlatformMerchantConfigView(APIView):
    """Read + write per-merchant operational config.

    * ``GET`` is allowed to any active platform admin (read-only roles
      can inspect).
    * ``PATCH`` is **Owner-only**. Operator/Support/Read-only get 403
      via :class:`OwnerRequiredError` raised inside the service layer.
    """

    permission_classes = [IsPlatformAdmin]
    authentication_classes = [PlatformAdminAuthentication]

    @extend_schema(tags=["Platform Admin"], responses=OpenApiTypes.OBJECT)
    def get(self, request, merchant_id: str):
        bundle = get_merchant_config_bundle(merchant_id)
        if bundle is None:
            return _not_found()
        return Response({"ok": True, "config": bundle})

    @extend_schema(
        tags=["Platform Admin"],
        request=OpenApiTypes.OBJECT,
        responses=OpenApiTypes.OBJECT,
    )
    def patch(self, request, merchant_id: str):
        body = request.data if isinstance(request.data, dict) else {}
        # Accept both snake_case and camelCase keys.
        feature_flags = body.get("feature_flags", body.get("featureFlags"))
        limits = body.get("limits")
        retry_policy = body.get("retry_policy", body.get("retryPolicy"))

        try:
            result = update_merchant_config(
                merchant_id=merchant_id,
                admin=getattr(request, "user", None),
                feature_flags=feature_flags,
                limits=limits,
                retry_policy=retry_policy,
                request=request,
            )
        except MerchantNotFoundError:
            return _not_found()
        except OwnerRequiredError as exc:
            return _forbidden(str(exc))
        except UnknownFeatureFlagError as exc:
            return _bad(str(exc))
        except ValueError as exc:
            return _bad(str(exc))

        bundle = get_merchant_config_bundle(result.merchant_id)
        return Response(
            {
                "ok": True,
                "config": bundle,
                "changed": list(result.changed_keys),
            }
        )
