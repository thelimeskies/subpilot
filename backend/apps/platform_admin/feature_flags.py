"""Canonical feature-flag catalog (S13).

A flag is the unit of capability that an admin can toggle for a single
merchant. Defaults live here, overrides live in
[MerchantConfig.feature_flags](file:///Users/mac/Desktop/Projects/HackathonxNomba/backend/apps/platform_admin/models.py).

The merchant API enforces flags via :func:`get_flag` (see e.g. refund
endpoints under apps/payments). The admin API exposes the catalog so the
FE can render labels + descriptions without duplicating strings.

Adding a flag is a single-file change: append it below, ship a migration
data-fix if you want a non-default boot value, then add the enforcement
point. Removing a flag is also single-file; stale rows in
``MerchantConfig.feature_flags`` are ignored by :func:`resolved_flags`.
"""
from __future__ import annotations

from typing import TypedDict


class FlagSpec(TypedDict):
    label: str
    description: str
    default: bool


FEATURE_FLAGS: dict[str, FlagSpec] = {
    "tokenized_cards": {
        "label": "Tokenized cards",
        "description": "Allow this merchant to save card tokens for re-use.",
        "default": True,
    },
    "manual_refunds": {
        "label": "Manual refunds",
        "description": "Allow merchant operators to refund payments from the dashboard.",
        "default": True,
    },
    "promo_codes": {
        "label": "Promo codes",
        "description": "Expose the promo-code endpoints to this merchant.",
        "default": False,
    },
    "smart_routing": {
        "label": "Smart adapter routing",
        "description": "Tag PaymentAttempts with a routing-policy hint for adapter selection.",
        "default": False,
    },
}


def catalog() -> list[dict[str, str | bool]]:
    """FE-shape catalog list. Stable ordering by declaration."""
    return [
        {
            "key": key,
            "label": spec["label"],
            "description": spec["description"],
            "default": spec["default"],
        }
        for key, spec in FEATURE_FLAGS.items()
    ]


def get_flag(merchant, key: str) -> bool:
    """Return the resolved boolean value for ``key`` on ``merchant``.

    Falls back to the catalog default when:
      - the merchant has no ``MerchantConfig`` row, or
      - the row's ``feature_flags`` map does not include the key.

    Unknown ``key`` raises :class:`KeyError` (callers are typed against
    the catalog).
    """
    spec = FEATURE_FLAGS.get(key)
    if spec is None:
        raise KeyError(f"Unknown feature flag: {key!r}")
    config = getattr(merchant, "config", None)
    if config is None:
        return spec["default"]
    override = (config.feature_flags or {}).get(key)
    if override is None:
        return spec["default"]
    return bool(override)


def resolved_flags(merchant) -> dict[str, bool]:
    """Return ``{flag_key: bool}`` for every catalog entry."""
    config = getattr(merchant, "config", None)
    override_map = (config.feature_flags or {}) if config is not None else {}
    return {
        key: bool(override_map.get(key, spec["default"]))
        for key, spec in FEATURE_FLAGS.items()
    }


def is_known_flag(key: str) -> bool:
    return key in FEATURE_FLAGS
