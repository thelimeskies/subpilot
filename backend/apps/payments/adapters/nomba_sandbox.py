"""Nomba sandbox payment adapter.

Implements the :class:`PaymentAdapter` Protocol against Nomba's sandbox HTTP
API. Live credentials are read from the merchant ``Environment`` (Nomba
client_id / client_secret are encrypted at rest); the base URL and webhook
secret come from settings. This adapter is intentionally conservative: it
defers everything but the bare minimum to other layers and converts every
non-2xx response into a normalized :class:`ChargeResult` failure.

Reference: docs/technical/api-and-webhooks.md and Nomba sandbox docs.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
from typing import Any

from django.conf import settings

from .base import ChargeResult
from .nomba import NombaPaymentAdapter

logger = logging.getLogger(__name__)


class NombaSandboxAdapter:
    """Minimal Nomba sandbox client.

    The real HTTP plumbing is intentionally lazy-imported so the rest of the
    project (and the Django check command) does not require ``requests``
    unless a Nomba charge is actually attempted.
    """

    name = "nomba_sandbox"

    def __init__(
        self,
        *,
        base_url: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
        timeout_seconds: float = 15.0,
    ) -> None:
        self.base_url = (
            base_url
            or getattr(settings, "NOMBA_SANDBOX_BASE_URL", "https://sandbox.nomba.com")
        ).rstrip("/")
        self.client_id = client_id or getattr(settings, "NOMBA_SANDBOX_CLIENT_ID", "")
        self.client_secret = client_secret or getattr(
            settings, "NOMBA_SANDBOX_CLIENT_SECRET", ""
        )
        self.timeout_seconds = timeout_seconds

    # ------------------------------------------------------------------ charge
    def charge(
        self,
        *,
        amount_minor: int,
        currency: str,
        token: str,
        idempotency_key: str,
        metadata: dict[str, Any] | None = None,
    ) -> ChargeResult:
        try:
            import requests  # noqa: PLC0415 — lazy import for optional dep
        except ImportError:  # pragma: no cover
            return ChargeResult(
                success=False,
                failure_code="processor_error",
                failure_message="`requests` not installed; cannot reach Nomba sandbox.",
                raw={"reason": "missing_dependency"},
            )

        url = f"{self.base_url}/v1/charges"
        body = {
            "amount": amount_minor,
            "currency": currency,
            "source": token,
            "metadata": metadata or {},
        }
        headers = {
            "Authorization": f"Bearer {self.client_secret}",
            "X-Client-Id": self.client_id,
            "Idempotency-Key": idempotency_key,
            "Content-Type": "application/json",
        }
        try:
            response = requests.post(
                url, json=body, headers=headers, timeout=self.timeout_seconds
            )
        except Exception as exc:  # network failure, dns, ssl, etc.
            logger.warning("nomba_sandbox.network_error", extra={"err": str(exc)})
            return ChargeResult(
                success=False,
                failure_code="network_timeout",
                failure_message=str(exc),
                raw={"exception": exc.__class__.__name__},
            )

        try:
            data: dict[str, Any] = response.json()
        except ValueError:
            data = {"raw_text": response.text}

        if 200 <= response.status_code < 300 and data.get("status") == "success":
            return ChargeResult(
                success=True,
                processor_reference=str(data.get("reference") or data.get("id") or ""),
                raw=data,
            )
        return ChargeResult(
            success=False,
            failure_code=str(data.get("failure_code") or data.get("code") or "processor_error"),
            failure_message=str(data.get("message") or data.get("error") or "Charge failed."),
            raw=data,
        )

    # ----------------------------------------------------------------- webhook
    def verify_webhook(
        self, *, payload: bytes, signature: str, secret: str, timestamp: str = ""
    ) -> bool:
        """Verify Nomba's documented Base64 HMAC-SHA256 webhook signature.

        Nomba signs this colon-joined string:
        event_type:requestId:merchant.userId:merchant.walletId:
        transaction.transactionId:transaction.type:transaction.time:
        transaction.responseCode:nomba-timestamp
        """
        if not signature or not secret:
            return False
        try:
            body = json.loads(payload.decode("utf-8")) if payload else {}
        except (UnicodeDecodeError, json.JSONDecodeError):
            return False
        signed_payload = self._webhook_signature_payload(body, timestamp)
        expected = base64.b64encode(
            hmac.new(
                secret.encode("utf-8"),
                signed_payload.encode("utf-8"),
                hashlib.sha256,
            ).digest()
        ).decode("utf-8")
        return hmac.compare_digest(expected, signature)

    def parse_webhook(self, *, payload: dict[str, Any]) -> dict[str, Any]:
        """Normalize a Nomba sandbox webhook payload to canonical shape."""
        raw_type = str(
            payload.get("event_type")
            or payload.get("event")
            or payload.get("type")
            or "unknown"
        )
        data = payload.get("data") or {}
        transaction = data.get("transaction") if isinstance(data, dict) else {}
        transaction = transaction if isinstance(transaction, dict) else {}
        tokenized_card = (
            data.get("tokenizedCardData")
            if isinstance(data, dict) and isinstance(data.get("tokenizedCardData"), dict)
            else data.get("tokenized_card_data")
            if isinstance(data, dict) and isinstance(data.get("tokenized_card_data"), dict)
            else {}
        )
        provider_event_id = str(payload.get("requestId") or payload.get("request_id") or "")
        processor_reference = str(
            transaction.get("transactionId")
            or data.get("reference")
            or data.get("id")
            or ""
        )
        amount = (
            transaction.get("transactionAmount")
            or data.get("amount")
            or data.get("amount_minor")
        )
        event_type = {
            "payment_success": "payment.succeeded",
            "payment_failed": "payment.failed",
            "payment_reversal": "charge.refunded",
            "payout_success": "payout.succeeded",
            "payout_failed": "payout.failed",
            "payout_refund": "payout.refunded",
        }.get(raw_type, raw_type)
        return {
            "provider": "nomba",
            "provider_event_id": provider_event_id,
            "event_type": event_type,
            "processor_reference": processor_reference,
            "amount_minor": int(float(amount) * 100) if amount not in {None, ""} else None,
            "currency": data.get("currency", ""),
            "failure_code": str(data.get("failure_code") or ""),
            "failure_message": str(data.get("message") or ""),
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


__all__ = ["NombaPaymentAdapter", "NombaSandboxAdapter"]
