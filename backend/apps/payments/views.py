"""Payments REST views.

Two surfaces:

1. ``PaymentAttemptViewSet`` — read-only listing/retrieve of attempts
   for the dashboard.
2. ``ProcessorWebhookView`` — public, anonymous endpoint that ingests Nomba
   (or mock) webhooks. Verifies the HMAC-SHA256 signature against
   ``Environment.webhook_secret`` and idempotently routes the event through
   :func:`apps.payments.services.process_processor_event`.
"""
from __future__ import annotations

import csv
import json
import logging
import uuid

from django.conf import settings
from django.db import transaction
from django.db.models import Q, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import Environment, Merchant
from apps.accounts.permissions import HasCapability
from apps.accounts.services.features import disabled_response, get_flag
from apps.audit.services.log_event import log_event
from apps.common.permissions import HasTenantContext
from apps.common.viewsets import TenantScopedViewSet
from apps.invoices.models import CreditNote, Invoice

from .adapters import get_adapter
from .models import BalanceTransaction, PaymentAttempt
from .selectors import payment_attempts_for
from .serializers import (
    ChargeInvoicePayloadSerializer,
    PaymentAttemptSerializer,
    RefundPaymentPayloadSerializer,
    WebhookAckSerializer,
)
from .services import charge_invoice, process_processor_event
from .services.delivery import build_payment_receipt_pdf
from .services.ledger import record_refund_transaction
from .services.nomba import refund_nomba_payment

logger = logging.getLogger(__name__)


def _processor_webhook_signature(request) -> str:
    return (
        request.META.get("HTTP_NOMBA_SIGNATURE")
        or request.META.get("HTTP_NOMBA_SIG_VALUE")
        or request.META.get("HTTP_X_SUBPILOT_SIGNATURE")
        or request.META.get("HTTP_X_NOMBA_SIGNATURE")
        or request.META.get("HTTP_X_WEBHOOK_SIGNATURE")
        or ""
    )


def _processor_webhook_timestamp(request) -> str:
    return request.META.get("HTTP_NOMBA_TIMESTAMP") or ""


