"""Tests for apps.common.idempotency."""
import pytest
from django.core.cache import cache

from apps.common import idempotency


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


def test_http_store_and_replay():
    idempotency.http_store(
        "merchant_x",
        "key_1",
        "POST",
        "/api/v1/customers",
        status_code=201,
        body=b'{"id":"cus_abc"}',
        content_type="application/json",
    )
    cached = idempotency.http_get("merchant_x", "key_1", "POST", "/api/v1/customers")
    assert cached is not None
    assert cached["status_code"] == 201
    assert "cus_abc" in cached["body_b64"]


def test_http_get_miss_returns_none():
    assert idempotency.http_get("m", "k", "POST", "/x") is None


def test_idempotent_enqueue_first_caller_wins():
    assert idempotency.idempotent_enqueue("renewal:sub_1:2024-01-01") is True
    assert idempotency.idempotent_enqueue("renewal:sub_1:2024-01-01") is False
