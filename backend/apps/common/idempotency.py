"""Redis-backed idempotency utilities.

Two layers:
1. :class:`IdempotencyMiddleware` (HTTP) — replays cached responses for the
   same ``(merchant_id, Idempotency-Key)`` pair within the TTL.
2. :func:`idempotent_enqueue` (Celery) — guards task enqueue using a Redis
   ``SET NX`` lock per docs/technical/celery-job-contracts.md.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from django.core.cache import cache

DEFAULT_TTL_SECONDS = 60 * 60 * 24  # 24h


def _http_cache_key(merchant_id: str | None, idem_key: str, method: str, path: str) -> str:
    base = f"{merchant_id or 'anon'}:{method}:{path}:{idem_key}"
    digest = hashlib.sha256(base.encode("utf-8")).hexdigest()[:32]
    return f"idem:http:{digest}"


def http_get(merchant_id: str | None, idem_key: str, method: str, path: str) -> dict | None:
    """Look up a previously-cached response. Returns ``None`` if not found."""
    return cache.get(_http_cache_key(merchant_id, idem_key, method, path))


def http_store(
    merchant_id: str | None,
    idem_key: str,
    method: str,
    path: str,
    *,
    status_code: int,
    body: bytes,
    content_type: str,
    ttl: int = DEFAULT_TTL_SECONDS,
) -> None:
    """Store the response payload for replay."""
    payload = {
        "status_code": status_code,
        "body_b64": body.decode("utf-8", errors="replace"),
        "content_type": content_type,
    }
    cache.set(_http_cache_key(merchant_id, idem_key, method, path), payload, ttl)


def idempotent_enqueue(key: str, ttl: int = DEFAULT_TTL_SECONDS) -> bool:
    """Acquire an enqueue lock. Returns ``True`` if this caller is first.

    Used inside Celery beat-driven scanners so the same ``renewal:{sub}:{end}``
    is enqueued at most once per period (per celery-job-contracts.md).
    """
    cache_key = f"idem:job:{key}"
    return cache.add(cache_key, "1", ttl)  # add() == SET NX in django-redis


def fingerprint_body(body: bytes | str | dict[str, Any] | None) -> str:
    """Stable hash of a request body, useful for idempotency conflict detection."""
    if body is None:
        return ""
    if isinstance(body, dict):
        body = json.dumps(body, sort_keys=True, default=str).encode("utf-8")
    elif isinstance(body, str):
        body = body.encode("utf-8")
    return hashlib.sha256(body).hexdigest()
