from __future__ import annotations

import json
from datetime import timedelta
from urllib import error

import pytest
from django.test import override_settings
from django.utils import timezone

from apps.accounts.models import Environment, Merchant
from apps.customers.models import Customer
from apps.payments.integrations.nomba.client import (
    NombaAuthError,
    NombaClient,
    NombaLiveNotActiveError,
    credentials_for_environment,
)
from apps.payments.services.nomba import (
    create_nomba_virtual_account,
    list_nomba_banks,
    nomba_routing_account_id_for_environment,
    nomba_sub_account_id_for_environment,
)

pytestmark = pytest.mark.django_db


class _Response:
    def __init__(self, payload: dict):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(self.payload).encode()


def _environment(mode="test", *, byok=True):
    merchant = Merchant.objects.create(name=f"Nomba {mode}", slug=f"nomba-{mode}")
    env = Environment.objects.create(
        merchant=merchant,
        mode=mode,
        nomba_integration_mode="byok" if byok else "platform",
        nomba_account_id="acct_123",
        nomba_client_id="client_123",
    )
    env.nomba_client_secret = "secret_123"
    env.save(update_fields=["nomba_client_secret_encrypted", "updated_at"])
    return env


def test_issue_token_uses_account_header_and_persists_tokens(monkeypatch):
    env = _environment()
    seen = {}

    def fake_urlopen(req, timeout):
        seen["url"] = req.full_url
        seen["headers"] = dict(req.header_items())
        seen["body"] = json.loads(req.data.decode())
        return _Response(
            {
                "code": "00",
                "data": {
                    "access_token": "access-token",
                    "refresh_token": "refresh-token",
                    "expiresAt": "2026-07-02T12:30:00Z",
                },
            }
        )

    monkeypatch.setattr("apps.payments.integrations.nomba.client.request.urlopen", fake_urlopen)

    client = NombaClient(environment=env, credentials=credentials_for_environment(env))
    client.issue_token()

    env.refresh_from_db()
    assert seen["url"] == "https://sandbox.nomba.com/v1/auth/token/issue"
    assert seen["headers"]["Accountid"] == "acct_123"
    assert seen["headers"]["User-agent"].startswith("SubPilot/0.1")
    assert seen["headers"]["X-requested-with"] == "SubPilotBackend"
    assert seen["body"]["grant_type"] == "client_credentials"
    assert env.nomba_access_token == "access-token"
    assert env.nomba_refresh_token == "refresh-token"
    assert env.nomba_token_expires_at is not None


def test_authorized_request_refreshes_once_on_401(monkeypatch):
    env = _environment()
    env.nomba_access_token = "old-access"
    env.nomba_refresh_token = "refresh-token"
    env.nomba_token_expires_at = timezone.now() + timedelta(hours=1)
    env.save(
        update_fields=[
            "nomba_access_token_encrypted",
            "nomba_refresh_token_encrypted",
            "nomba_token_expires_at",
            "updated_at",
        ]
    )
    calls = []

    def fake_urlopen(req, timeout):
        calls.append((req.get_method(), req.full_url, dict(req.header_items()), req.data))
        if len(calls) == 1:
            raise error.HTTPError(req.full_url, 401, "Unauthorized", {}, None)
        if "/v1/auth/token/refresh" in req.full_url:
            return _Response(
                {
                    "code": "00",
                    "data": {
                        "access_token": "new-access",
                        "refresh_token": "new-refresh",
                        "expiresAt": "2026-07-02T12:30:00Z",
                    },
                }
            )
        return _Response({"code": "00", "results": []})

    monkeypatch.setattr("apps.payments.integrations.nomba.client.request.urlopen", fake_urlopen)

    client = NombaClient(environment=env, credentials=credentials_for_environment(env))
    payload = client.list_accounts()

    assert payload["code"] == "00"
    assert len(calls) == 3
    assert calls[1][1].endswith("/v1/auth/token/refresh")
    assert calls[2][2]["Authorization"] == "Bearer new-access"


