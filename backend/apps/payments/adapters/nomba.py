"""Nomba payment adapter backed by the OAuth-aware integration client."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
from decimal import Decimal
from typing import Any

from django.conf import settings

from apps.payments.integrations.nomba.client import NombaClient, credentials_for_environment

from .base import ChargeResult


class NombaPaymentAdapter:
    name = "nomba"

    def __init__(self, *, environment=None) -> None:
        self.environment = environment

    def charge(
        self,
        *,
        amount_minor: int,
        currency: str,
        token: str,
        idempotency_key: str,
        metadata: dict[str, Any] | None = None,
    ) -> ChargeResult:
        invoice = (metadata or {}).get("_invoice")
        payment_method = (metadata or {}).get("_payment_method")
        if invoice is None or payment_method is None:
            return ChargeResult(
                success=False,
                failure_code="processor_error",
                failure_message="Nomba charge requires invoice and payment method context.",
            )
        try:
            client = NombaClient(
                environment=invoice.environment,
                credentials=credentials_for_environment(invoice.environment),
            )
            order_reference = idempotency_key.replace(":", "-")
            response = client.charge_tokenized_card(
                {
                    "tokenKey": payment_method.token,
                    "order": {
                        "orderReference": order_reference,
                        "customerId": str(invoice.customer_id),
                        "callbackUrl": getattr(settings, "NOMBA_CHECKOUT_CALLBACK_URL", ""),
                        "customerEmail": invoice.customer.email,
                        "amount": f"{Decimal(invoice.amount_due_minor) / Decimal(100):.2f}",
                        "currency": invoice.currency,
                        "accountId": client.routing_account_id(),
                        "orderMetaData": {
                            "invoice_id": str(invoice.id),
                            "customer_id": str(invoice.customer_id),
                            "subscription_id": str(invoice.subscription_id) if invoice.subscription_id else "",
                            "subpilot_idempotency_key": idempotency_key,
                        },
                    },
                }
            )
        except Exception as exc:
            return ChargeResult(
                success=False,
                failure_code="processor_error",
                failure_message=str(exc),
                raw={"exception": exc.__class__.__name__},
            )
        data = response.get("data") if isinstance(response.get("data"), dict) else {}
        ok = response.get("code") in {"00", "200"} or data.get("status") is True
        if ok:
            reference = (
                data.get("transactionId")
                or data.get("id")
                or data.get("orderReference")
                or idempotency_key.replace(":", "-")
            )
            return ChargeResult(success=True, processor_reference=str(reference), raw=response)
        return ChargeResult(
            success=False,
            failure_code=str(response.get("code") or data.get("code") or "processor_error"),
            failure_message=str(response.get("description") or data.get("message") or "Nomba charge failed."),
            raw=response,
        )

    def verify_webhook(
        self, *, payload: bytes, signature: str, secret: str, timestamp: str = ""
    ) -> bool:
        if not signature or not secret:
            return False
        try:
            body = json.loads(payload.decode("utf-8")) if payload else {}
        except (UnicodeDecodeError, json.JSONDecodeError):
            return False
        signed_payload = self._webhook_signature_payload(body, timestamp)
        expected = base64.b64encode(
            hmac.new(secret.encode("utf-8"), signed_payload.encode("utf-8"), hashlib.sha256).digest()
        ).decode("utf-8")
        return hmac.compare_digest(expected, signature)

    def parse_webhook(self, *, payload: dict[str, Any]) -> dict[str, Any]:
        raw_type = str(payload.get("event_type") or payload.get("event") or payload.get("type") or "unknown")
        data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
        transaction = data.get("transaction") if isinstance(data.get("transaction"), dict) else {}
        tokenized_card = (
            data.get("tokenizedCardData")
            if isinstance(data.get("tokenizedCardData"), dict)
            else data.get("tokenized_card_data")
            if isinstance(data.get("tokenized_card_data"), dict)
            else {}
        )
        provider_event_id = str(
            payload.get("requestId")
            or payload.get("request_id")
            or payload.get("hookRequestId")
            or payload.get("hooksRequestId")
            or payload.get("eventId")
            or data.get("requestId")
            or data.get("request_id")
            or data.get("hookRequestId")
            or data.get("hooksRequestId")
            or data.get("eventId")
            or ""
        )
        processor_reference = str(transaction.get("transactionId") or data.get("reference") or data.get("id") or "")
        order_reference = str(
            data.get("orderReference")
            or data.get("order_reference")
            or transaction.get("orderReference")
            or transaction.get("order_reference")
            or ""
        )
        amount = transaction.get("transactionAmount") or data.get("amount") or data.get("amount_minor")
        event_type = {
            "payment_success": "payment.succeeded",
            "payment_failed": "payment.failed",
            "payment_reversal": "charge.refunded",
            "wallet_topup": "payment.succeeded",
            "payout_success": "payout.succeeded",
            "payout_failed": "payout.failed",
            "payout_refund": "payout.refunded",
        }.get(raw_type, raw_type)
        return {
            "provider": "nomba",
            "provider_event_id": provider_event_id,
            "event_type": event_type,
            "processor_reference": processor_reference,
            "order_reference": order_reference,
            "amount_minor": int(float(amount) * 100) if amount not in {None, ""} else None,
            "currency": data.get("currency", ""),
            "failure_code": str(data.get("failure_code") or transaction.get("responseCode") or ""),
            "failure_message": str(data.get("message") or transaction.get("responseMessage") or ""),
            "token_key": str(tokenized_card.get("tokenKey") or ""),
            "card_type": str(tokenized_card.get("cardType") or ""),
            "card_pan": str(tokenized_card.get("cardPan") or ""),
            "token_expiration_date": str(tokenized_card.get("tokenExpirationDate") or ""),
            "raw": payload,
        }

    @staticmethod
    def _webhook_signature_payload(payload: dict[str, Any], timestamp: str) -> str:
        data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
        merchant = data.get("merchant") if isinstance(data.get("merchant"), dict) else {}
        transaction = data.get("transaction") if isinstance(data.get("transaction"), dict) else {}
        response_code = transaction.get("responseCode", "")
        if response_code in {None, "null"}:
            response_code = ""
        return ":".join(
            [
                str(payload.get("event_type") or ""),
                str(payload.get("requestId") or payload.get("request_id") or ""),
                str(merchant.get("userId") or ""),
                str(merchant.get("walletId") or ""),
                str(transaction.get("transactionId") or ""),
                str(transaction.get("type") or ""),
                str(transaction.get("time") or ""),
                str(response_code),
                str(timestamp or ""),
            ]
        )


__all__ = ["NombaPaymentAdapter"]
