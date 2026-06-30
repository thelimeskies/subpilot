"""Pytest fixtures available to the entire backend test suite.

Provides:
 * DB access by default (no need for ``@pytest.mark.django_db`` everywhere).
 * Platform-admin role fixtures: ``platform_admin_owner``,
   ``platform_admin_operator``, ``platform_admin_support``,
   ``platform_admin_readonly``, ``platform_admin_suspended``.
 * Merchant-tenant fixture: ``merchant_user`` (Acme owner, demo password).
 * Client helpers: ``signed_in_admin_client``, ``signed_in_merchant_client``.

Tests inside ``apps/platform_admin/tests/`` extend these via the app-level
``conftest.py`` (cache reset autouse).
"""
from __future__ import annotations

from typing import Callable

import pytest
from rest_framework.test import APIClient

DEMO_PASSWORD = "Subpilot1!"

# ---------------------------------------------------------------------------
# DB access default
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _enable_db_access_for_all_tests(db):
    """All tests get DB access by default; opt out with @pytest.mark.no_db if needed."""
    return db


# ---------------------------------------------------------------------------
# Platform admin role fixtures
# ---------------------------------------------------------------------------


def _create_admin(email: str, role: str, name: str):
    from apps.platform_admin.models import PlatformAdmin, PlatformAdminStatus

    admin = PlatformAdmin.objects.create(
        email=email,
        display_name=name,
        role=role,
        status=PlatformAdminStatus.ACTIVE,
    )
    admin.set_password(DEMO_PASSWORD)
    admin.save()
    return admin


@pytest.fixture
def platform_admin_owner():
    from apps.platform_admin.models import PlatformAdminRole

    return _create_admin("owner@subpilot.dev", PlatformAdminRole.OWNER, "Ada Okafor")


@pytest.fixture
def platform_admin_operator():
    from apps.platform_admin.models import PlatformAdminRole

    return _create_admin("ops@subpilot.dev", PlatformAdminRole.OPERATOR, "Tunde Martins")


@pytest.fixture
def platform_admin_support():
    from apps.platform_admin.models import PlatformAdminRole

    return _create_admin("support@subpilot.dev", PlatformAdminRole.SUPPORT, "Zainab Musa")


@pytest.fixture
def platform_admin_readonly():
    from apps.platform_admin.models import PlatformAdminRole

    return _create_admin(
        "finance@subpilot.dev", PlatformAdminRole.READ_ONLY, "Chinedu Bello"
    )


@pytest.fixture
def platform_admin_suspended():
    from apps.platform_admin.models import PlatformAdminRole, PlatformAdminStatus

    admin = _create_admin("suspended@subpilot.dev", PlatformAdminRole.OPERATOR, "Suspended Op")
    admin.status = PlatformAdminStatus.SUSPENDED
    admin.save()
    return admin


# ---------------------------------------------------------------------------
# Merchant tenant fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def merchant_user():
    """A merchant-tenant Owner user belonging to a fresh Acme merchant."""
    from apps.accounts.models import Merchant, Role, TeamMember, User

    merchant = Merchant.objects.create(
        name="Acme RBAC", slug="acme-rbac", default_currency="NGN"
    )
    user = User.objects.create(email="owner@acme-rbac.test", is_active=True)
    user.set_password(DEMO_PASSWORD)
    user.save()
    TeamMember.objects.create(merchant=merchant, user=user, role=Role.OWNER)
    return user


# ---------------------------------------------------------------------------
# Authenticated client factories
# ---------------------------------------------------------------------------


@pytest.fixture
def signed_in_admin_client() -> Callable:
    """Return a factory that signs an admin into a fresh APIClient.

    Usage:
        client = signed_in_admin_client(platform_admin_owner)
    """

    def _factory(admin) -> APIClient:
        client = APIClient()
        resp = client.post(
            "/api/v1/platform/auth/sign-in",
            data={"email": admin.email, "password": DEMO_PASSWORD},
            format="json",
        )
        assert resp.status_code == 200, resp.content
        return client

    return _factory


@pytest.fixture
def signed_in_merchant_client() -> Callable:
    """Return a factory that signs a merchant user into a fresh APIClient."""

    def _factory(user) -> APIClient:
        client = APIClient()
        resp = client.post(
            "/api/v1/auth/sign-in",
            data={"email": user.email, "password": DEMO_PASSWORD},
            format="json",
        )
        assert resp.status_code == 200, resp.content
        return client

    return _factory
"""Pytest fixtures available to the entire backend test suite."""
import pytest


@pytest.fixture(autouse=True)
def _enable_db_access_for_all_tests(db):
    """All tests get DB access by default; opt out with @pytest.mark.no_db if needed."""
    return db
