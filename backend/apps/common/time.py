"""Time helpers — always tz-aware UTC."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone


def utcnow() -> datetime:
    """Tz-aware UTC ``datetime.now()``. Use this everywhere instead of ``datetime.utcnow``."""
    return datetime.now(timezone.utc)


def in_minutes(minutes: int) -> datetime:
    return utcnow() + timedelta(minutes=minutes)


def in_hours(hours: int) -> datetime:
    return utcnow() + timedelta(hours=hours)


def in_days(days: int) -> datetime:
    return utcnow() + timedelta(days=days)


def is_expired(when: datetime | None) -> bool:
    if when is None:
        return False
    return when <= utcnow()
