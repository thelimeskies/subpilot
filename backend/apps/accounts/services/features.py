"""Merchant feature-flag helpers (S13).

Thin facade over :mod:`apps.platform_admin.feature_flags`. The catalog and
resolution logic are owned by ``platform_admin`` (single source of truth);
this module re-exports them under the ``accounts.services`` namespace so the
merchant-side API never needs to import from the admin app directly.

Two reusable helpers are exposed in addition to the re-exports:

* :func:`feature_payload` - returns the FE-friendly bundle for ``GET
  /api/v1/me/features`` (``{flags, catalog}``).
* :func:`disabled_response` - returns the canonical ``403`` envelope
  ``{ok: False, reason: "Feature '<label>' is disabled for this merchant."}``
  used by every enforcement point (refunds, tokenized cards, promo codes).
"""
from __future__ import annotations

from rest_framework import status
from rest_framework.response import Response

from apps.platform_admin.feature_flags import (
    FEATURE_FLAGS,
    catalog as _catalog,
    get_flag,
    is_known_flag,
    resolved_flags,
)


__all__ = [
    "FEATURE_FLAGS",
    "disabled_response",
    "feature_payload",
    "get_flag",
    "is_known_flag",
    "resolved_flags",
]


def feature_payload(merchant) -> dict:
    """Return ``{flags, catalog}`` for the current merchant session."""
    return {
        "flags": resolved_flags(merchant),
        "catalog": _catalog(),
    }


def disabled_response(key: str) -> Response:
    """Return the standard 403 envelope for a disabled feature flag."""
    spec = FEATURE_FLAGS.get(key)
    label = spec["label"] if spec else key
    return Response(
        {
            "ok": False,
            "reason": f"Feature '{label}' is disabled for this merchant.",
        },
        status=status.HTTP_403_FORBIDDEN,
    )
