from __future__ import annotations

import json
import logging
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
from apps.platform_admin.services.settings import update_settings

pytestmark = pytest.mark.django_db


class _Response:
    def __init__(self, payload: dict, *, headers: dict | None = None, status: int = 200):
        self.payload = payload
        self.headers = headers or {}
        self.status = status

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


def test_nomba_logs_request_and_response_headers_with_redaction(monkeypatch, caplog):
    env = _environment()
    env.nomba_account_id = "acct_123456789"
    env.nomba_access_token = "access-token"
    env.nomba_token_expires_at = timezone.now() + timedelta(hours=1)
    env.save(
        update_fields=[
            "nomba_account_id",
            "nomba_access_token_encrypted",
            "nomba_token_expires_at",
            "updated_at",
        ]
    )

    def fake_urlopen(req, timeout):
        return _Response(
            {"code": "00", "data": {"tokenKey": "tok_secret", "status": "ok"}},
            headers={
                "Content-Type": "application/json",
                "Set-Cookie": "session=secret-cookie",
                "X-Nomba-Signature": "signature-secret",
                "accountId": "acct_123456789",
            },
        )

    monkeypatch.setattr("apps.payments.integrations.nomba.client.request.urlopen", fake_urlopen)
    client = NombaClient(environment=env, credentials=credentials_for_environment(env))

    with caplog.at_level(logging.WARNING, logger="apps.payments.integrations.nomba.client"):
        client.create_checkout_order({"order": {"orderReference": "checkout-ref"}})

    request_logs = [record.getMessage() for record in caplog.records if record.getMessage().startswith("nomba.request")]
    response_logs = [record.getMessage() for record in caplog.records if record.getMessage().startswith("nomba.response")]

    assert request_logs
    assert response_logs
    request_log = request_logs[-1]
    response_log = response_logs[-1]
    assert '"headers":' in request_log
    assert '"body":' in request_log
    assert '"Authorization": "[redacted]"' in request_log
    assert "Bearer access-token" not in request_log
    assert "acct_123456789" not in request_log
    assert "acct...6789" in request_log
    assert '"headers":' in response_log
    assert '"payload":' in response_log
    assert '"Set-Cookie": "[redacted]"' in response_log
    assert '"X-Nomba-Signature": "[redacted]"' in response_log
    assert '"accountId": "acct...6789"' in response_log
    assert "secret-cookie" not in response_log
    assert "signature-secret" not in response_log
    assert "tok_secret" not in response_log


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


def test_authorized_request_refreshes_once_on_nomba_jwt_expired_server_error(monkeypatch):
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
            raise error.HTTPError(
                req.full_url,
                500,
                "Internal Server Error",
                {},
                _BytesReader(
                    {
                        "detail": (
                            "Internal Server Error: INTERNAL: JWT expired at "
                            "2026-07-07T23:10:48Z."
                        )
                    }
                ),
            )
        if req.full_url.endswith("/v1/auth/token/refresh"):
            return _Response(
                {
                    "code": "00",
                    "data": {
                        "access_token": "new-access",
                        "refresh_token": "new-refresh",
                        "expiresIn": 1800,
                    },
                }
            )
        return _Response({"code": "00", "results": []})

    monkeypatch.setattr("apps.payments.integrations.nomba.client.request.urlopen", fake_urlopen)

    client = NombaClient(environment=env, credentials=credentials_for_environment(env))
    payload = client.list_accounts()

    assert payload["code"] == "00"
    assert len(calls) == 3
    assert calls[0][2]["Authorization"] == "Bearer old-access"
    assert calls[1][1].endswith("/v1/auth/token/refresh")
    assert calls[2][2]["Authorization"] == "Bearer new-access"


