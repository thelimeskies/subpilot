from datetime import timedelta

import pytest
from django.core import mail
from django.test import override_settings
from django.utils import timezone

from apps.accounts.models import Environment, Merchant
from apps.customers.models import Customer, PortalSession
from apps.invoices.models import Invoice
from apps.invoices.services.delivery import send_invoice_reminder

pytestmark = pytest.mark.django_db


def _workspace():
    merchant = Merchant.objects.create(name="Acme Learning Hub", slug="acme-learning")
    environment = Environment.objects.create(merchant=merchant, mode=Environment.Mode.TEST)
    customer = Customer.objects.create(
        merchant=merchant,
        environment=environment,
        email="asikhalaye@example.test",
        name="Asikhalaye Samuel",
    )
    invoice = Invoice.objects.create(
        merchant=merchant,
        environment=environment,
        customer=customer,
        number="INV-202607-92326489-000001",
        status=Invoice.Status.OPEN,
        subtotal_minor=1_000_000,
        total_minor=1_000_000,
        amount_due_minor=1_000_000,
        currency="NGN",
        due_at=timezone.now() + timedelta(days=14),
    )
    return invoice


@override_settings(SUBPILOT_FRONTEND_URLS={"customer": "https://portal.example"})
def test_invoice_reminder_generates_portal_payment_link_when_invoice_has_no_hosted_url():
    invoice = _workspace()

    result = send_invoice_reminder(
        invoice=invoice,
        channel="email",
        message="Your invoice is due soon.",
    )

    assert result["sent"] is True
    assert result["recipient"] == "asikhalaye@example.test"
    assert PortalSession.objects.filter(invoice=invoice).count() == 1
    assert len(mail.outbox) == 1
    email = mail.outbox[0]
    assert "Pay invoice:" in email.body
    assert "https://portal.example/session/portal_" in email.body
    html = email.alternatives[0][0]
    assert "Pay invoice" in html
    assert "https://portal.example/session/portal_" in html
