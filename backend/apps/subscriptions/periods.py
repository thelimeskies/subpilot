"""Period / billing-anchor helpers for the subscriptions domain."""
from __future__ import annotations

from datetime import datetime, timedelta

from apps.catalog.models import PriceVersion


def add_interval(start: datetime, *, unit: str, count: int = 1) -> datetime:
    """Add ``count * unit`` to ``start`` and return the new datetime.

    Months and years use simple month-anchor arithmetic that clamps to the
    last day of the target month to avoid 31 -> Feb weirdness.
    """
    if unit == PriceVersion.IntervalUnit.DAY:
        return start + timedelta(days=count)
    if unit == PriceVersion.IntervalUnit.WEEK:
        return start + timedelta(weeks=count)
    if unit == PriceVersion.IntervalUnit.MONTH:
        return _add_months(start, count)
    if unit == PriceVersion.IntervalUnit.YEAR:
        return _add_months(start, 12 * count)
    raise ValueError(f"Unknown interval unit: {unit!r}")


def _add_months(start: datetime, months: int) -> datetime:
    year = start.year + (start.month - 1 + months) // 12
    month = (start.month - 1 + months) % 12 + 1
    # Day clamp.
    day = min(start.day, _last_day_of_month(year, month))
    return start.replace(year=year, month=month, day=day)


def _last_day_of_month(year: int, month: int) -> int:
    if month == 12:
        next_month = datetime(year + 1, 1, 1)
    else:
        next_month = datetime(year, month + 1, 1)
    last = next_month - timedelta(days=1)
    return last.day


def compute_period_end(
    start: datetime, price_version: PriceVersion
) -> datetime:
    return add_interval(
        start,
        unit=price_version.interval_unit,
        count=price_version.interval_count,
    )
