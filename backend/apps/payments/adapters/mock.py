"""Deterministic mock payment adapter.

Used for development, demos, and tests. The behavior of a charge is driven
either by ``metadata['mock_outcome']`` (explicit override for the demo seeder)
or by the trailing characters of the token (so a card token ending in
``_fail_insufficient`` always returns insufficient_funds).
"""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from typing import Any

from .base import ChargeResult, FailureCategory


# Map of "outcome" hint -> (failure_code, message). Empty key means success.
_OUTCOMES: dict[str, tuple[str, str]] = {
    "success": ("", ""),
    "insufficient": ("insufficient_funds", "Card has insufficient funds."),
    "expired": ("expired_card", "Card has expired."),
    "declined": ("declined", "Card declined by issuer."),
    "fraud": ("fraud", "Suspected fraud, blocked."),
    "auth": ("authentication_required", "3DS authentication required."),
    "timeout": ("network_timeout", "Processor network timeout."),
    "processor": ("processor_error", "Generic processor error."),
}


def _resolve_outcome(token: str, metadata: dict[str, Any] | None) -> str:
    if metadata and "mock_outcome" in metadata:
        return str(metadata["mock_outcome"]).lower()
    token_lc = (token or "").lower()
    for hint in _OUTCOMES:
        if hint != "success" and f"_fail_{hint}" in token_lc:
            return hint
    return "success"


class MockPaymentAdapter:
    """Concrete adapter conforming to :class:`PaymentAdapter` protocol."""

    name = "mock"

    def charge(
        self,
        *,
        amount_minor: int,
        currency: str,
        token: str,
        idempotency_key: str,
        metadata: dict[str, Any] | None = None,
    ) -> ChargeResult:
        outcome = _resolve_outcome(token, metadata)
        failure_code, failure_message = _OUTCOMES.get(outcome, _OUTCOMES["success"])
        if not failure_code:
            ref = f"mock_{secrets.token_hex(8)}"
            return ChargeResult(
                success=True,
                processor_reference=ref,
                raw={
                    "amount_minor": amount_minor,
                    "currency": currency,
                    "idempotency_key": idempotency_key,
                    "outcome": outcome,
                },
            )
        return ChargeResult(
            success=False,
            processor_reference="",
            failure_code=failure_code,
            failure_message=failure_message,
            raw={
                "amount_minor": amount_minor,
                "currency": currency,
                "idempotency_key": idempotency_key,
                "outcome": outcome,
            },
        )

    def verify_webhook(
        self, *, payload: bytes, signature: str, secret: str, timestamp: str = ""
    ) -> bool:
        # Mock signs the payload with HMAC-SHA256 of the secret, hex digest.
        if not signature or not secret:
            return False
        expected = hmac.new(
            secret.encode("utf-8"), payload, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature)

    def parse_webhook(self, *, payload: dict[str, Any]) -> dict[str, Any]:
        """Normalize a mock webhook payload to SubPilot's canonical shape."""
        event_type = str(payload.get("type") or payload.get("event") or "unknown")
        data = payload.get("data") or {}
        return {
            "provider": "mock",
            "provider_event_id": str(payload.get("id") or payload.get("event_id") or ""),
            "event_type": event_type,
            "processor_reference": str(data.get("reference") or ""),
            "amount_minor": data.get("amount_minor"),
            "currency": data.get("currency", ""),
            "failure_code": str(data.get("failure_code") or ""),
            "failure_message": str(data.get("failure_message") or ""),
            "raw": payload,
        }


# Re-export for ``classify_failure`` if callers want it locally.
__all__ = ["MockPaymentAdapter", "FailureCategory"]
