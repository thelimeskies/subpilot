"""Tests for apps.common.money."""
from decimal import Decimal

import pytest

from apps.common.money import Money, format_money, to_major_units, to_minor_units


def test_to_minor_units_default_centesimal():
    assert to_minor_units(Decimal("12.50"), "NGN") == 1250
    assert to_minor_units("9.99", "USD") == 999
    assert to_minor_units(0, "USD") == 0


def test_to_minor_units_jpy_no_minor_units():
    assert to_minor_units(1500, "JPY") == 1500


def test_to_major_units_round_trip():
    assert to_major_units(1250, "NGN") == Decimal("12.50")
    assert to_major_units(1500, "JPY") == Decimal("1500.00")


def test_format_money_with_thousands():
    assert format_money(1_234_500, "NGN") == "NGN 12,345.00"


def test_money_addition_same_currency():
    a = Money.from_major("10.00", "NGN")
    b = Money.from_major("5.50", "NGN")
    assert (a + b).amount_minor == 1550


def test_money_currency_mismatch_raises():
    a = Money.from_major("10.00", "NGN")
    b = Money.from_major("5.50", "USD")
    with pytest.raises(ValueError):
        _ = a + b


def test_money_negative_rejected():
    with pytest.raises(ValueError):
        Money(-1, "NGN")
