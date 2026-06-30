"""Payment processor adapter interface.

Adapters translate SubPilot's domain calls (charge invoice, register payment
method, ingest processor webhook) to a specific gateway. The base class
defines the shape; concrete adapters implement it.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


class FailureCategory:
    """Standardized payment-failure categories used by the dunning engine.

    See docs/technical/api-and-webhooks.md and
    docs/technical/celery-job-contracts.md for the full taxonomy.
    """

    INSUFFICIENT_FUNDS = "insufficient_funds"
    EXPIRED_CARD = "expired_card"
    DECLINED = "declined"
    FRAUD = "fraud"
    PROCESSOR_ERROR = "processor_error"
    AUTHENTICATION_REQUIRED = "authentication_required"
    NETWORK_TIMEOUT = "network_timeout"
    UNKNOWN = "unknown"


# Soft (retryable) vs hard (stop-until-pm-replaced) failure groups.
SOFT_FAILURES = {
    FailureCategory.INSUFFICIENT_FUNDS,
    FailureCategory.PROCESSOR_ERROR,
    FailureCategory.NETWORK_TIMEOUT,
}
HARD_FAILURES = {
    FailureCategory.EXPIRED_CARD,
    FailureCategory.DECLINED,
    FailureCategory.FRAUD,
    FailureCategory.AUTHENTICATION_REQUIRED,
}


@dataclass
class ChargeResult:
    """Outcome of a single charge attempt."""

    success: bool
    processor_reference: str = ""
    failure_code: str = ""
    failure_message: str = ""
    raw: dict[str, Any] | None = None

    @property
    def failure_category(self) -> str:
        if self.success or not self.failure_code:
            return ""
        return classify_failure(self.failure_code)


def classify_failure(code: str) -> str:
    """Map raw provider failure codes into our normalized categories."""
    code_lc = (code or "").lower()
    if "insufficient" in code_lc or code_lc in {"51", "ndf"}:
        return FailureCategory.INSUFFICIENT_FUNDS
    if "expired" in code_lc or code_lc in {"54"}:
        return FailureCategory.EXPIRED_CARD
    if "fraud" in code_lc or code_lc in {"43", "59"}:
        return FailureCategory.FRAUD
    if "auth" in code_lc or code_lc in {"3ds", "3d_secure"}:
        return FailureCategory.AUTHENTICATION_REQUIRED
    if "decline" in code_lc or code_lc in {"05", "57", "61", "62", "65"}:
        return FailureCategory.DECLINED
    if "timeout" in code_lc or "network" in code_lc:
        return FailureCategory.NETWORK_TIMEOUT
    if "processor" in code_lc or "internal" in code_lc:
        return FailureCategory.PROCESSOR_ERROR
    return FailureCategory.UNKNOWN


class PaymentAdapter(Protocol):
    """Protocol every concrete adapter implements."""

    name: str

    def charge(
        self,
        *,
        amount_minor: int,
        currency: str,
        token: str,
        idempotency_key: str,
        metadata: dict[str, Any] | None = None,
    ) -> ChargeResult: ...

    def verify_webhook(
        self, *, payload: bytes, signature: str, secret: str, timestamp: str = ""
    ) -> bool: ...

    def parse_webhook(self, *, payload: dict[str, Any]) -> dict[str, Any]: ...