def test_refresh_token_falls_back_to_issue_when_refresh_access_token_is_expired(monkeypatch):
    env = _environment()
    env.nomba_access_token = "expired-access"
    env.nomba_refresh_token = "refresh-token"
    env.nomba_token_expires_at = timezone.now() - timedelta(minutes=1)
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
        if req.full_url.endswith("/v1/auth/token/refresh"):
            raise error.HTTPError(
                req.full_url,
                400,
                "Bad Request",
                {},
                _BytesReader(
                    {
                        "description": (
                            "Internal Server Error: INTERNAL: JWT expired at "
                            "2026-07-07T23:10:48Z."
                        )
                    }
                ),
            )
        if req.full_url.endswith("/v1/auth/token/issue"):
            return _Response(
                {
                    "code": "00",
                    "data": {
                        "access_token": "issued-access",
                        "refresh_token": "issued-refresh",
                        "expiresIn": 1800,
                    },
                }
            )
        return _Response({"code": "00", "data": {"checkoutLink": "https://checkout.test/pay"}})

    monkeypatch.setattr("apps.payments.integrations.nomba.client.request.urlopen", fake_urlopen)

    client = NombaClient(environment=env, credentials=credentials_for_environment(env))
    payload = client.create_checkout_order({"order": {"orderReference": "checkout-ref"}})

    assert payload["data"]["checkoutLink"] == "https://checkout.test/pay"
    assert len(calls) == 3
    assert calls[0][1].endswith("/v1/auth/token/refresh")
    assert calls[0][2]["Authorization"] == "Bearer expired-access"
    assert calls[1][1].endswith("/v1/auth/token/issue")
    assert "Authorization" not in calls[1][2]
    assert calls[2][1].endswith("/v1/checkout/order")
    assert calls[2][2]["Authorization"] == "Bearer issued-access"


def test_refresh_token_falls_back_to_issue_when_refresh_token_is_not_found(monkeypatch):
    env = _environment()
    env.nomba_access_token = "expired-access"
    env.nomba_refresh_token = "missing-refresh-token"
    env.nomba_token_expires_at = timezone.now() - timedelta(minutes=1)
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
        if req.full_url.endswith("/v1/auth/token/refresh"):
            raise error.HTTPError(
                req.full_url,
                404,
                "Not Found",
                {},
                _BytesReader(
                    {
                        "code": "404",
                        "description": "Refresh Token not found",
                        "status": False,
                    }
                ),
            )
        if req.full_url.endswith("/v1/auth/token/issue"):
            return _Response(
                {
                    "code": "00",
                    "data": {
                        "access_token": "issued-access",
                        "refresh_token": "issued-refresh",
                        "expiresIn": 1800,
                    },
                }
            )
        return _Response({"code": "00", "data": {"checkoutLink": "https://checkout.test/pay"}})

    monkeypatch.setattr("apps.payments.integrations.nomba.client.request.urlopen", fake_urlopen)

    client = NombaClient(environment=env, credentials=credentials_for_environment(env))
    payload = client.create_checkout_order({"order": {"orderReference": "checkout-ref"}})

    assert payload["data"]["checkoutLink"] == "https://checkout.test/pay"
    assert len(calls) == 3
    assert calls[0][1].endswith("/v1/auth/token/refresh")
    assert calls[1][1].endswith("/v1/auth/token/issue")
    assert "Authorization" not in calls[1][2]
    assert calls[2][1].endswith("/v1/checkout/order")
    assert calls[2][2]["Authorization"] == "Bearer issued-access"


def test_expired_token_refresh_does_not_recurse_before_checkout(monkeypatch):
    env = _environment()
    env.nomba_access_token = "expired-access"
    env.nomba_refresh_token = "refresh-token"
    env.nomba_token_expires_at = timezone.now() - timedelta(minutes=1)
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
        if req.full_url.endswith("/v1/auth/token/refresh"):
            return _Response(
                {
                    "code": "00",
                    "data": {
                        "access_token": "new-access",
                        "refresh_token": "new-refresh",
                        "expiresIn": 1800,
                    },
                }
            )
        return _Response({"code": "00", "data": {"checkoutLink": "https://checkout.test/pay"}})

    monkeypatch.setattr("apps.payments.integrations.nomba.client.request.urlopen", fake_urlopen)

    client = NombaClient(environment=env, credentials=credentials_for_environment(env))
    payload = client.create_checkout_order({"order": {"orderReference": "checkout-ref"}})

    assert payload["data"]["checkoutLink"] == "https://checkout.test/pay"
    assert len(calls) == 2
    assert calls[0][1].endswith("/v1/auth/token/refresh")
    assert calls[0][2]["Authorization"] == "Bearer expired-access"
    assert calls[1][1].endswith("/v1/checkout/order")
    assert calls[1][2]["Authorization"] == "Bearer new-access"


