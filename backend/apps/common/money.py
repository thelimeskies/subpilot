"""Money helpers.

SubPilot stores all monetary amounts as integer minor units (kobo for NGN, cents
for USD, etc.) per docs/technical/architecture.md. This module guards against
the most common mistakes: float math, currency mismatches, and rendering
amounts in their major-unit form for the UI.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

# Currencies whose minor unit factor is not 100. Extend as needed.
_NON_CENTESIMAL = {
    "JPY": 1,
    "KRW": 1,
    "VND": 1,
    "BHD": 1000,
    "JOD": 1000,
    "KWD": 1000,
    "OMR": 1000,
    "TND": 1000,
}


def minor_unit_factor(currency: str) -> int:
    """Return how many minor units make up one major unit for ``currency``."""
    return _NON_CENTESIMAL.get(currency.upper(), 100)


def to_minor_units(amount: Decimal | str | int | float, currency: str) -> int:
    """Convert a major-unit amount (e.g. 12.50 NGN) to minor units (1250)."""
    factor = minor_unit_factor(currency)
    decimal_amount = Decimal(str(amount))
    minor = int((decimal_amount * factor).quantize(Decimal("1")))
    if minor < 0:
        raise ValueError("Money amounts cannot be negative")
    return minor


def to_major_units(amount_minor: int, currency: str) -> Decimal:
    """Convert minor units back to a major-unit Decimal."""
    factor = minor_unit_factor(currency)
    return (Decimal(amount_minor) / Decimal(factor)).quantize(Decimal("0.01"))


def format_money(amount_minor: int, currency: str) -> str:
    """Render `amount_minor` as e.g. ``"NGN 12,500.00"`` for emails / logs."""
    major = to_major_units(amount_minor, currency)
    return f"{currency.upper()} {major:,.2f}"


@dataclass(frozen=True)
class Money:
    """Immutable amount + currency pair. Use sparingly; DB stores ints."""

    amount_minor: int
    currency: str

    def __post_init__(self) -> None:
        if self.amount_minor < 0:
            raise ValueError("Money amounts cannot be negative")
        if not self.currency or len(self.currency) != 3:
            raise ValueError("Currency must be a 3-letter ISO code")

    @classmethod
    def from_major(cls, amount: Decimal | str | int | float, currency: str) -> Money:
        return cls(to_minor_units(amount, currency), currency.upper())

    def to_major(self) -> Decimal:
        return to_major_units(self.amount_minor, self.currency)

    def format(self) -> str:
        return format_money(self.amount_minor, self.currency)

    def __add__(self, other: Money) -> Money:
        if self.currency != other.currency:
            raise ValueError(f"Currency mismatch: {self.currency} vs {other.currency}")
        return Money(self.amount_minor + other.amount_minor, self.currency)

    def __sub__(self, other: Money) -> Money:
        if self.currency != other.currency:
            raise ValueError(f"Currency mismatch: {self.currency} vs {other.currency}")
        return Money(self.amount_minor - other.amount_minor, self.currency)
