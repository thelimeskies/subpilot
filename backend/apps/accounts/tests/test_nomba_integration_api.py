from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Environment, Merchant, Role, TeamMember, User

pytestmark = pytest.mark.django_db

PASSWORD = "Subpilot1!"


def _owner(slug="nomba-api-co"):
    merchant = Merchant.objects.create(name="Nomba API Co", slug=slug, default_currency="NGN")
    Environment.objects.create(merchant=merchant, mode=Environment.Mode.TEST)
    user = User.objects.create_user(
        email=f"owner@{slug}.test",
        password=PASSWORD,
        display_name="Nomba Owner",
        email_verified=True,
        onboarding_complete=True,
    )
    TeamMember.objects.create(merchant=merchant, user=user, role=Role.OWNER)
    client = APIClient()
    response = client.post(
        "/api/v1/auth/sign-in",
        data={"email": user.email, "password": PASSWORD},
        format="json",
    )
    assert response.status_code == 200, response.content
    assert response.json()["ok"] is True
    return client, merchant


def test_nomba_credentials_endpoint_stores_masked_configuration():
    client, merchant = _owner()

    response = client.post(
        "/api/v1/nomba/",
        {
            "integration_mode": "byok",
            "account_id": "acct_123",
            "client_id": "client_123",
            "client_secret": "secret_123",
            "webhook_secret": "webhook_123",
            "sub_account_id": "sub_123",
        },
        format="json",
    )

    assert response.status_code == 200
    body = response.json()
    assert body["integrationMode"] == "byok"
    assert body["accountId"] == "acct_123"
    assert body["hasClientSecret"] is True
    assert "secret_123" not in str(body)

    env = Environment.objects.get(merchant=merchant, mode=Environment.Mode.TEST)
    assert env.nomba_client_secret == "secret_123"
    assert env.webhook_secret == "webhook_123"
    assert env.nomba_sub_account_id == "sub_123"


def test_nomba_sub_account_mapping_endpoint_updates_environment():
    client, merchant = _owner("nomba-map-co")

    response = client.post("/api/v1/nomba/sub-account/", {"sub_account_id": "sub_456"}, format="json")

    assert response.status_code == 200
    assert response.json()["sub_account_id"] == "sub_456"
    env = Environment.objects.get(merchant=merchant, mode=Environment.Mode.TEST)
    assert env.nomba_sub_account_id == "sub_456"


def test_nomba_bank_account_lookup_endpoint_uses_environment(monkeypatch):
    client, merchant = _owner("nomba-lookup-co")
    seen = {}

    def fake_lookup(environment, *, bank, account_number, actor_user=None, request=None):
        seen["environment_id"] = environment.id
        seen["bank"] = bank
        seen["account_number"] = account_number
        seen["actor_email"] = actor_user.email
        return {
            "ok": True,
            "account_name": "Zylodo Tech Ltd",
            "bank_name": "Access Bank",
            "bank_code": "000014",
            "raw": {"data": {"accountName": "Zylodo Tech Ltd"}},
        }

    monkeypatch.setattr("apps.accounts.views.lookup_nomba_bank_account", fake_lookup)

    response = client.post(
        "/api/v1/nomba/bank-account/lookup/",
        {"bank": "Access Bank", "accountNumber": "0123456789"},
        format="json",
    )

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "accountName": "Zylodo Tech Ltd",
        "bankName": "Access Bank",
        "bankCode": "000014",
        "raw": {"data": {"accountName": "Zylodo Tech Ltd"}},
    }
    env = Environment.objects.get(merchant=merchant, mode=Environment.Mode.TEST)
    assert seen == {
        "environment_id": env.id,
        "bank": "Access Bank",
        "account_number": "0123456789",
        "actor_email": "owner@nomba-lookup-co.test",
    }