def test_live_calls_require_explicit_activation():
    env = _environment("live")
    env.nomba_access_token = "live-token"
    env.nomba_token_expires_at = timezone.now() + timedelta(hours=1)
    env.save(update_fields=["nomba_access_token_encrypted", "nomba_token_expires_at", "updated_at"])

    client = NombaClient(environment=env, credentials=credentials_for_environment(env))

    with pytest.raises(NombaLiveNotActiveError):
        client.list_accounts()


@override_settings(
    NOMBA_PLATFORM_TEST_ACCOUNT_ID="platform-account",
    NOMBA_PLATFORM_TEST_CLIENT_ID="platform-client",
    NOMBA_PLATFORM_TEST_CLIENT_SECRET="platform-secret",
)
def test_platform_credentials_are_used_when_environment_is_not_byok():
    env = _environment(byok=False)
    creds = credentials_for_environment(env)

    assert creds.account_id == "acct_123"
    assert creds.client_id == "platform-client"
    assert creds.client_secret == "platform-secret"


@override_settings(NOMBA_PLATFORM_TEST_SUB_ACCOUNT_ID="platform-sub-account")
def test_platform_sub_account_fallback_is_used_when_environment_has_no_mapping():
    env = _environment(byok=False)

    assert nomba_sub_account_id_for_environment(env) == "platform-sub-account"
    assert nomba_routing_account_id_for_environment(env) == "platform-sub-account"


@override_settings(NOMBA_PLATFORM_TEST_SUB_ACCOUNT_ID="platform-sub-account")
def test_environment_sub_account_mapping_overrides_platform_fallback():
    env = _environment(byok=False)
    env.nomba_sub_account_id = "environment-sub-account"
    env.save(update_fields=["nomba_sub_account_id", "updated_at"])

    assert nomba_sub_account_id_for_environment(env) == "environment-sub-account"
    assert nomba_routing_account_id_for_environment(env) == "environment-sub-account"


@override_settings(NOMBA_PLATFORM_TEST_SUB_ACCOUNT_ID="platform-sub-account")
def test_byok_environment_does_not_inherit_platform_sub_account():
    env = _environment(byok=True)

    assert nomba_sub_account_id_for_environment(env) == ""
    assert nomba_routing_account_id_for_environment(env) == "acct_123"


@override_settings(
    NOMBA_PLATFORM_TEST_SUB_ACCOUNT_ID="platform-sub-account",
    NOMBA_PLATFORM_TEST_CLIENT_ID="platform-client",
    NOMBA_PLATFORM_TEST_CLIENT_SECRET="platform-secret",
)
def test_virtual_account_creation_uses_platform_sub_account_fallback(monkeypatch):
    env = _environment(byok=False)
    env.nomba_access_token = "access-token"
    env.nomba_token_expires_at = timezone.now() + timedelta(hours=1)
    env.save(update_fields=["nomba_access_token_encrypted", "nomba_token_expires_at", "updated_at"])
    customer = Customer.objects.create(
        merchant=env.merchant,
        environment=env,
        email="ada@example.test",
        name="Ada Example",
    )
    seen = {}

    def fake_urlopen(req, timeout):
        seen["method"] = req.get_method()
        seen["url"] = req.full_url
        return _Response({"code": "00", "data": {"accountRef": "subpilot"}})

    monkeypatch.setattr("apps.payments.integrations.nomba.client.request.urlopen", fake_urlopen)

    create_nomba_virtual_account(customer=customer)

    assert seen == {
        "method": "POST",
        "url": "https://sandbox.nomba.com/v1/accounts/virtual/platform-sub-account",
    }


