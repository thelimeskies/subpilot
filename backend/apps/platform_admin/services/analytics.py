"""Cache + audit wrapper for the cross-tenant analytics snapshot (S11).

Mirrors :mod:`apps.platform_admin.services.overview` but stores one cached
payload per time-range key. Cache key format: ``platform:analytics:<range>``.
"""
from __future__ import annotations

from django.core.cache import cache

from apps.audit.services.log_event import log_event

from ..selectors.analytics import (
    DEFAULT_RANGE,
    RANGE_KEYS,
    build_analytics_snapshot,
    project_analytics,
)

_CACHE_TTL = 60 * 15  # 15 minutes
_CACHE_KEY_PREFIX = "platform:analytics"


def _cache_key(range_key: str) -> str:
    return f"{_CACHE_KEY_PREFIX}:{range_key}"


def refresh_platform_analytics(
    *,
    range_key: str = DEFAULT_RANGE,
    actor_label: str | None = None,
    request=None,
) -> dict:
    """Recompute, cache, and return the analytics snapshot."""
    if range_key not in RANGE_KEYS:
        range_key = DEFAULT_RANGE
    snapshot = build_analytics_snapshot(range_key=range_key)
    payload = project_analytics(snapshot)
    cache.set(_cache_key(range_key), payload, _CACHE_TTL)
    log_event(
        action="platform.analytics.refreshed",
        actor_user=None,
        actor_label=actor_label or "system",
        actor_role="platform_admin",
        merchant=None,
        environment=None,
        target_type="platform",
        target_id=f"analytics:{range_key}",
        metadata={
            "range": range_key,
            "revenue_points": len(snapshot.revenue_series),
            "top_merchants": len(snapshot.top_merchants),
        },
        request=request,
    )
    return payload


def get_cached_analytics(range_key: str = DEFAULT_RANGE) -> dict | None:
    if range_key not in RANGE_KEYS:
        range_key = DEFAULT_RANGE
    return cache.get(_cache_key(range_key))


def get_or_refresh_analytics(
    *,
    range_key: str = DEFAULT_RANGE,
    actor_label: str | None = None,
    request=None,
) -> dict:
    """Read cache; on miss compute synchronously and warm cache."""
    cached = get_cached_analytics(range_key)
    if cached is not None:
        return cached
    return refresh_platform_analytics(
        range_key=range_key, actor_label=actor_label, request=request
    )


__all__ = [
    "get_cached_analytics",
    "get_or_refresh_analytics",
    "refresh_platform_analytics",
]
