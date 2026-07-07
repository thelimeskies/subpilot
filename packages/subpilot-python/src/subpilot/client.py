from __future__ import annotations

import json
import uuid
from typing import Any, Dict, Iterable, Mapping, MutableMapping, Optional
from urllib import error, parse, request

from .exceptions import SubPilotAPIError, SubPilotConnectionError

Json = Dict[str, Any]


class SubPilot:
    """SubPilot API client.

    The client intentionally uses Python's standard library so it can be copied
    into small backend services without pulling extra dependencies.
    """

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://api.subpilot.dev/api/v1",
        timeout: float = 20.0,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.customers = CustomersResource(self)
        self.payment_methods = PaymentMethodsResource(self)
        self.portal_sessions = PortalSessionsResource(self)
        self.portal = PortalResource(self)
        self.subscriptions = SubscriptionsResource(self)
        self.invoices = InvoicesResource(self)
        self.publishable_keys = PublishableKeysResource(self)

    def request(
        self,
        method: str,
        path: str,
        *,
        json_body: Optional[Mapping[str, Any]] = None,
        headers: Optional[Mapping[str, str]] = None,
        query: Optional[Mapping[str, Any]] = None,
        idempotency_key: Optional[str] = None,
        portal_token: Optional[str] = None,
        publishable_key: Optional[str] = None,
    ) -> Any:
        url = self._url(path, query=query)
        body = None
        request_headers: MutableMapping[str, str] = {
            "Accept": "application/json",
            "User-Agent": "subpilot-python/0.1.0",
        }
        if portal_token:
            request_headers["Authorization"] = f"Portal {portal_token}"
        else:
            request_headers["Authorization"] = f"Bearer {self.api_key}"
        if publishable_key:
            request_headers["X-SubPilot-Publishable-Key"] = publishable_key
        if idempotency_key:
            request_headers["Idempotency-Key"] = idempotency_key
        if json_body is not None:
            request_headers["Content-Type"] = "application/json"
            body = json.dumps(json_body).encode("utf-8")
        if headers:
            request_headers.update(headers)

        req = request.Request(url, data=body, headers=dict(request_headers), method=method.upper())
        try:
            with request.urlopen(req, timeout=self.timeout) as response:
                return _read_response(response.read(), response.headers.get("Content-Type", ""))
        except error.HTTPError as exc:
            payload = _read_response(exc.read(), exc.headers.get("Content-Type", ""))
            raise SubPilotAPIError(
                _error_message(payload, f"SubPilot API request failed ({exc.code})"),
                status_code=exc.code,
                payload=payload,
            ) from exc
        except error.URLError as exc:
            raise SubPilotConnectionError(str(exc.reason)) from exc

    def _url(self, path: str, *, query: Optional[Mapping[str, Any]] = None) -> str:
        normalized = path if path.startswith("/") else f"/{path}"
        url = f"{self.base_url}{normalized}"
        if not query:
            return url
        clean = {key: value for key, value in query.items() if value is not None}
        return f"{url}?{parse.urlencode(clean, doseq=True)}"


class Resource:
    def __init__(self, client: SubPilot) -> None:
        self.client = client

    @staticmethod
    def idempotency_key(prefix: str) -> str:
        return f"{prefix}-{uuid.uuid4()}"


class CustomersResource(Resource):
    def list(self, *, limit: Optional[int] = None) -> Any:
        return self.client.request("GET", "/customers/", query={"limit": limit})

    def retrieve(self, customer_id: str) -> Any:
        return self.client.request("GET", f"/customers/{customer_id}/")

    def create(
        self,
        *,
        email: str,
        name: str = "",
        phone: str = "",
        external_id: str = "",
        metadata: Optional[Mapping[str, Any]] = None,
        idempotency_key: Optional[str] = None,
    ) -> Any:
        return self.client.request(
            "POST",
            "/customers/",
            json_body={
                "email": email,
                "name": name,
                "phone": phone,
                "external_id": external_id,
                "metadata": dict(metadata or {}),
            },
            idempotency_key=idempotency_key,
        )

    def update(self, customer_id: str, *, idempotency_key: Optional[str] = None, **fields: Any) -> Any:
        return self.client.request(
            "PATCH",
            f"/customers/{customer_id}/",
            json_body={key: value for key, value in fields.items() if value is not None},
            idempotency_key=idempotency_key,
        )

    def archive(self, customer_id: str, *, idempotency_key: Optional[str] = None) -> Any:
        return self.client.request("POST", f"/customers/{customer_id}/archive/", idempotency_key=idempotency_key)

    def reactivate(self, customer_id: str, *, idempotency_key: Optional[str] = None) -> Any:
        return self.client.request("POST", f"/customers/{customer_id}/reactivate/", idempotency_key=idempotency_key)

    def merge(self, source_customer_id: str, *, target_customer_id: str, idempotency_key: Optional[str] = None) -> Any:
        return self.client.request(
            "POST",
            f"/customers/{source_customer_id}/merge/",
            json_body={"target_customer_id": target_customer_id},
            idempotency_key=idempotency_key,
        )


