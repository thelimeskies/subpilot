"""HTTP middleware: request id + idempotency replay."""
from __future__ import annotations

import json
import logging
import uuid
from typing import Callable

from django.http import HttpRequest, HttpResponse, JsonResponse

from apps.common import idempotency

log = logging.getLogger("subpilot.middleware")

_MUTATION_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
_HEADER = "HTTP_IDEMPOTENCY_KEY"


class RequestIdMiddleware:
    """Attach a stable ``X-Request-ID`` to every request/response for log correlation."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        request_id = request.META.get("HTTP_X_REQUEST_ID") or uuid.uuid4().hex
        request.request_id = request_id  # type: ignore[attr-defined]
        response = self.get_response(request)
        response["X-Request-ID"] = request_id
        return response


class IdempotencyMiddleware:
    """Replay cached responses for repeated POST/PUT/PATCH/DELETE with the same Idempotency-Key.

    Scoped per-merchant (when authenticated) and per (method, path). Only applies
    to ``/api/`` paths.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if not self._is_eligible(request):
            return self.get_response(request)

        idem_key = request.META.get(_HEADER, "").strip()
        if not idem_key:
            return self.get_response(request)

        merchant_id = self._merchant_id(request)
        cached = idempotency.http_get(merchant_id, idem_key, request.method, request.path)
        if cached:
            log.info("idempotency.replay key=%s method=%s path=%s", idem_key, request.method, request.path)
            try:
                payload = json.loads(cached["body_b64"])
                response = JsonResponse(payload, status=cached["status_code"], safe=False)
            except (ValueError, KeyError):
                # Body wasn't JSON; replay raw.
                response = HttpResponse(
                    cached.get("body_b64", ""),
                    status=cached.get("status_code", 200),
                    content_type=cached.get("content_type", "application/json"),
                )
            response["Idempotency-Replayed"] = "true"
            return response

        response = self.get_response(request)

        # Only cache successful or client-error responses (don't cache 5xx).
        if 200 <= response.status_code < 500:
            idempotency.http_store(
                merchant_id,
                idem_key,
                request.method,
                request.path,
                status_code=response.status_code,
                body=response.content,
                content_type=response.get("Content-Type", "application/json"),
            )
        return response

    @staticmethod
    def _is_eligible(request: HttpRequest) -> bool:
        return request.method in _MUTATION_METHODS and request.path.startswith("/api/")

    @staticmethod
    def _merchant_id(request: HttpRequest) -> str | None:
        merchant = getattr(request, "merchant", None)
        return str(merchant.id) if merchant is not None else None