def _decode_webhook_json(raw_body: bytes) -> tuple[dict, Response | None]:
    try:
        payload = json.loads(raw_body.decode("utf-8")) if raw_body else {}
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}, Response(
            {"detail": "Invalid JSON body."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if not isinstance(payload, dict):
        return {}, Response(
            {"detail": "Invalid JSON body."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return payload, None


def _webhook_probe_response(*, provider: str, mode: str = "", merchant_id: str = "") -> Response:
    body = {
        "ok": True,
        "provider": provider,
        "mode": mode,
        "merchant_id": merchant_id,
        "accepts": ["POST"],
    }
    return Response(body, status=status.HTTP_200_OK)


def _first_mapping(*values):
    for value in values:
        if isinstance(value, dict):
            return value
    return {}


def _central_webhook_metadata(payload: dict) -> dict:
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    transaction = data.get("transaction") if isinstance(data.get("transaction"), dict) else {}
    return _first_mapping(
        payload.get("metadata"),
        payload.get("orderMetaData"),
        data.get("metadata"),
        data.get("orderMetaData"),
        transaction.get("metadata"),
        transaction.get("orderMetaData"),
    )


def _central_nomba_identifiers(payload: dict) -> list[str]:
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    merchant = data.get("merchant") if isinstance(data.get("merchant"), dict) else {}
    identifiers = [
        merchant.get("walletId"),
        merchant.get("wallet_id"),
        merchant.get("userId"),
        merchant.get("user_id"),
        data.get("walletId"),
        data.get("wallet_id"),
        data.get("merchantId"),
        data.get("merchant_id"),
    ]
    seen = set()
    result = []
    for identifier in identifiers:
        identifier = str(identifier or "").strip()
        if identifier and identifier not in seen:
            seen.add(identifier)
            result.append(identifier)
    return result


def _environment_for_merchant_account(merchant: Merchant) -> Environment | None:
    return (
        Environment.objects.filter(merchant=merchant, mode=Environment.Mode.LIVE)
        .order_by("created_at")
        .first()
        or Environment.objects.filter(merchant=merchant, mode=Environment.Mode.TEST)
        .order_by("created_at")
        .first()
    )


def _resolve_central_nomba_environment(payload: dict, parsed: dict):
    metadata = _central_webhook_metadata(payload)
    invoice_id = str(metadata.get("invoice_id") or metadata.get("invoiceId") or "").strip()
    if invoice_id:
        try:
            invoice = Invoice.objects.select_related("merchant", "environment").get(id=invoice_id)
            return invoice.merchant, invoice.environment
        except (Invoice.DoesNotExist, ValueError):
            pass

    reference = parsed.get("processor_reference") or ""
    if reference:
        attempt = (
            PaymentAttempt.objects.select_related("merchant", "environment")
            .filter(processor_reference=reference)
            .order_by("-created_at")
            .first()
        )
        if attempt is not None:
            return attempt.merchant, attempt.environment

    for identifier in _central_nomba_identifiers(payload):
        environment = (
            Environment.objects.select_related("merchant")
            .filter(Q(nomba_account_id=identifier) | Q(nomba_sub_account_id=identifier))
            .order_by("-mode", "created_at")
            .first()
        )
        if environment is not None:
            return environment.merchant, environment

        merchant = Merchant.objects.filter(nomba_account_id=identifier).first()
        if merchant is not None:
            environment = _environment_for_merchant_account(merchant)
            if environment is not None:
                return merchant, environment

    return None, None


class PaymentAttemptViewSet(TenantScopedViewSet):
    serializer_class = PaymentAttemptSerializer
    queryset = PaymentAttempt.objects.all()
    http_method_names = ["get", "head", "options", "post"]

    def get_base_queryset(self):
        return payment_attempts_for(self.request.merchant, self.request.environment)

    def get_permissions(self):
        if self.action in {"list", "retrieve"}:
            return [
                IsAuthenticated(),
                HasTenantContext(),
                HasCapability("view_dashboard")(),
            ]
        if self.action == "charge":
            return [
                IsAuthenticated(),
                HasTenantContext(),
                HasCapability("retry_invoice")(),
            ]
        if self.action == "refund":
            return [
                IsAuthenticated(),
                HasTenantContext(),
                HasCapability("refund_payment")(),
            ]
        if self.action in {"receipt", "export"}:
            return [
                IsAuthenticated(),
                HasTenantContext(),
                HasCapability("export_invoices")(),
            ]
        return [IsAuthenticated(), HasTenantContext()]

    @action(
        detail=False,
        methods=["post"],
        url_path=r"charge/(?P<invoice_id>[0-9a-f-]+)",
    )
    def charge(self, request, invoice_id=None):
        invoice = get_object_or_404(
            Invoice,
            id=invoice_id,
            merchant=request.merchant,
            environment=request.environment,
        )
        s = ChargeInvoicePayloadSerializer(data=request.data or {})
        s.is_valid(raise_exception=True)
        from apps.customers.models import PaymentMethod
        pm = None
        pm_id = s.validated_data.get("payment_method_id")
        if pm_id:
            pm = get_object_or_404(
                PaymentMethod,
                id=pm_id,
                merchant=request.merchant,
                environment=request.environment,
                customer=invoice.customer,
            )
        outcome = charge_invoice(
            invoice=invoice,
            payment_method=pm,
            adapter_name=s.validated_data.get("adapter") or None,
            actor_user=request.user,
            request=request,
        )
        return Response(
            {
                "attempt": PaymentAttemptSerializer(outcome.attempt).data,
                "success": outcome.result.success,
                "failure_code": outcome.result.failure_code,
                "failure_category": outcome.result.failure_category,
                "processor_reference": outcome.result.processor_reference,
            },
            status=status.HTTP_200_OK if outcome.result.success else status.HTTP_402_PAYMENT_REQUIRED,
        )

    @action(detail=True, methods=["post"], url_path="refund")
    def refund(self, request, pk=None):
        # Feature-flag gate (S13). ``manual_refunds`` defaults on; admins can
        # disable per-merchant from the platform-admin Config sheet.
        if not get_flag(request.merchant, "manual_refunds"):
            return disabled_response("manual_refunds")
        attempt = self.get_object()
        if attempt.status != PaymentAttempt.Status.SUCCEEDED:
            return Response(
                {"detail": f"Cannot refund a {attempt.status} payment."},
                status=status.HTTP_409_CONFLICT,
            )

        s = RefundPaymentPayloadSerializer(data=request.data or {})
        s.is_valid(raise_exception=True)
        refunded_so_far = abs(
            attempt.balance_transactions.filter(type=BalanceTransaction.Type.REFUND).aggregate(
                total=Sum("signed_amount_minor")
            )["total"] or 0
        )
        refundable_minor = max(0, attempt.amount_minor - refunded_so_far)
        if refundable_minor <= 0:
            return Response(
                {"detail": "Payment has already been fully refunded."},
                status=status.HTTP_409_CONFLICT,
            )

        full = s.validated_data.get("full", True)
        amount_minor = (
            refundable_minor
            if full or s.validated_data.get("amount_minor") is None
            else s.validated_data["amount_minor"]
        )
        if amount_minor > refundable_minor:
            return Response(
                {"detail": "Refund amount cannot exceed the remaining refundable amount."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        invoice = attempt.invoice
        reason = (s.validated_data.get("reason") or "").strip()
        provider = getattr(attempt.payment_method, "provider", "")
        if provider == "nomba" and not (attempt.processor_reference or "").startswith("mock_"):
            try:
                refund_nomba_payment(
                    payment_attempt=attempt,
                    amount_minor=amount_minor,
                    reason=reason,
                )
            except Exception as exc:
                return Response(
                    {"detail": f"Nomba refund failed: {str(exc)}"},
                    status=status.HTTP_502_BAD_GATEWAY,
                )

        with transaction.atomic():
            metadata = dict(invoice.metadata or {})
            refunded_at = timezone.now()
            credit_note = CreditNote.objects.create(
                merchant=attempt.merchant,
                environment=attempt.environment,
                invoice=invoice,
                amount_minor=amount_minor,
                currency=attempt.currency,
                reason=CreditNote.Reason.REFUND,
                note=reason,
            )
            record_refund_transaction(
                attempt=attempt,
                amount_minor=amount_minor,
                credit_note=credit_note,
                metadata={"reason": reason, "actor": "merchant"},
            )
            metadata.update(
                {
                    "last_refunded_at": refunded_at.isoformat(),
                    "last_refund_reason": reason,
                    "last_refund_payment_attempt_id": str(attempt.id),
                    "last_refunded_amount_minor": amount_minor,
                    "refunded_amount_minor": refunded_so_far + amount_minor,
                    "refund_full": bool(refunded_so_far + amount_minor >= attempt.amount_minor),
                }
            )
            invoice.metadata = metadata
            invoice.save(update_fields=["metadata", "updated_at"])

            log_event(
                action="payments.payment_refunded",
                actor_user=request.user,
                merchant=attempt.merchant,
                environment=attempt.environment,
                target_type="payment_attempt",
                target_id=str(attempt.id),
                metadata={
                    "invoice_id": str(invoice.id),
                    "amount_minor": amount_minor,
                    "currency": attempt.currency,
                    "reason": reason,
                    "full": bool(refunded_so_far + amount_minor >= attempt.amount_minor),
                    "refunded_so_far_minor": refunded_so_far + amount_minor,
                    "remaining_refundable_minor": max(0, refundable_minor - amount_minor),
                },
                request=request,
            )

        attempt.refresh_from_db()
        return Response(PaymentAttemptSerializer(attempt).data)

    @action(detail=True, methods=["get"], url_path="receipt")
    def receipt(self, request, pk=None):
        attempt = self.get_object()
        filename = f"receipt-{attempt.id}.pdf"
        response = HttpResponse(build_payment_receipt_pdf(attempt), content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response

    @action(detail=False, methods=["get"], url_path="export")
    def export(self, request):
        qs = self._export_queryset(request)
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="subpilot-payments.csv"'
        writer = csv.writer(response)
        writer.writerow(
            [
                "payment_id",
                "invoice_number",
                "customer_name",
                "customer_email",
                "status",
                "channel",
                "currency",
                "amount_minor",
                "refunded_amount_minor",
                "failure_code",
                "failure_message",
                "processor_reference",
                "occurred_at",
            ]
        )
        count = 0
        for attempt in qs:
            metadata = attempt.invoice.metadata or {}
            refunded_amount_minor = 0
            if metadata.get("refund_payment_attempt_id") == str(attempt.id):
                refunded_amount_minor = int(metadata.get("refunded_amount_minor") or 0)
            status_label = self._export_status(attempt, refunded_amount_minor)
            payment_method = attempt.payment_method
            writer.writerow(
                [
                    str(attempt.id),
                    attempt.invoice.number,
                    attempt.invoice.customer.name,
                    attempt.invoice.customer.email,
                    status_label,
                    "card" if payment_method else "unknown",
                    attempt.currency,
                    attempt.amount_minor,
                    refunded_amount_minor,
                    attempt.failure_code,
                    attempt.failure_message,
                    attempt.processor_reference,
                    (metadata.get("refunded_at") or attempt.created_at.isoformat() if attempt.created_at else ""),
                ]
            )
            count += 1

        log_event(
            action="payments.exported",
            actor_user=request.user,
            merchant=request.merchant,
            environment=request.environment,
            target_type="payment_export",
            target_id="csv",
            metadata={
                "row_count": count,
                "status": request.query_params.get("status", ""),
                "channel": request.query_params.get("channel", ""),
                "query": request.query_params.get("q", ""),
            },
            request=request,
        )
        return response

    def _export_queryset(self, request):
        qs = self.get_base_queryset().select_related(
            "invoice",
            "invoice__customer",
            "payment_method",
        ).order_by("-created_at")

        status_param = (request.query_params.get("status") or "").strip()
        if status_param and status_param != "all":
            if status_param == "captured":
                qs = qs.filter(status=PaymentAttempt.Status.SUCCEEDED).exclude(
                    invoice__metadata__refund_payment_attempt_id__isnull=False
                )
            elif status_param == "failed":
                qs = qs.filter(status=PaymentAttempt.Status.FAILED)
            elif status_param == "pending":
                qs = qs.filter(status=PaymentAttempt.Status.PENDING)
            elif status_param == "refunded":
                qs = qs.filter(invoice__metadata__refund_payment_attempt_id__isnull=False)
            elif status_param == "recovered":
                qs = qs.filter(status=PaymentAttempt.Status.SUCCEEDED, attempt_number__gt=1).exclude(
                    invoice__metadata__refund_payment_attempt_id__isnull=False
                )

        channel_param = (request.query_params.get("channel") or "").strip()
        if channel_param and channel_param != "all":
            if channel_param == "card":
                qs = qs.filter(payment_method__isnull=False)
            else:
                qs = qs.none()

        query = (request.query_params.get("q") or "").strip()
        if query:
            query_filter = (
                Q(invoice__number__icontains=query)
                | Q(invoice__customer__name__icontains=query)
                | Q(invoice__customer__email__icontains=query)
                | Q(processor_reference__icontains=query)
            )
            try:
                query_filter |= Q(id=uuid.UUID(query))
            except ValueError:
                pass
            qs = qs.filter(query_filter)
        return qs[:5000]

    def _export_status(self, attempt: PaymentAttempt, refunded_amount_minor: int) -> str:
        if refunded_amount_minor > 0:
            return "refunded"
        if attempt.status == PaymentAttempt.Status.SUCCEEDED:
            return "recovered" if attempt.attempt_number > 1 else "captured"
        return attempt.status


class ProcessorWebhookView(APIView):
    """Public webhook endpoint.

    URL shape:
        ``POST /api/v1/payments/webhooks/<provider>/<merchant_id>/<env_mode>/``

    Headers:
        Nomba: ``nomba-signature`` + ``nomba-timestamp`` per Nomba's HMAC-SHA256
        webhook docs. Mock/local adapters may still use ``X-SubPilot-Signature``.

    Returns 200 with ``{"received": true, "event_id": "..."}`` on success;
    401 on signature mismatch; 404 if the merchant/env is unknown.
    """

    authentication_classes: list = []
    permission_classes = [AllowAny]
    serializer_class = WebhookAckSerializer

    def get(self, request, provider: str, merchant_id: str, mode: str):
        return _webhook_probe_response(
            provider=provider,
            mode=mode,
            merchant_id=str(merchant_id),
        )

    def post(self, request, provider: str, merchant_id: str, mode: str):
        merchant = get_object_or_404(Merchant, id=merchant_id)
        environment = get_object_or_404(Environment, merchant=merchant, mode=mode)

        adapter = get_adapter(provider, environment=environment)
        raw_body = request.body or b""
        signature = _processor_webhook_signature(request)
        timestamp = _processor_webhook_timestamp(request)
        secret = environment.webhook_secret or ""
        if not adapter.verify_webhook(
            payload=raw_body,
            signature=signature,
            secret=secret,
            timestamp=timestamp,
        ):
            logger.warning(
                "payments.webhook_signature_invalid",
                extra={"provider": provider, "merchant_id": str(merchant.id)},
            )
            return Response({"detail": "Invalid signature."}, status=status.HTTP_401_UNAUTHORIZED)

        payload, error = _decode_webhook_json(raw_body)
        if error is not None:
            return error

        parsed = adapter.parse_webhook(payload=payload)
        event = process_processor_event(
            merchant=merchant,
            environment=environment,
            parsed=parsed,
            request=request,
        )
        body = WebhookAckSerializer(
            {"received": True, "event_id": str(event.id)}
        ).data
        return Response(body, status=status.HTTP_200_OK)


class CentralNombaWebhookView(APIView):
    """Platform-managed Nomba webhook endpoint.

    URL shape:
        ``POST /api/v1/payments/webhooks/nomba/``

    This is for the normal mode where SubPilot owns the Nomba integration.
    The endpoint verifies against ``settings.NOMBA_WEBHOOK_SECRET`` first,
    then routes the event to the merchant environment by invoice metadata,
    processor reference, or Nomba wallet/user account identifiers.
    """

    authentication_classes: list = []
    permission_classes = [AllowAny]
    serializer_class = WebhookAckSerializer

    def get(self, request):
        return _webhook_probe_response(provider="nomba", mode="platform")

    def post(self, request):
        adapter = get_adapter("nomba")
        raw_body = request.body or b""
        signature = _processor_webhook_signature(request)
        timestamp = _processor_webhook_timestamp(request)
        secret = getattr(settings, "NOMBA_WEBHOOK_SECRET", "") or ""

        if not secret:
            logger.error("payments.central_nomba_webhook_secret_missing")
            return Response(
                {"detail": "Webhook endpoint is not configured."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        if not adapter.verify_webhook(
            payload=raw_body,
            signature=signature,
            secret=secret,
            timestamp=timestamp,
        ):
            logger.warning("payments.central_nomba_webhook_signature_invalid")
            return Response({"detail": "Invalid signature."}, status=status.HTTP_401_UNAUTHORIZED)

        payload, error = _decode_webhook_json(raw_body)
        if error is not None:
            return error

        parsed = adapter.parse_webhook(payload=payload)
        merchant, environment = _resolve_central_nomba_environment(payload, parsed)
        if merchant is None or environment is None:
            logger.warning(
                "payments.central_nomba_webhook_unroutable",
                extra={"provider_event_id": parsed.get("provider_event_id") or ""},
            )
            return Response(
                {"detail": "Unable to route webhook event."},
                status=status.HTTP_404_NOT_FOUND,
            )

        event = process_processor_event(
            merchant=merchant,
            environment=environment,
            parsed=parsed,
            request=request,
        )
        body = WebhookAckSerializer(
            {"received": True, "event_id": str(event.id)}
        ).data
        return Response(body, status=status.HTTP_200_OK)