def test_missing_access_token_issues_new_token_before_checkout(monkeypatch):
    env = _environment()
    env.nomba_refresh_token = "refresh-token"
    env.nomba_token_expires_at = timezone.now() - timedelta(minutes=1)
    env.save(update_fields=["nomba_refresh_token_encrypted", "nomba_token_expires_at", "updated_at"])
    calls = []

    def fake_urlopen(req, timeout):
        calls.append((req.get_method(), req.full_url, dict(req.header_items()), req.data))
        if req.full_url.endswith("/v1/auth/token/issue"):
            return _Response(
                {
                    "code": "00",
                    "data": {
                        "access_token": "issued-access",
                        "refresh_token": "issued-refresh",
                        "expiresIn": 1800,
                    },
                }
            )
        return _Response({"code": "00", "data": {"checkoutLink": "https://checkout.test/pay"}})

    monkeypatch.setattr("apps.payments.integrations.nomba.client.request.urlopen", fake_urlopen)

    client = NombaClient(environment=env, credentials=credentials_for_environment(env))
    payload = client.create_checkout_order({"order": {"orderReference": "checkout-ref"}})

    assert payload["data"]["checkoutLink"] == "https://checkout.test/pay"
    assert len(calls) == 2
    assert calls[0][1].endswith("/v1/auth/token/issue")
    assert "Authorization" not in calls[0][2]
    assert calls[1][1].endswith("/v1/checkout/order")
    assert calls[1][2]["Authorization"] == "Bearer issued-access"


def test_live_calls_require_explicit_activation():
    env = _environment("live")
    env.nomba_access_token = "live-token"
    env.nomba_token_expires_at = timezone.now() + timedelta(hours=1)
    env.save(update_fields=["nomba_access_token_encrypted", "nomba_token_expires_at", "updated_at"])

    client = NombaClient(environment=env, credentials=credentials_for_environment(env))

    with pytest.raises(NombaLiveNotActiveError):
        client.list_accounts()


def test_platform_managed_live_credentials_are_read_from_platform_admin_settings(platform_admin_owner):
    env = _environment("live", byok=False)
    update_settings(
        actor=platform_admin_owner,
        nomba_platform={
            "liveActive": True,
            "live": {
                "baseUrl": "https://live.nomba.test",
                "accountId": "platform-live-account",
                "subAccountId": "platform-live-sub",
                "clientId": "platform-live-client",
                "clientSecret": "platform-live-secret",
            },
        },
    )

    creds = credentials_for_environment(env)

    assert creds.base_url == "https://live.nomba.test"
    assert creds.account_id == "platform-live-account"
    assert creds.client_id == "platform-live-client"
    assert creds.client_secret == "platform-live-secret"
    assert creds.live_active is True
    assert NombaClient(environment=env, credentials=creds).routing_account_id() == "platform-live-sub"


