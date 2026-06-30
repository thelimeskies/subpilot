"""Service entry-point for writing audit log rows.

Always call :func:`log_event` instead of instantiating ``AuditLog`` directly so
we have one chokepoint for actor/tenant resolution and metadata sanitation.
"""
from __future__ import annotations

from typing import Any

from django.http import HttpRequest

from apps.audit.models import AuditLog


def log_event(
    *,
    action: str,
    actor_user=None,
    actor_label: str = "",
    actor_role: str = "",
    merchant=None,
    environment=None,
    target_type: str = "",
    target_id: str = "",
    metadata: dict[str, Any] | None = None,
    request: HttpRequest | None = None,
) -> AuditLog:
    """Persist an audit-log row. Returns the saved object."""
    request_id = ""
    ip = None
    ua = ""
    if request is not None:
        request_id = getattr(request, "request_id", "") or ""
        ip = _client_ip(request)
        ua = request.META.get("HTTP_USER_AGENT", "")[:512]

    if actor_user is not None and not actor_label:
        actor_label = getattr(actor_user, "display_name", "") or actor_user.email

    return AuditLog.objects.create(
        actor_user=actor_user,
        actor_label=actor_label,
        actor_role=actor_role,
        merchant=merchant,
        environment=environment,
        action=action,
        target_type=target_type,
        target_id=target_id,
        metadata=metadata or {},
        request_id=request_id,
        ip_address=ip,
        user_agent=ua,
    )


def _client_ip(request: HttpRequest) -> str | None:
    fwd = request.META.get("HTTP_X_FORWARDED_FOR")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")
