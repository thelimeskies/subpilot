"""OAuth-aware internal Nomba API client.

The public SubPilot API does not proxy Nomba directly. This client is the
internal integration boundary used by billing services and narrow credential
management endpoints.
"""
from __future__ import annotations

import json
import logging
import socket
from dataclasses import dataclass
from datetime import timezone as datetime_timezone
from datetime import timedelta
from typing import Any
from urllib import error, parse, request

from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime


logger = logging.getLogger(__name__)


class NombaError(Exception):
    """Base class for all Nomba integration errors."""


class NombaLiveNotActiveError(NombaError):
    """Raised when production calls are attempted before explicit activation."""


class NombaRequestError(NombaError):
    def __init__(self, message: str, *, status_code: int = 0, payload: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


class NombaValidationError(NombaRequestError):
    pass


class NombaAuthError(NombaRequestError):
    pass


class NombaForbiddenError(NombaRequestError):
    pass


class NombaNotFoundError(NombaRequestError):
    pass


class NombaRateLimitError(NombaRequestError):
    pass


class NombaServerError(NombaRequestError):
    pass


class NombaTimeoutError(NombaRequestError):
    pass


@dataclass(frozen=True)
class NombaCredentials:
    mode: str
    account_id: str
    client_id: str
    client_secret: str
    base_url: str
    live_active: bool = False


class NombaClient:
    """Small generated-style wrapper around Nomba's official OpenAPI paths."""

    REFRESH_WINDOW = timedelta(minutes=5)
    USER_AGENT = "SubPilot/0.1 (+https://subpilot.kylodo.com; nomba-api-client)"
    REDACTED = "[redacted]"
    LOG_VALUE_LIMIT = 4000

    def __init__(self, *, environment, credentials: NombaCredentials, timeout_seconds: float = 20.0) -> None:
        self.environment = environment
        self.credentials = credentials
        self.base_url = credentials.base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def _sub_account_id(self, explicit: str = "") -> str:
        if explicit:
            return explicit
        if self.environment.nomba_sub_account_id:
            return self.environment.nomba_sub_account_id
        if self.environment.nomba_integration_mode == "byok":
            return ""
        if self.environment.mode == "live":
            return getattr(settings, "NOMBA_PLATFORM_LIVE_SUB_ACCOUNT_ID", "") or ""
        return getattr(settings, "NOMBA_PLATFORM_TEST_SUB_ACCOUNT_ID", "") or ""

    # ------------------------------------------------------------------ auth
    def issue_token(self) -> dict[str, Any]:
        payload = self._request_json(
            "POST",
            "/v1/auth/token/issue",
            body={
                "grant_type": "client_credentials",
                "client_id": self.credentials.client_id,
                "client_secret": self.credentials.client_secret,
            },
            authorized=False,
            enforce_live_activation=False,
        )
        data = payload.get("data") if isinstance(payload, dict) else {}
        self._persist_token(data if isinstance(data, dict) else {})
        return payload

    def refresh_token(self) -> dict[str, Any]:
        refresh_token = self.environment.nomba_refresh_token
        if not refresh_token:
            return self.issue_token()
        payload = self._request_json(
            "POST",
            "/v1/auth/token/refresh",
            body={"grant_type": "refresh_token", "refresh_token": refresh_token},
            authorized=True,
            enforce_live_activation=False,
            refresh_on_401=False,
        )
        data = payload.get("data") if isinstance(payload, dict) else {}
        self._persist_token(data if isinstance(data, dict) else {})
        return payload

    def revoke_token(self, access_token: str | None = None) -> dict[str, Any]:
        token = access_token or self.environment.nomba_access_token
        return self._request_json(
            "POST",
            "/v1/auth/token/revoke",
            body={"clientId": self.credentials.client_id, "access_token": token},
            authorized=False,
            enforce_live_activation=False,
        )

    # --------------------------------------------------------------- low-level
    def request(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        query: dict[str, Any] | None = None,
        authorized: bool = True,
        enforce_live_activation: bool = True,
    ) -> dict[str, Any]:
        return self._request_json(
            method,
            path,
            body=body,
            query=query,
            authorized=authorized,
            enforce_live_activation=enforce_live_activation,
        )

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        query: dict[str, Any] | None = None,
        authorized: bool = True,
        enforce_live_activation: bool = True,
        refresh_on_401: bool = True,
    ) -> dict[str, Any]:
        if enforce_live_activation and self.credentials.mode == "live" and not self.credentials.live_active:
            raise NombaLiveNotActiveError("Live Nomba calls require explicit activation.")
        if authorized:
            self._ensure_access_token()
        try:
            return self._send(method, path, body=body, query=query, authorized=authorized)
        except NombaAuthError:
            if not authorized or not refresh_on_401:
                raise
            self.refresh_token()
            return self._send(method, path, body=body, query=query, authorized=authorized)

    def _send(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        query: dict[str, Any] | None = None,
        authorized: bool = True,
    ) -> dict[str, Any]:
        url = self._url(path, query)
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": getattr(settings, "NOMBA_HTTP_USER_AGENT", self.USER_AGENT),
            "X-Requested-With": "SubPilotBackend",
            "accountId": self.credentials.account_id,
        }
        if authorized:
            headers["Authorization"] = f"Bearer {self.environment.nomba_access_token}"
        data = json.dumps(body or {}).encode("utf-8") if body is not None else None
        req = request.Request(url, data=data, headers=headers, method=method.upper())
        self._log_request(method=method, url=url, headers=headers, body=body)
        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as response:
                payload = self._decode_response(response.read())
                status_code = getattr(response, "status", None)
                if status_code is None and hasattr(response, "getcode"):
                    status_code = response.getcode()
                self._log_response(method=method, url=url, status_code=status_code or 200, payload=payload)
                return payload
        except error.HTTPError as exc:
            payload = self._decode_response(exc.read())
            self._log_response(method=method, url=url, status_code=exc.code, payload=payload, failed=True)
            raise self._error_for_status(exc.code, payload) from exc
        except (error.URLError, TimeoutError, socket.timeout) as exc:
            self._log_transport_error(method=method, url=url, exc=exc)
            raise NombaTimeoutError(str(exc), status_code=0, payload={"exception": exc.__class__.__name__}) from exc

    @classmethod
    def _redact(cls, value: Any) -> Any:
        if isinstance(value, dict):
            redacted = {}
            for key, child in value.items():
                lowered = str(key).lower()
                if any(part in lowered for part in ("authorization", "secret", "token", "password")):
                    redacted[key] = cls.REDACTED
                elif lowered in {"client_id", "clientid", "accountid", "account_id"}:
                    redacted[key] = cls._mask_identifier(str(child))
                else:
                    redacted[key] = cls._redact(child)
            return redacted
        if isinstance(value, list):
            return [cls._redact(item) for item in value[:50]]
        return value

    @staticmethod
    def _mask_identifier(value: str) -> str:
        if len(value) <= 8:
            return value
        return f"{value[:4]}...{value[-4:]}"

    @classmethod
    def _limit(cls, value: Any) -> Any:
        rendered = json.dumps(value, default=str, ensure_ascii=True)
        if len(rendered) <= cls.LOG_VALUE_LIMIT:
            return value
        return {"truncated": True, "preview": rendered[: cls.LOG_VALUE_LIMIT]}

    def _log_request(self, *, method: str, url: str, headers: dict[str, str], body: dict[str, Any] | None) -> None:
        logger.warning("nomba.request %s", self._log_json({
            "method": method.upper(),
            "url": url,
            "headers": self._limit(self._redact(headers)),
            "body": self._limit(self._redact(body or {})),
            "environment_id": str(getattr(self.environment, "id", "")),
            "merchant_id": str(getattr(self.environment, "merchant_id", "")),
            "mode": self.credentials.mode,
        }))

    def _log_response(
        self,
        *,
        method: str,
        url: str,
        status_code: int,
        payload: dict[str, Any],
        failed: bool = False,
    ) -> None:
        logger.warning("nomba.response %s", self._log_json({
            "method": method.upper(),
            "url": url,
            "status_code": status_code,
            "failed": failed,
            "payload": self._limit(self._redact(payload)),
            "environment_id": str(getattr(self.environment, "id", "")),
            "merchant_id": str(getattr(self.environment, "merchant_id", "")),
            "mode": self.credentials.mode,
        }))

    def _log_transport_error(self, *, method: str, url: str, exc: Exception) -> None:
        logger.warning("nomba.transport_error %s", self._log_json({
            "method": method.upper(),
            "url": url,
            "exception": exc.__class__.__name__,
            "reason": str(exc),
            "environment_id": str(getattr(self.environment, "id", "")),
            "merchant_id": str(getattr(self.environment, "merchant_id", "")),
            "mode": self.credentials.mode,
        }))

    @staticmethod
    def _log_json(payload: dict[str, Any]) -> str:
        return json.dumps(payload, default=str, ensure_ascii=True, sort_keys=True)

    def _url(self, path: str, query: dict[str, Any] | None = None) -> str:
        normalized = path if path.startswith("/") else f"/{path}"
        url = f"{self.base_url}{normalized}"
        if not query:
            return url
        clean = {key: value for key, value in query.items() if value is not None}
        return f"{url}?{parse.urlencode(clean, doseq=True)}"

    @staticmethod
    def _decode_response(raw: bytes) -> dict[str, Any]:
        if not raw:
            return {}
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return {"raw": raw.decode("utf-8", errors="replace")}
        return payload if isinstance(payload, dict) else {"data": payload}

    @staticmethod
    def _error_message(payload: Any, fallback: str) -> str:
        if isinstance(payload, dict):
            for key in ("reason", "description", "message", "error", "detail", "raw"):
                if payload.get(key):
                    return str(payload[key])
        return fallback

    def _error_for_status(self, status_code: int, payload: dict[str, Any]) -> NombaRequestError:
        message = self._error_message(payload, f"Nomba request failed ({status_code}).")
        cls: type[NombaRequestError]
        if status_code == 400:
            cls = NombaValidationError
        elif status_code == 401:
            cls = NombaAuthError
        elif status_code == 403:
            cls = NombaForbiddenError
        elif status_code == 404:
            cls = NombaNotFoundError
        elif status_code == 429:
            cls = NombaRateLimitError
        elif status_code >= 500:
            cls = NombaServerError
        else:
            cls = NombaRequestError
        return cls(message, status_code=status_code, payload=payload)

    def _ensure_access_token(self) -> None:
        expires_at = self.environment.nomba_token_expires_at
        if self.environment.nomba_access_token and expires_at and expires_at > timezone.now() + self.REFRESH_WINDOW:
            return
        if self.environment.nomba_refresh_token:
            self.refresh_token()
        else:
            self.issue_token()

    def _persist_token(self, data: dict[str, Any]) -> None:
        access_token = str(data.get("access_token") or "")
        refresh_token = str(data.get("refresh_token") or "")
        expires_raw = str(data.get("expiresAt") or "")
        expires_at = parse_datetime(expires_raw) if expires_raw else None
        if expires_at is not None and timezone.is_naive(expires_at):
            expires_at = timezone.make_aware(expires_at, datetime_timezone.utc)
        if access_token:
            self.environment.nomba_access_token = access_token
        if refresh_token:
            self.environment.nomba_refresh_token = refresh_token
        self.environment.nomba_token_expires_at = expires_at
        self.environment.save(
            update_fields=[
                "nomba_access_token_encrypted",
                "nomba_refresh_token_encrypted",
                "nomba_token_expires_at",
                "updated_at",
            ]
        )

    # ---------------------------------------------------------- endpoint group
    # Authenticate
    # issue_token / refresh_token / revoke_token are explicit above.

    # Accounts
    def list_accounts(self, **query: Any) -> dict[str, Any]:
        return self.request("GET", "/v1/accounts", query=query)

    def create_sub_account(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.request("POST", "/v1/accounts", body=payload)

    def fetch_sub_account_details(self, **query: Any) -> dict[str, Any]:
        return self.request("GET", "/v1/accounts/sub-account-details", query=query)

    def fetch_parent_account_details(self) -> dict[str, Any]:
        return self.request("GET", "/v1/accounts/parent")

    def fetch_parent_account_balance(self) -> dict[str, Any]:
        return self.request("GET", "/v1/accounts/balance")

    def fetch_sub_account_balance(self, sub_account_id: str) -> dict[str, Any]:
        return self.request("GET", f"/v1/accounts/{sub_account_id}/balance")

    def fetch_parent_terminals(self) -> dict[str, Any]:
        return self.request("GET", "/v1/accounts/terminals")

    def fetch_sub_account_terminals(self, sub_account_id: str) -> dict[str, Any]:
        return self.request("GET", f"/v1/accounts/{sub_account_id}/terminals")

    # Virtual Accounts
    def create_virtual_account(self, payload: dict[str, Any], *, sub_account_id: str = "") -> dict[str, Any]:
        sub_account_id = self._sub_account_id(sub_account_id)
        path = f"/v1/accounts/virtual/{sub_account_id}" if sub_account_id else "/v1/accounts/virtual"
        return self.request("POST", path, body=payload)

    def filter_virtual_accounts(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.request("POST", "/v1/accounts/virtual/list", body=payload)

    def fetch_virtual_account(self, identifier: str) -> dict[str, Any]:
        return self.request("GET", f"/v1/accounts/virtual/{identifier}")

    def update_virtual_account(self, identifier: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self.request("PUT", f"/v1/accounts/virtual/{identifier}", body=payload)

    def expire_virtual_account(self, identifier: str) -> dict[str, Any]:
        return self.request("DELETE", f"/v1/accounts/virtual/{identifier}")

    # Online Checkout / Charge
    def create_checkout_order(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.request("POST", "/v1/checkout/order", body=payload)

    def cancel_checkout_order(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.request("POST", "/v1/checkout/order/cancel", body=payload)

    def get_checkout_order(self, order_reference: str) -> dict[str, Any]:
        return self.request("GET", f"/v1/checkout/order/{order_reference}")

    def charge_tokenized_card(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.request("POST", "/v1/checkout/tokenized-card-payment", body=payload)

    def list_tokenized_cards(self, **query: Any) -> dict[str, Any]:
        return self.request("GET", "/v1/checkout/tokenized-card-data", query=query)

    def update_tokenized_card(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.request("POST", "/v1/checkout/tokenized-card-data", body=payload)

    def delete_tokenized_card(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.request("DELETE", "/v1/checkout/tokenized-card-data", body=payload)

    def fetch_checkout_transaction(self, **query: Any) -> dict[str, Any]:
        return self.request("GET", "/v1/checkout/transaction", query=query)

    def refund_checkout_transaction(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.request("POST", "/v1/checkout/refund", body=payload)

    def submit_card_details(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.request("POST", "/v1/checkout/checkout-card-detail", body=payload)

    def submit_card_otp(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.request("POST", "/v1/checkout/checkout-card-otp", body=payload)

    def resend_card_otp(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.request("POST", "/v1/checkout/resend-otp", body=payload)

    def confirm_transaction_receipt(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.request("POST", "/v1/checkout/confirm-transaction-receipt", body=payload)

    def fetch_checkout_flash_account(self, order_reference: str) -> dict[str, Any]:
        return self.request("GET", f"/v1/checkout/get-checkout-kta/{order_reference}")

    def request_user_card_otp(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.request("POST", "/v1/checkout/user-card/auth", body=payload)

    def request_saved_card_otp(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.request("POST", "/v1/checkout/user-card/saved-card/auth", body=payload)

    def submit_user_card_otp(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.request("POST", "/v1/checkout/user-card", body=payload)

    def get_user_saved_cards(self, order_reference: str) -> dict[str, Any]:
        return self.request("GET", f"/v1/checkout/user-card/{order_reference}")

    def cancel_checkout_transaction(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.request("POST", "/v1/checkout/transaction/cancel", body=payload)

    # Transfers
    def fetch_banks(self) -> dict[str, Any]:
        return self.request("GET", "/v1/transfers/banks")

    def lookup_bank_account(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.request("POST", "/v1/transfers/bank/lookup", body=payload)

    def bank_transfer(self, payload: dict[str, Any], *, sub_account_id: str = "") -> dict[str, Any]:
        sub_account_id = self._sub_account_id(sub_account_id)
        path = f"/v2/transfers/bank/{sub_account_id}" if sub_account_id else "/v2/transfers/bank"
        return self.request("POST", path, body=payload)

    def wallet_transfer(self, payload: dict[str, Any], *, sub_account_id: str = "") -> dict[str, Any]:
        sub_account_id = self._sub_account_id(sub_account_id)
        path = f"/v2/transfers/wallet/{sub_account_id}" if sub_account_id else "/v2/transfers/wallet"
        return self.request("POST", path, body=payload)

    # Terminals
    def assign_terminal(self, payload: dict[str, Any], *, sub_account_id: str = "") -> dict[str, Any]:
        sub_account_id = self._sub_account_id(sub_account_id)
        path = f"/v1/terminals/assign/{sub_account_id}" if sub_account_id else "/v1/terminals/assign"
        return self.request("POST", path, body=payload)

    def unassign_terminal(self, payload: dict[str, Any], *, sub_account_id: str = "") -> dict[str, Any]:
        sub_account_id = self._sub_account_id(sub_account_id)
        path = f"/v1/terminals/unassign/{sub_account_id}" if sub_account_id else "/v1/terminals/unassign"
        return self.request("POST", path, body=payload)

    def send_terminal_payment_request(self, terminal_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self.request("POST", f"/v1/terminals/payment-request/{terminal_id}", body=payload)

    # Transactions
    def fetch_credit_debit_transactions(self, *, sub_account_id: str = "", **query: Any) -> dict[str, Any]:
        sub_account_id = self._sub_account_id(sub_account_id)
        path = f"/v1/transactions/bank/{sub_account_id}" if sub_account_id else "/v1/transactions/bank"
        return self.request("GET", path, query=query)

    def fetch_account_transactions(self, *, sub_account_id: str = "", **query: Any) -> dict[str, Any]:
        sub_account_id = self._sub_account_id(sub_account_id)
        path = f"/v1/transactions/accounts/{sub_account_id}" if sub_account_id else "/v1/transactions/accounts"
        return self.request("GET", path, query=query)

    def filter_account_transactions(self, payload: dict[str, Any], *, sub_account_id: str = "") -> dict[str, Any]:
        sub_account_id = self._sub_account_id(sub_account_id)
        path = f"/v1/transactions/accounts/{sub_account_id}" if sub_account_id else "/v1/transactions/accounts"
        return self.request("POST", path, body=payload)

    def fetch_single_transaction(self, *, sub_account_id: str = "", **query: Any) -> dict[str, Any]:
        sub_account_id = self._sub_account_id(sub_account_id)
        path = f"/v1/transactions/accounts/{sub_account_id}/single" if sub_account_id else "/v1/transactions/accounts/single"
        return self.request("GET", path, query=query)

    def requery_transaction(self, session_id: str) -> dict[str, Any]:
        return self.request("GET", f"/v1/transactions/requery/{session_id}")

    # Airtime / Data / Bills
    def fetch_data_plans(self, telco: str) -> dict[str, Any]:
        return self.request("GET", f"/v1/bill/data-plan/{telco}")

    def vend_airtime(self, payload: dict[str, Any], *, sub_account_id: str = "") -> dict[str, Any]:
        sub_account_id = self._sub_account_id(sub_account_id)
        path = f"/v1/bill/topup/{sub_account_id}" if sub_account_id else "/v1/bill/topup"
        return self.request("POST", path, body=payload)

    def vend_data(self, payload: dict[str, Any], *, sub_account_id: str = "") -> dict[str, Any]:
        sub_account_id = self._sub_account_id(sub_account_id)
        path = f"/v1/bill/data/{sub_account_id}" if sub_account_id else "/v1/bill/data"
        return self.request("POST", path, body=payload)

    def cabletv_lookup(self, **query: Any) -> dict[str, Any]:
        return self.request("GET", "/v1/bill/cabletv/lookup", query=query)

    def vend_cabletv(self, payload: dict[str, Any], *, sub_account_id: str = "") -> dict[str, Any]:
        sub_account_id = self._sub_account_id(sub_account_id)
        path = f"/v1/bill/cabletv/{sub_account_id}" if sub_account_id else "/v1/bill/cabletv"
        return self.request("POST", path, body=payload)

    def fetch_electricity_providers(self) -> dict[str, Any]:
        return self.request("GET", "/v1/bill/electricity/discos")

    def electricity_lookup(self, **query: Any) -> dict[str, Any]:
        return self.request("GET", "/v1/bill/electricity/lookup", query=query)

    def vend_electricity(self, payload: dict[str, Any], *, sub_account_id: str = "") -> dict[str, Any]:
        sub_account_id = self._sub_account_id(sub_account_id)
        path = f"/v1/bill/electricity/{sub_account_id}" if sub_account_id else "/v1/bill/electricity"
        return self.request("POST", path, body=payload)

    def fetch_betting_providers(self) -> dict[str, Any]:
        return self.request("GET", "/v1/bill/betting/providers")

    def betting_lookup(self, **query: Any) -> dict[str, Any]:
        return self.request("GET", "/v1/bill/betting/lookup", query=query)

    def vend_betting(self, payload: dict[str, Any], *, sub_account_id: str = "") -> dict[str, Any]:
        sub_account_id = self._sub_account_id(sub_account_id)
        path = f"/v1/bill/betting/{sub_account_id}" if sub_account_id else "/v1/bill/betting"
        return self.request("POST", path, body=payload)

    # Direct Debits
    def list_direct_debit_mandates(self, **query: Any) -> dict[str, Any]:
        return self.request("GET", "/v1/direct-debits/mandates", query=query)

    def update_direct_debit_status(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.request("PUT", "/v1/direct-debits/update-status", body=payload)

    def debit_mandate(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.request("POST", "/v1/direct-debits/debit-mandate", body=payload)

    def get_mandate_status(self, mandate_id: str) -> dict[str, Any]:
        return self.request("GET", "/v1/direct-debits/status", query={"mandateId": mandate_id})

    def get_mandate(self, mandate_id: str) -> dict[str, Any]:
        return self.request("GET", f"/v1/direct-debits/{mandate_id}")

    def create_mandate(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.request("POST", "/v1/direct-debits", body=payload)

    # Global payout / collections
    def authorize_global_transfer(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.request("POST", "/v1/global-payout/transfer/authorize", body=payload)

    def authorize_global_exchange(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.request("POST", "/v1/global-payout/exchange/authorize", body=payload)

    def convert_global_money(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.request("POST", "/v1/global-payout/money/convert", body=payload)

    def fetch_global_exchange_rates(self, **query: Any) -> dict[str, Any]:
        return self.request("GET", "/v1/global-payout/exchange-rates", query=query)

    def fetch_global_payout_transaction(self, transaction_id: str) -> dict[str, Any]:
        return self.request("GET", f"/v1/global-payout/transactions/{transaction_id}")

    def fetch_global_payment_methods(self, **query: Any) -> dict[str, Any]:
        return self.request("GET", "/v1/global-payout/payment-methods", query=query)

    def fetch_global_bank_providers(self, **query: Any) -> dict[str, Any]:
        return self.request("GET", "/v1/global-payout/bank/providers", query=query)

    def initiate_global_collection_inflow(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.request("POST", "/v1/global-collection/inflow/initiate", body=payload)

    def fetch_global_collection_transaction(self, transaction_id: str) -> dict[str, Any]:
        return self.request("GET", f"/v1/global-collection/transactions/{transaction_id}")

    def fetch_drc_inflow_providers(self, *, sandbox_path: bool = False) -> dict[str, Any]:
        path = "/v1/sandbox/global-collection/drc/inflow/providers" if sandbox_path else "/v1/global-collection/drc/inflow/providers"
        return self.request("GET", path)


def credentials_for_environment(environment) -> NombaCredentials:
    mode = environment.mode
    is_live = mode == "live"
    if is_live:
        base_url = getattr(settings, "NOMBA_LIVE_BASE_URL", "https://api.nomba.com")
        platform_account_id = getattr(settings, "NOMBA_PLATFORM_LIVE_ACCOUNT_ID", "")
        platform_client_id = getattr(settings, "NOMBA_PLATFORM_LIVE_CLIENT_ID", "")
        platform_client_secret = getattr(settings, "NOMBA_PLATFORM_LIVE_CLIENT_SECRET", "")
    else:
        base_url = getattr(settings, "NOMBA_SANDBOX_BASE_URL", "https://sandbox.nomba.com")
        platform_account_id = getattr(settings, "NOMBA_PLATFORM_TEST_ACCOUNT_ID", "")
        platform_client_id = getattr(settings, "NOMBA_PLATFORM_TEST_CLIENT_ID", "")
        platform_client_secret = getattr(settings, "NOMBA_PLATFORM_TEST_CLIENT_SECRET", "")

    byok = environment.nomba_integration_mode == "byok"
    account_id = environment.nomba_account_id or platform_account_id
    client_id = environment.nomba_client_id if byok else platform_client_id
    client_secret = environment.nomba_client_secret if byok else platform_client_secret
    return NombaCredentials(
        mode=mode,
        account_id=account_id,
        client_id=client_id,
        client_secret=client_secret,
        base_url=base_url,
        live_active=bool(environment.nomba_live_active),
    )
