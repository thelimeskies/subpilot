"""Service: create_portal_session.

Returns a tuple ``(session, plaintext_token)``. Only the SHA-256 hash is
persisted; the plaintext token is shown to the caller exactly once and then
forgotten.
"""
from __future__ import annotations

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.audit.services.log_event import log_event
from apps.common.crypto import generate_token, hash_secret
from apps.common.email import (
    format_email_datetime,
    frontend_url,
    merchant_email_context,
    send_templated_email,
)
from apps.common.exceptions import ServiceError

from ..models import Customer, PortalSession

DEFAULT_TTL = timedelta(hours=24)
DEFAULT_ALLOWED_ACTIONS = (
    "view_subscriptions",
    "update_payment_method",
    "view_invoices",
    "pay_invoice",
)


def portal_session_url(token: str) -> str:
    return f"{frontend_url('customer')}/session/{token}"


def send_portal_session_email(
    *,
    customer: Customer,
    session: PortalSession,
    token: str,
    actor_user=None,
    request=None,
) -> dict:
    url = portal_session_url(token)
    recipient_name = customer.name or customer.email
    subject = f"Manage your {customer.merchant.name} billing"
    send_templated_email(
        to=customer.email,
        subject=subject,
        template="portal_session",
        context=merchant_email_context(
            customer.merchant,
            email_label="Customer portal",
            recipient_name=recipient_name,
            portal_link=url,
            expires_at=format_email_datetime(session.expires_at),
        ),
    )
    log_event(
        action="customers.portal_session_emailed",
        actor_user=actor_user,
        merchant=customer.merchant,
        environment=customer.environment,
        target_type="portal_session",
        target_id=str(session.id),
        metadata={
            "customer_id": str(customer.id),
            "recipient": customer.email,
            "expires_at": session.expires_at.isoformat(),
        },
        request=request,
    )
    return {"ok": True, "recipient": customer.email, "url": url}


def send_customer_blocked_email(
    *,
    customer: Customer,
    paused_subscription_count: int,
    actor_user=None,
    request=None,
) -> dict:
    recipient_name = customer.name or customer.email
    plural = "" if paused_subscription_count == 1 else "s"
    subject = f"Your {customer.merchant.name} billing has been paused"
    send_templated_email(
        to=customer.email,
        subject=subject,
        template="customer_blocked",
        context=merchant_email_context(
            customer.merchant,
            email_label="Billing status",
            recipient_name=recipient_name,
            paused_subscription_count=paused_subscription_count,
            subscription_plural=plural,
        ),
    )
    log_event(
        action="customers.customer_blocked_emailed",
        actor_user=actor_user,
        merchant=customer.merchant,
        environment=customer.environment,
        target_type="customer",
        target_id=str(customer.id),
        metadata={
            "recipient": customer.email,
            "paused_subscriptions": paused_subscription_count,
        },
        request=request,
    )
    return {
        "ok": True,
        "recipient": customer.email,
        "paused_subscriptions": paused_subscription_count,
    }


@transaction.atomic
def create_portal_session(
    *,
    customer: Customer,
    subscription=None,
    invoice=None,
    allowed_actions: list[str] | None = None,
    return_url: str = "",
    ttl: timedelta = DEFAULT_TTL,
    actor_user=None,
    request=None,
) -> tuple[PortalSession, str]:
    if subscription is not None and subscription.customer_id != customer.id:
        raise ServiceError("Subscription does not belong to this customer.")
    if invoice is not None and invoice.customer_id != customer.id:
        raise ServiceError("Invoice does not belong to this customer.")

    plaintext = generate_token(prefix="portal")
    session = PortalSession.objects.create(
        merchant=customer.merchant,
        environment=customer.environment,
        customer=customer,
        subscription=subscription,
        invoice=invoice,
        token_hash=hash_secret(plaintext),
        allowed_actions=list(allowed_actions or DEFAULT_ALLOWED_ACTIONS),
        return_url=return_url,
        expires_at=timezone.now() + ttl,
    )
    log_event(
        action="customers.portal_session_created",
        actor_user=actor_user,
        merchant=customer.merchant,
        environment=customer.environment,
        target_type="portal_session",
        target_id=str(session.id),
        metadata={
            "customer_id": str(customer.id),
            "expires_at": session.expires_at.isoformat(),
        },
        request=request,
    )
    return session, plaintext
