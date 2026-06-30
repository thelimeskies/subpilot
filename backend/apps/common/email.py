"""Shared helpers for branded product emails."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.formats import date_format


@dataclass(frozen=True)
class SentEmail:
    to: str
    subject: str
    template: str


def support_email() -> str:
    return getattr(settings, "SUBPILOT_SUPPORT_EMAIL", "support@subpilot.test")


def frontend_url(kind: str = "merchant") -> str:
    urls = getattr(settings, "SUBPILOT_FRONTEND_URLS", {}) or {}
    fallback = "http://localhost:5173" if kind == "merchant" else "http://localhost:5174"
    return urls.get(kind, fallback).rstrip("/")


def format_email_date(value) -> str:
    if not value:
        return ""
    return date_format(timezone.localtime(value), "M j, Y")


def format_email_datetime(value) -> str:
    if not value:
        return ""
    return date_format(timezone.localtime(value), "M j, Y P T")


def email_context(**context: Any) -> dict[str, Any]:
    now = timezone.now()
    return {
        "product_name": "SubPilot",
        "support_email": support_email(),
        "current_year": now.year,
        **context,
    }


def merchant_email_context(merchant, **context: Any) -> dict[str, Any]:
    metadata = getattr(merchant, "metadata", None) or {}
    settings_meta = metadata.get("settings", {}) if isinstance(metadata, dict) else {}
    branding = settings_meta.get("branding", {}) if isinstance(settings_meta, dict) else {}
    org_meta = metadata.get("org", {}) if isinstance(metadata, dict) else {}
    merchant_name = (
        branding.get("trading_name")
        or org_meta.get("trading_name")
        or getattr(merchant, "name", "")
        or "your merchant"
    )
    primary_color = branding.get("primary_color") or "#14B8A6"
    logo_url = branding.get("logo_url") or ""
    return email_context(
        merchant=merchant,
        merchant_name=merchant_name,
        primary_color=primary_color,
        logo_url=logo_url,
        **context,
    )


def send_templated_email(
    *,
    to: str,
    subject: str,
    template: str,
    context: dict[str, Any] | None = None,
    from_email: str | None = None,
) -> SentEmail:
    payload = email_context(**(context or {}))
    text = render_to_string(f"email/{template}.txt", payload)
    html = render_to_string(f"email/{template}.html", payload)
    msg = EmailMultiAlternatives(
        subject,
        text,
        from_email or settings.DEFAULT_FROM_EMAIL,
        [to],
    )
    msg.attach_alternative(html, "text/html")
    msg.send(fail_silently=False)
    return SentEmail(to=to, subject=subject, template=template)