@override_settings(
    NOMBA_PLATFORM_TEST_SUB_ACCOUNT_ID="platform-sub-account",
    NOMBA_PLATFORM_TEST_CLIENT_ID="platform-client",
    NOMBA_PLATFORM_TEST_CLIENT_SECRET="platform-secret",
)
def test_client_sub_account_wrappers_use_platform_fallback(monkeypatch):
    env = _environment(byok=False)
    env.nomba_access_token = "access-token"
    env.nomba_token_expires_at = timezone.now() + timedelta(hours=1)
    env.save(update_fields=["nomba_access_token_encrypted", "nomba_token_expires_at", "updated_at"])
    seen = []

    def fake_urlopen(req, timeout):
        seen.append((req.get_method(), req.full_url))
        return _Response({"code": "00"})

    monkeypatch.setattr("apps.payments.integrations.nomba.client.request.urlopen", fake_urlopen)
    client = NombaClient(environment=env, credentials=credentials_for_environment(env))

    client.bank_transfer({"merchantTxRef": "ref"})
    client.vend_airtime({"amount": 100})
    client.fetch_account_transactions()

    assert seen == [
        ("POST", "https://sandbox.nomba.com/v2/transfers/bank/platform-sub-account"),
        ("POST", "https://sandbox.nomba.com/v1/bill/topup/platform-sub-account"),
        ("GET", "https://sandbox.nomba.com/v1/transactions/accounts/platform-sub-account"),
    ]


def test_list_nomba_banks_normalizes_bank_rows(monkeypatch):
    env = _environment()
    env.nomba_access_token = "access-token"
    env.nomba_token_expires_at = timezone.now() + timedelta(hours=1)
    env.save(update_fields=["nomba_access_token_encrypted", "nomba_token_expires_at", "updated_at"])

    def fake_urlopen(req, timeout):
        assert req.full_url == "https://sandbox.nomba.com/v1/transfers/banks"
        return _Response(
            {
                "data": [
                    {"bankName": "Zenith Bank", "bankCode": "057"},
                    {"name": "Access Bank", "code": "044"},
                ]
            }
        )

    monkeypatch.setattr("apps.payments.integrations.nomba.client.request.urlopen", fake_urlopen)

    assert list_nomba_banks(env)["banks"] == [
        {"name": "Access Bank", "code": "044"},
        {"name": "Zenith Bank", "code": "057"},
    ]


def test_endpoint_wrappers_match_official_paths(monkeypatch):
    env = _environment()
    env.nomba_access_token = "access-token"
    env.nomba_token_expires_at = timezone.now() + timedelta(hours=1)
    env.save(update_fields=["nomba_access_token_encrypted", "nomba_token_expires_at", "updated_at"])
    seen = []

    def fake_urlopen(req, timeout):
        seen.append((req.get_method(), req.full_url))
        return _Response({"code": "00"})

    monkeypatch.setattr("apps.payments.integrations.nomba.client.request.urlopen", fake_urlopen)
    client = NombaClient(environment=env, credentials=credentials_for_environment(env))

    client.create_virtual_account({"accountRef": "ref", "accountName": "Example User"}, sub_account_id="sub_123")
    client.charge_tokenized_card({"tokenKey": "tok", "order": {"amount": "10.00"}})
    client.bank_transfer({"merchantTxRef": "ref"}, sub_account_id="sub_123")
    client.vend_airtime({"amount": 100}, sub_account_id="sub_123")
    client.create_mandate({"mandateId": "m"})
    client.fetch_drc_inflow_providers()

    assert seen == [
        ("POST", "https://sandbox.nomba.com/v1/accounts/virtual/sub_123"),
        ("POST", "https://sandbox.nomba.com/v1/checkout/tokenized-card-payment"),
        ("POST", "https://sandbox.nomba.com/v2/transfers/bank/sub_123"),
        ("POST", "https://sandbox.nomba.com/v1/bill/topup/sub_123"),
        ("POST", "https://sandbox.nomba.com/v1/direct-debits"),
        ("GET", "https://sandbox.nomba.com/v1/global-collection/drc/inflow/providers"),
    ]


def test_http_statuses_normalize_to_auth_error(monkeypatch):
    env = _environment()

    def fake_urlopen(req, timeout):
        raise error.HTTPError(
            req.full_url,
            401,
            "Unauthorized",
            {},
            _BytesReader({"description": "Unauthorized"}),
        )

    monkeypatch.setattr("apps.payments.integrations.nomba.client.request.urlopen", fake_urlopen)
    client = NombaClient(environment=env, credentials=credentials_for_environment(env))

    with pytest.raises(NombaAuthError):
        client.issue_token()


class _BytesReader:
    def __init__(self, payload):
        self.payload = payload

    def read(self):
        return json.dumps(self.payload).encode()

    def close(self):
        return None
