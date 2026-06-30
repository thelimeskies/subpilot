"""Database helpers shared across services.

Currently exposes :func:`atomic_with_retry`, a drop-in replacement for
``@transaction.atomic`` that retries the wrapped callable on transient
``deadlock detected`` errors raised by PostgreSQL.

Why we need this
----------------
Several domain services emit a webhook event (which inserts ``WebhookEvent``
+ one ``WebhookDelivery`` per matching endpoint) inside the same
transaction as their primary mutation.  Because every child row touching a
tenant takes a ``FOR KEY SHARE`` lock on ``accounts_merchant`` for FK
validation, concurrent transactions across the web container and the
Celery worker can — under load — produce spurious PostgreSQL deadlocks
on multi-xact promotion.  PG resolves them by aborting one transaction
with ``OperationalError: deadlock detected``; retrying the entire
transaction lets the request succeed without exposing the conflict to
the caller.
"""
from __future__ import annotations

import logging
import random
import time
from functools import wraps
from typing import Any, Callable, TypeVar

from django.db import OperationalError, transaction

log = logging.getLogger("subpilot.db")

F = TypeVar("F", bound=Callable[..., Any])

_DEADLOCK_MARKERS = ("deadlock detected",)
_DEFAULT_MAX_RETRIES = 3
_DEFAULT_BASE_DELAY = 0.04  # 40 ms


def _is_deadlock(exc: BaseException) -> bool:
    msg = str(exc).lower()
    return any(marker in msg for marker in _DEADLOCK_MARKERS)


def atomic_with_retry(
    func: F | None = None,
    *,
    max_retries: int = _DEFAULT_MAX_RETRIES,
    base_delay: float = _DEFAULT_BASE_DELAY,
    using: str | None = None,
) -> F:
    """Run the decorated callable inside ``transaction.atomic``, retry on deadlock.

    Usage::

        @atomic_with_retry
        def attach_payment_method(...):
            ...

    The decorator can also be parameterised::

        @atomic_with_retry(max_retries=5)
        def heavy_service(...):
            ...
    """

    def _decorate(fn: F) -> F:
        @wraps(fn)
        def _wrapped(*args: Any, **kwargs: Any) -> Any:
            attempt = 0
            while True:
                try:
                    with transaction.atomic(using=using):
                        return fn(*args, **kwargs)
                except OperationalError as exc:
                    if not _is_deadlock(exc) or attempt >= max_retries:
                        raise
                    delay = base_delay * (2 ** attempt) + random.uniform(0, base_delay)
                    log.warning(
                        "atomic_with_retry: deadlock on %s attempt=%s sleeping=%.3fs",
                        fn.__qualname__, attempt + 1, delay,
                    )
                    time.sleep(delay)
                    attempt += 1

        return _wrapped  # type: ignore[return-value]

    if func is None:
        return _decorate  # type: ignore[return-value]
    return _decorate(func)