def test_platform_managed_checkout_uses_selected_live_platform_mode(platform_admin_owner):
    env = _environment("test", byok=False)
    update_settings(
        actor=platform_admin_owner,
        nomba_platform={
            "activeMode": "live",
            "liveActive": True,
            "test": {
                "baseUrl": "https://sandbox.nomba.test",
                "accountId": "platform-test-account",
                "subAccountId": "platform-test-sub",
                "clientId": "platform-test-client",
                "clientSecret": "platform-test-secret",
            },
            "live": {
                "baseUrl": "https://live.nomba.test",
                "accountId": "platform-live-account",
                "subAccountId": "platform-live-sub",
                "clientId": "platform-live-client",
                "clientSecret": "platform-live-secret",
            },
        },
    )

    creds = credentials_for_environment(env)

    assert creds.mode == "live"
    assert creds.base_url == "https://live.nomba.test"
    assert creds.account_id == "platform-live-account"
    assert creds.client_id == "platform-live-client"
    assert creds.client_secret == "platform-live-secret"
    assert creds.live_active is True
    assert nomba_sub_account_id_for_environment(env) == "platform-live-sub"
    assert nomba_routing_account_id_for_environment(env) == "platform-live-sub"
    assert NombaClient(environment=env, credentials=creds).routing_account_id() == "platform-live-sub"


def test_byok_ignores_selected_live_platform_mode(platform_admin_owner):
    env = _environment("test", byok=True)
    update_settings(
        actor=platform_admin_owner,
        nomba_platform={
            "activeMode": "live",
            "liveActive": True,
            "live": {
                "baseUrl": "https://live.nomba.test",
                "accountId": "platform-live-account",
                "clientId": "platform-live-client",
                "clientSecret": "platform-live-secret",
            },
        },
    )

    creds = credentials_for_environment(env)

    assert creds.mode == "test"
    assert creds.base_url == "https://sandbox.nomba.com"
    assert creds.account_id == "acct_123"
    assert creds.client_id == "client_123"
    assert creds.client_secret == "secret_123"


@override_settings(
    NOMBA_PLATFORM_TEST_ACCOUNT_ID="platform-account",
    NOMBA_PLATFORM_TEST_CLIENT_ID="platform-client",
    NOMBA_PLATFORM_TEST_CLIENT_SECRET="platform-secret",
)
def test_platform_credentials_are_used_when_environment_is_not_byok():
    env = _environment(byok=False)
    creds = credentials_for_environment(env)

    assert creds.account_id == "platform-account"
    assert creds.client_id == "platform-client"
    assert creds.client_secret == "platform-secret"


@override_settings(
    NOMBA_PLATFORM_TEST_ACCOUNT_ID="parent-account",
    NOMBA_PLATFORM_TEST_CLIENT_ID="platform-client",
    NOMBA_PLATFORM_TEST_CLIENT_SECRET="platform-secret",
)
def test_platform_issue_token_uses_parent_account_header(monkeypatch):
    env = _environment(byok=False)
    env.nomba_account_id = "mistaken-sub-account"
    env.save(update_fields=["nomba_account_id", "updated_at"])
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
                    "expiresIn": 1800,
                },
            }
        )

    monkeypatch.setattr("apps.payments.integrations.nomba.client.request.urlopen", fake_urlopen)

    client = NombaClient(environment=env, credentials=credentials_for_environment(env))
    client.issue_token()

    assert seen["url"] == "https://sandbox.nomba.com/v1/auth/token/issue"
    assert seen["headers"]["Accountid"] == "parent-account"
    assert seen["body"]["client_id"] == "platform-client"


