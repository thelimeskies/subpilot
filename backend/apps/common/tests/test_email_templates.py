import pytest
from django.core import mail
from django.template.loader import render_to_string

from apps.common.email import email_context, send_templated_email

EMAIL_CASES = [
    (
        "verify",
        {"verify_link": "https://app.example/verify?token=verify_123"},
        "Verify your email",
    ),
    (
        "reset",
        {"reset_link": "https://app.example/reset?token=reset_123"},
        "Reset your password",
    ),
    (
        "invite",
        {"org_name": "Acme Fitness", "invite_link": "https://app.example/invite/123"},
        "Join Acme Fitness",
    ),
    (
        "welcome",
        {"org_name": "Acme Fitness", "dashboard_link": "https://app.example"},
        "Acme Fitness is ready",
    ),
    (
        "portal_session",
        {
            "merchant_name": "Acme Fitness",
            "recipient_name": "Ada",
            "portal_link": "https://portal.example/session/portal_123",
            "expires_at": "Jun 20, 2026 4:00 PM UTC",
        },
        "Manage your Acme Fitness billing",
    ),
    (
        "customer_blocked",
        {
            "merchant_name": "Acme Fitness",
            "recipient_name": "Ada",
            "paused_subscription_count": 2,
            "subscription_plural": "s",
        },
        "billing profile has been paused",
    ),
    (
        "invoice_reminder",
        {
            "merchant_name": "Acme Fitness",
            "recipient_name": "Ada",
            "invoice_number": "INV-001",
            "amount_due": "NGN 12,500.00",
            "due_at": "Jun 20, 2026",
            "hosted_payment_url": "https://pay.example/inv",
            "message": "Please complete payment.",
        },
        "Invoice INV-001",
    ),
    (
        "payment_receipt",
        {
            "merchant_name": "Acme Fitness",
            "recipient_name": "Ada",
            "invoice_number": "INV-001",
            "amount_paid": "NGN 12,500.00",
            "payment_method_label": "VISA ending 4242",
            "processor_reference": "nomba_ref_123",
        },
        "payment was successful",
    ),
    (
        "payment_failed",
        {
            "merchant_name": "Acme Fitness",
            "recipient_name": "Ada",
            "invoice_number": "INV-001",
            "amount_due": "NGN 12,500.00",
            "failure_message": "Insufficient funds",
            "recovery_link": "https://portal.example/session/portal_123",
            "next_retry_at": "Jun 21, 2026 9:00 AM UTC",
        },
        "We could not collect",
    ),
    (
        "dunning_recovery",
        {
            "merchant_name": "Acme Fitness",
            "recipient_name": "Ada",
            "invoice_number": "INV-001",
            "amount_due": "NGN 12,500.00",
            "recovery_link": "https://portal.example/session/portal_123",
            "next_retry_at": "Jun 21, 2026 9:00 AM UTC",
            "expires_at": "Jun 22, 2026 9:00 AM UTC",
        },
        "Keep your Acme Fitness subscription active",
    ),
    (
        "subscription_canceled",
        {
            "merchant_name": "Acme Fitness",
            "recipient_name": "Ada",
            "plan_name": "Pro",
            "canceled_at": "Jun 20, 2026",
            "portal_link": "https://portal.example/session/portal_123",
        },
        "subscription has been canceled",
    ),
]


@pytest.mark.parametrize(("template", "context", "expected"), EMAIL_CASES)
def test_email_templates_render_html_and_text(template, context, expected):
    payload = email_context(**context)

    html = render_to_string(f"email/{template}.html", payload)
    text = render_to_string(f"email/{template}.txt", payload)

    assert expected in html
    assert text.strip()
    assert "SubPilot" in html


def test_send_templated_email_sends_multipart_message():
    sent = send_templated_email(
        to="owner@example.test",
        subject="Verify your SubPilot email",
        template="verify",
        context={"verify_link": "https://app.example/verify?token=verify_123"},
    )

    assert sent.to == "owner@example.test"
    assert len(mail.outbox) == 1
    assert mail.outbox[0].alternatives[0][1] == "text/html"