class PaymentMethodsResource(Resource):
    def list(self, *, customer_id: Optional[str] = None) -> Any:
        if customer_id:
            return self.client.request("GET", f"/customers/{customer_id}/payment-methods/")
        return self.client.request("GET", "/payment-methods/")

    def attach(
        self,
        customer_id: str,
        *,
        provider: str,
        token: str,
        brand: str = "",
        last4: str = "",
        exp_month: Optional[int] = None,
        exp_year: Optional[int] = None,
        fingerprint: str = "",
        set_default: bool = False,
        metadata: Optional[Mapping[str, Any]] = None,
        idempotency_key: Optional[str] = None,
    ) -> Any:
        return self.client.request(
            "POST",
            f"/customers/{customer_id}/payment-methods/",
            json_body={
                "provider": provider,
                "token": token,
                "brand": brand,
                "last4": last4,
                "exp_month": exp_month,
                "exp_year": exp_year,
                "fingerprint": fingerprint,
                "set_default": set_default,
                "metadata": dict(metadata or {}),
            },
            idempotency_key=idempotency_key,
        )

    def set_default(self, payment_method_id: str, *, idempotency_key: Optional[str] = None) -> Any:
        return self.client.request(
            "POST",
            f"/payment-methods/{payment_method_id}/set-default/",
            idempotency_key=idempotency_key,
        )


class PortalSessionsResource(Resource):
    def list(self, *, customer_id: Optional[str] = None) -> Any:
        if customer_id:
            return self.client.request("GET", f"/customers/{customer_id}/portal-sessions/")
        return self.client.request("GET", "/portal-sessions/")

    def create(
        self,
        *,
        customer_id: str,
        subscription_id: Optional[str] = None,
        invoice_id: Optional[str] = None,
        send_email: bool = False,
        allowed_actions: Optional[Iterable[str]] = None,
        return_url: str = "",
        ttl_minutes: Optional[int] = None,
        idempotency_key: Optional[str] = None,
    ) -> Any:
        body: Json = {
            "subscription_id": subscription_id,
            "invoice_id": invoice_id,
            "send_email": send_email,
            "allowed_actions": list(allowed_actions) if allowed_actions is not None else None,
            "return_url": return_url,
            "ttl_minutes": ttl_minutes,
        }
        return self.client.request(
            "POST",
            f"/customers/{customer_id}/portal-sessions/",
            json_body={key: value for key, value in body.items() if value not in (None, "")},
            idempotency_key=idempotency_key,
        )


class PortalResource(Resource):
    def context(self, *, token: str, publishable_key: Optional[str] = None) -> Any:
        return self.client.request(
            "GET",
            "/portal/context",
            portal_token=token,
            publishable_key=publishable_key,
        )

    def pay_invoice(self, invoice_id: str, *, token: str, publishable_key: Optional[str] = None) -> Any:
        return self.client.request(
            "POST",
            f"/portal/invoices/{invoice_id}/pay",
            portal_token=token,
            publishable_key=publishable_key,
        )


class SubscriptionsResource(Resource):
    def list(self, *, status: Optional[str] = None) -> Any:
        return self.client.request("GET", "/subscriptions/", query={"status": status})

    def create(self, payload: Mapping[str, Any], *, idempotency_key: Optional[str] = None) -> Any:
        return self.client.request("POST", "/subscriptions/", json_body=payload, idempotency_key=idempotency_key)


class InvoicesResource(Resource):
    def list(self) -> Any:
        return self.client.request("GET", "/invoices/")

    def retry(self, invoice_id: str, *, idempotency_key: Optional[str] = None) -> Any:
        return self.client.request("POST", f"/invoices/{invoice_id}/retry/", idempotency_key=idempotency_key)


class PublishableKeysResource(Resource):
    def list(self) -> Any:
        return self.client.request("GET", "/api-keys/publishable-key/")

    def rotate(self, mode: str) -> Any:
        return self.client.request("POST", "/api-keys/publishable-key/", json_body={"mode": mode})


def _read_response(raw: bytes, content_type: str) -> Any:
    if not raw:
        return None
    text = raw.decode("utf-8")
    if "application/json" not in content_type:
        return text
    return json.loads(text)


def _error_message(payload: Any, fallback: str) -> str:
    if isinstance(payload, dict):
        if payload.get("reason"):
            return str(payload["reason"])
        if payload.get("detail"):
            return str(payload["detail"])
        errors = payload.get("errors")
        if isinstance(errors, list) and errors:
            detail = errors[0].get("detail") if isinstance(errors[0], dict) else None
            if detail:
                return str(detail)
    return fallback