@override_settings(
    NOMBA_PLATFORM_TEST_ACCOUNT_ID="parent-account",
    NOMBA_PLATFORM_TEST_SUB_ACCOUNT_ID="platform-sub-account",
    NOMBA_PLATFORM_TEST_CLIENT_ID="platform-client",
    NOMBA_PLATFORM_TEST_CLIENT_SECRET="platform-secret",
)
def test_platform_nomba_requests_keep_parent_account_in_header(monkeypatch):
    env = _environment(byok=False)
    env.nomba_access_token = "access-token"
    env.nomba_token_expires_at = timezone.now() + timedelta(hours=1)
    env.nomba_account_id = "mistaken-sub-account"
    env.save(
        update_fields=[
            "nomba_access_token_encrypted",
            "nomba_token_expires_at",
            "nomba_account_id",
            "updated_at",
        ]
    )
    seen = []

    def fake_urlopen(req, timeout):
        seen.append(
            (req.get_method(), req.full_url, dict(req.header_items())["Accountid"])
        )
        return _Response({"code": "00"})

    monkeypatch.setattr("apps.payments.integrations.nomba.client.request.urlopen", fake_urlopen)
    client = NombaClient(environment=env, credentials=credentials_for_environment(env))

    client.bank_transfer({"merchantTxRef": "ref"})
    client.vend_airtime({"amount": 100})
    client.fetch_account_transactions()

    assert seen == [
        (
            "POST",
            "https://sandbox.nomba.com/v2/transfers/bank/platform-sub-account",
            "parent-account",
        ),
        (
            "POST",
            "https://sandbox.nomba.com/v1/bill/topup/platform-sub-account",
            "parent-account",
        ),
        (
            "GET",
            "https://sandbox.nomba.com/v1/transactions/accounts/platform-sub-account",
            "parent-account",
        ),
    ]


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
    NOMBA_PLATFORM_TEST_ACCOUNT_ID="platform-account",
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
        seen.append(
            (req.get_method(), req.full_url, dict(req.header_items())["Accountid"])
        )
        return _Response({"code": "00"})

    monkeypatch.setattr("apps.payments.integrations.nomba.client.request.urlopen", fake_urlopen)
    client = NombaClient(environment=env, credentials=credentials_for_environment(env))

    client.bank_transfer({"merchantTxRef": "ref"})
    client.vend_airtime({"amount": 100})
    client.fetch_account_transactions()

    assert seen == [
        (
            "POST",
            "https://sandbox.nomba.com/v2/transfers/bank/platform-sub-account",
            "platform-account",
        ),
        (
            "POST",
            "https://sandbox.nomba.com/v1/bill/topup/platform-sub-account",
            "platform-account",
        ),
        (
            "GET",
            "https://sandbox.nomba.com/v1/transactions/accounts/platform-sub-account",
            "platform-account",
        ),
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
        seen.append((req.get_method(), req.full_url, dict(req.header_items())["Accountid"]))
        return _Response({"code": "00"})

    monkeypatch.setattr("apps.payments.integrations.nomba.client.request.urlopen", fake_urlopen)
    client = NombaClient(environment=env, credentials=credentials_for_environment(env))

    client.create_virtual_account({"accountRef": "ref", "accountName": "Example User"}, sub_account_id="sub_123")
    client.filter_virtual_accounts({"accountRef": "ref"})
    client.fetch_virtual_account("va_ref")
    client.expire_virtual_account("va_ref")
    client.fetch_sub_account_balance("sub_123")
    client.fetch_account_transactions(sub_account_id="sub_123")
    client.filter_account_transactions({"status": "SUCCESS"}, sub_account_id="sub_123")
    client.requery_transaction("session_123")
    client.create_checkout_order({"order": {"amount": "10.00", "currency": "NGN"}})
    client.get_checkout_order("order_ref")
    client.submit_card_details({"checkoutId": "checkout_id"})
    client.submit_card_otp({"checkoutId": "checkout_id", "otp": "9999"})
    client.get_checkout_kta("order_ref")
    client.refund_checkout_transaction({"transactionId": "txn_123"})
    client.charge_tokenized_card({"tokenKey": "tok", "order": {"amount": "10.00"}})
    client.list_tokenized_cards()
    client.create_direct_debit_mandate({"merchantReference": "123"})
    client.debit_direct_debit_mandate({"mandateId": "mandate_123", "amount": "100.00"})
    client.get_direct_debit_mandate("mandate_123")
    client.bank_transfer({"merchantTxRef": "ref"}, sub_account_id="sub_123")
    client.lookup_bank_account({"accountNumber": "0000000000", "bankCode": "035"})
    client.fetch_banks()
    client.vend_airtime({"amount": 100}, sub_account_id="sub_123")
    client.vend_data({"amount": 100}, sub_account_id="sub_123")
    client.vend_electricity({"amount": 100}, sub_account_id="sub_123")
    client.vend_cabletv({"amount": 100}, sub_account_id="sub_123")
    client.global_payout_exchange_rates()
    client.global_payout_convert_money({"amount": "10.00"})
    client.global_payout_authorize_transfer({"amount": "10.00"})
    client.wallet_transfer({"merchantTxRef": "ref"}, sub_account_id="sub_123")
    client.terminal_payment_request("terminal_123", {"amount": "10.00"})

    assert seen == [
        ("POST", "https://sandbox.nomba.com/v1/accounts/virtual/sub_123", "acct_123"),
        ("POST", "https://sandbox.nomba.com/v1/accounts/virtual/list", "acct_123"),
        ("GET", "https://sandbox.nomba.com/v1/accounts/virtual/va_ref", "acct_123"),
        ("DELETE", "https://sandbox.nomba.com/v1/accounts/virtual/va_ref", "acct_123"),
        ("GET", "https://sandbox.nomba.com/v1/accounts/sub_123/balance", "acct_123"),
        ("GET", "https://sandbox.nomba.com/v1/transactions/accounts/sub_123", "acct_123"),
        ("POST", "https://sandbox.nomba.com/v1/transactions/accounts/sub_123", "acct_123"),
        ("GET", "https://sandbox.nomba.com/v1/transactions/requery/session_123", "acct_123"),
        ("POST", "https://sandbox.nomba.com/v1/checkout/order", "acct_123"),
        ("GET", "https://sandbox.nomba.com/v1/checkout/order/order_ref", "acct_123"),
        ("POST", "https://sandbox.nomba.com/v1/checkout/checkout-card-detail", "acct_123"),
        ("POST", "https://sandbox.nomba.com/v1/checkout/checkout-card-otp", "acct_123"),
        ("GET", "https://sandbox.nomba.com/v1/checkout/get-checkout-kta/order_ref", "acct_123"),
        ("POST", "https://sandbox.nomba.com/v1/checkout/refund", "acct_123"),
        ("POST", "https://sandbox.nomba.com/v1/checkout/tokenized-card-payment", "acct_123"),
        ("GET", "https://sandbox.nomba.com/v1/checkout/tokenized-card-data", "acct_123"),
        ("POST", "https://sandbox.nomba.com/v1/direct-debits", "acct_123"),
        ("POST", "https://sandbox.nomba.com/v1/direct-debits/debit-mandate", "acct_123"),
        ("GET", "https://sandbox.nomba.com/v1/direct-debits/mandate_123", "acct_123"),
        ("POST", "https://sandbox.nomba.com/v2/transfers/bank/sub_123", "acct_123"),
        ("POST", "https://sandbox.nomba.com/v1/transfers/bank/lookup", "acct_123"),
        ("GET", "https://sandbox.nomba.com/v1/transfers/banks", "acct_123"),
        ("POST", "https://sandbox.nomba.com/v1/bill/topup/sub_123", "acct_123"),
        ("POST", "https://sandbox.nomba.com/v1/bill/data/sub_123", "acct_123"),
        ("POST", "https://sandbox.nomba.com/v1/bill/electricity/sub_123", "acct_123"),
        ("POST", "https://sandbox.nomba.com/v1/bill/cabletv/sub_123", "acct_123"),
        ("GET", "https://sandbox.nomba.com/v1/global-payout/exchange-rates", "acct_123"),
        ("POST", "https://sandbox.nomba.com/v1/global-payout/money/convert", "acct_123"),
        ("POST", "https://sandbox.nomba.com/v1/global-payout/transfer/authorize", "acct_123"),
        ("POST", "https://sandbox.nomba.com/v2/transfers/wallet/sub_123", "acct_123"),
        ("POST", "https://sandbox.nomba.com/v1/terminals/payment-request/terminal_123", "acct_123"),
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
