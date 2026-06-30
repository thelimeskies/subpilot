"""Payment adapter registry.

Resolve a :class:`PaymentAdapter` by name, given a merchant ``Environment``
(used to pull encrypted credentials when applicable). Adapter selection is
driven by the ``Environment.mode`` and the configured ``PAYMENTS_ADAPTER``
setting (``"mock"`` or ``"nomba_sandbox"``).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from django.conf import settings

from .base import (
    HARD_FAILURES,
    SOFT_FAILURES,
    ChargeResult,
    FailureCategory,
    PaymentAdapter,
    classify_failure,
)
from .mock import MockPaymentAdapter
from .nomba_sandbox import NombaSandboxAdapter

if TYPE_CHECKING:  # pragma: no cover
    from apps.accounts.models import Environment


def get_adapter(name: str | None = None, *, environment: Environment | None = None) -> PaymentAdapter:
    """Return the adapter for ``name`` (defaulting to settings.PAYMENTS_ADAPTER)."""
    resolved = (name or getattr(settings, "PAYMENTS_ADAPTER", "mock")).lower()
    if resolved in {"mock", "demo"}:
        return MockPaymentAdapter()
    if resolved in {"nomba", "nomba_sandbox"}:
        byok_mode = getattr(environment, "nomba_integration_mode", "") == "byok"
        if environment is not None and byok_mode:
            try:
                client_id = environment.nomba_client_id or ""
                client_secret = environment.nomba_client_secret or ""
                return NombaSandboxAdapter(client_id=client_id, client_secret=client_secret)
            except Exception:
                # Fall through to settings-based defaults
                pass
        return NombaSandboxAdapter()
    raise ValueError(f"Unknown payments adapter: {resolved!r}")


__all__ = [
    "ChargeResult",
    "FailureCategory",
    "HARD_FAILURES",
    "PaymentAdapter",
    "SOFT_FAILURES",
    "MockPaymentAdapter",
    "NombaSandboxAdapter",
    "classify_failure",
    "get_adapter",
]
