"""Pytest fixtures for the platform admin app.

Admin role fixtures (``platform_admin_owner``, ``platform_admin_operator``,
``platform_admin_support``, ``platform_admin_readonly``,
``platform_admin_suspended``) and the ``merchant_user`` /
``signed_in_admin_client`` / ``signed_in_merchant_client`` helpers are defined
at the project root (``backend/conftest.py``) — see that module.
"""
from __future__ import annotations

import pytest
from django.core.cache import cache


@pytest.fixture(autouse=True)
def _clear_cache_between_tests():
    """DRF AnonRateThrottle uses the default cache and the locmem backend
    persists across tests in a single pytest run. Clear before each test so
    sign-ins inside helpers don't accumulate against the 60/min anon ceiling.
    """
    cache.clear()
    yield
    cache.clear()
