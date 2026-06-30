"""Webhook endpoint CRUD services."""
from __future__ import annotations

import secrets
from typing import Iterable

from apps.audit.services.log_event import log_event
from apps.common.db import atomic_with_retry

from ..models import WebhookEndpoint


def _generate_secret() -> str:
    return f"whsec_{secrets.token_urlsafe(32)}"


@atomic_with_retry
def create_webhook_endpoint(
    *,
    merchant,
    environment,
    url: str,
    description: str = "",
    event_filters: Iterable[str] | None = None,
    enabled: bool = True,
    secret: str | None = None,
    actor_user=None,
    request=None,
) -> tuple[WebhookEndpoint, str]:
    """Create a webhook endpoint. Returns ``(endpoint, plaintext_secret)``.

    The plaintext secret is only returned to the caller once and is then
    encrypted at rest via the ``WebhookEndpoint.secret`` setter.
    """
    plaintext = secret or _generate_secret()
    endpoint = WebhookEndpoint(
        merchant=merchant,
        environment=environment,
        url=url,
        description=description,
        event_filters=list(event_filters or []),
        enabled=enabled,
    )
    endpoint.secret = plaintext  # property encrypts
    endpoint.save()
    log_event(
        action="events.endpoint_created",
        actor_user=actor_user,
        merchant=merchant,
        environment=environment,
        target_type="WebhookEndpoint",
        target_id=str(endpoint.id),
        metadata={"url": url, "filters": list(event_filters or [])},
        request=request,
    )
    return endpoint, plaintext


@atomic_with_retry
def update_webhook_endpoint(
    *, endpoint: WebhookEndpoint, actor_user=None, request=None, **patch
) -> WebhookEndpoint:
    """Patch-style update for editable fields."""
    allowed = {"url", "description", "event_filters", "enabled"}
    changed: dict[str, object] = {}
    for field, value in patch.items():
        if field not in allowed or value is None:
            continue
        setattr(endpoint, field, value)
        changed[field] = value
    if changed:
        endpoint.save(update_fields=[*changed.keys(), "updated_at"])
        log_event(
            action="events.endpoint_updated",
            actor_user=actor_user,
            merchant=endpoint.merchant,
            environment=endpoint.environment,
            target_type="WebhookEndpoint",
            target_id=str(endpoint.id),
            metadata={"changed": list(changed.keys())},
            request=request,
        )
    return endpoint


@atomic_with_retry
def rotate_webhook_secret(
    *, endpoint: WebhookEndpoint, actor_user=None, request=None
) -> str:
    """Rotate the endpoint secret and return the new plaintext value."""
    plaintext = _generate_secret()
    endpoint.secret = plaintext
    endpoint.save(update_fields=["secret_encrypted", "updated_at"])
    log_event(
        action="events.endpoint_secret_rotated",
        actor_user=actor_user,
        merchant=endpoint.merchant,
        environment=endpoint.environment,
        target_type="WebhookEndpoint",
        target_id=str(endpoint.id),
        metadata={},
        request=request,
    )
    return plaintext
