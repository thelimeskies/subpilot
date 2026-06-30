"""FE-shape formatting helpers for the platform admin overview.

The frontend expects compact human-readable strings such as ``"NGN 42.8m"``
rather than precise figures. These helpers do the conversion in one place so
the selector / service layer keeps numbers in **minor units** (the rest of
the codebase's invariant).
"""
from __future__ import annotations

from decimal import Decimal

from apps.common.money import to_major_units


def format_compact_money(amount_minor: int, currency: str) -> str:
    """Render ``amount_minor`` as a compact, human-readable money string.

    Examples:
        12_345 -> "NGN 12.3k"     (Decimal kobo)
        42_800_000_00 -> "NGN 42.8m"
        0 -> "NGN 0"
    """
    if amount_minor <= 0:
        return f"{currency.upper()} 0"
    major = to_major_units(amount_minor, currency)  # Decimal
    return f"{currency.upper()} {_compact_decimal(major)}"


def format_compact_int(value: int) -> str:
    """Render an integer compactly. Useful for "+14 this month" deltas."""
    if value < 1_000:
        return str(value)
    if value < 1_000_000:
        return _compact_decimal(Decimal(value) / Decimal(1_000)) + "k"
    if value < 1_000_000_000:
        return _compact_decimal(Decimal(value) / Decimal(1_000_000)) + "m"
    return _compact_decimal(Decimal(value) / Decimal(1_000_000_000)) + "b"


def format_pct(pct: float, *, signed: bool = False) -> str:
    if pct == 0:
        return "0%"
    sign = ""
    if signed and pct > 0:
        sign = "+"
    return f"{sign}{pct:.1f}%"


def _compact_decimal(major: Decimal) -> str:
    """Render a Decimal as compact (k/m/b) without losing one decimal of detail."""
    if major < 1_000:
        # No suffix needed; trim trailing zeros / .00 for a tighter look.
        if major == major.to_integral_value():
            return f"{int(major)}"
        return f"{major:.2f}"
    if major < 1_000_000:
        return f"{(major / Decimal(1_000)):.1f}k"
    if major < 1_000_000_000:
        return f"{(major / Decimal(1_000_000)):.1f}m"
    return f"{(major / Decimal(1_000_000_000)):.2f}b"
