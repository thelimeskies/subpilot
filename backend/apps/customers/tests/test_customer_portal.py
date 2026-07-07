import json
from datetime import timedelta

from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Environment, Merchant, Role, TeamMember, User
from apps.catalog.models import Plan, PriceVersion, Product
from apps.customers.models import Customer, PaymentMethod
from apps.invoices.models import Invoice
from apps.payments.models import PaymentAttempt
from apps.subscriptions.models import Subscription, SubscriptionItem

PASSWORD = "Subpilot1!"


class _NombaResponse:
    def __init__(self, payload: dict):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(self.payload).encode()


def _setup_workspace(*, allow_cancel: bool = True):
    merchant = Merchant.objects.create(
        name="Portal Co",
        slug="portal-co",
        default_currency="NGN",
        metadata={
            "org": {"trading_name": "Portal Co", "portal_subdomain": "portal-co"},
            "settings": {
                "branding": {
                    "primary_color": "#125C4E",
                    "logo_url": "https://cdn.example/logo.png",
                    "portal_subdomain": "portal-co",
                },
                "portal": {
                    "allow_cancel": allow_cancel,
                    "allow_pause": True,
                    "allow_change_plan": False,
                    "success_url": "https://merchant.example/success",
                    "cancel_url": "https://merchant.example/cancel",
                },
            },
        },
    )
    environment = Environment.objects.create(merchant=merchant, mode=Environment.Mode.TEST)
    user = User.objects.create_user(
        email="owner@portal-co.test",
        password=PASSWORD,
        display_name="Owner",
        email_verified=True,
        onboarding_complete=True,
    )
    TeamMember.objects.create(merchant=merchant, user=user, role=Role.OWNER)
    customer = Customer.objects.create(
        merchant=merchant,
        environment=environment,
        email="customer@example.test",
        name="Customer One",
    )
    method = PaymentMethod.objects.create(
        merchant=merchant,
        environment=environment,
        customer=customer,
        provider=PaymentMethod.Provider.MOCK,
        brand="Visa",
        last4="4242",
        exp_month=4,
        exp_year=2028,
        is_default=True,
    )
    method.token = "tok_test_4242"
    method.save(update_fields=["token_encrypted"])
    product = Product.objects.create(merchant=merchant, environment=environment, name="Membership")
    plan = Plan.objects.create(
        merchant=merchant,
        environment=environment,
        product=product,
        name="Pro",
        status=Plan.Status.ACTIVE,
    )
    price = PriceVersion.objects.create(
        plan=plan,
        amount_minor=1500000,
        currency="NGN",
        interval_unit=PriceVersion.IntervalUnit.MONTH,
        interval_count=1,
        active_from=timezone.now(),
    )
    subscription = Subscription.objects.create(
        merchant=merchant,
        environment=environment,
        customer=customer,
        plan=plan,
        status=Subscription.Status.ACTIVE,
        current_period_end=timezone.now() + timezone.timedelta(days=30),
        default_payment_method=method,
    )
    SubscriptionItem.objects.create(subscription=subscription, price_version=price, quantity=1)
    Invoice.objects.create(
        merchant=merchant,
        environment=environment,
        customer=customer,
        subscription=subscription,
        number="INV-PORTAL-001",
        status=Invoice.Status.OPEN,
        subtotal_minor=1500000,
        total_minor=1500000,
        amount_due_minor=1500000,
        currency="NGN",
        due_at=timezone.now() + timezone.timedelta(days=3),
    )
    return user, customer


def _signed_in_client(user):
    client = APIClient()
    response = client.post(
        "/api/v1/auth/sign-in",
        data={"email": user.email, "password": PASSWORD},
        format="json",
    )
    assert response.status_code == 200, response.content
    return client


def _portal_token(client, customer, actions=None):
    response = client.post(
        f"/api/v1/customers/{customer.id}/portal-sessions/",
        data={
            "allowed_actions": actions
            or ["view_subscriptions", "view_invoices", "update_payment_method", "pay_invoice", "cancel_subscription"],
            "ttl_minutes": 60,
        },
        format="json",
    )
    assert response.status_code == 201, response.content
    return response.json()["token"], response.json()["session"]


def test_portal_context_returns_branding_and_payment_methods():
    user, customer = _setup_workspace()
    client = _signed_in_client(user)
    token, _session = _portal_token(client, customer)

    response = APIClient().get("/api/v1/portal/context", HTTP_AUTHORIZATION=f"Portal {token}")

    assert response.status_code == 200, response.content
    body = response.json()
    assert body["merchant"]["name"] == "Portal Co"
    assert body["merchant"]["brand_color"] == "#125C4E"
    assert body["merchant"]["logo_url"] == "https://cdn.example/logo.png"
    assert body["payment_methods"][0]["last4"] == "4242"
    assert "cancel_subscription" in body["allowed_actions"]


def test_portal_session_creation_removes_cancel_when_merchant_disables_it():
    user, customer = _setup_workspace(allow_cancel=False)
    client = _signed_in_client(user)

    _token, session = _portal_token(client, customer)

    assert "cancel_subscription" not in session["allowed_actions"]


def test_portal_context_checks_publishable_key_when_present():
    user, customer = _setup_workspace()
    customer.environment.publishable_key = "pk_test_matching"
    customer.environment.save(update_fields=["publishable_key"])
    client = _signed_in_client(user)
    token, _session = _portal_token(client, customer)

    valid = APIClient().get(
        "/api/v1/portal/context",
        HTTP_AUTHORIZATION=f"Portal {token}",
        HTTP_X_SUBPILOT_PUBLISHABLE_KEY="pk_test_matching",
    )
    invalid = APIClient().get(
        "/api/v1/portal/context",
        HTTP_AUTHORIZATION=f"Portal {token}",
        HTTP_X_SUBPILOT_PUBLISHABLE_KEY="pk_test_wrong",
    )

    assert valid.status_code == 200, valid.content
    assert invalid.status_code == 401, invalid.content


@override_settings(NOMBA_CHECKOUT_CALLBACK_URL="https://example.test/nomba/callback")
def test_portal_payment_method_checkout_starts_nomba_tokenized_checkout(monkeypatch):
    user, customer = _setup_workspace()
    environment = customer.environment
    environment.nomba_integration_mode = Environment.NombaIntegrationMode.BYOK
    environment.nomba_account_id = "acct_123"
    environment.nomba_client_id = "client_123"
    environment.nomba_client_secret = "secret_123"
    environment.nomba_access_token = "access-token"
    environment.nomba_token_expires_at = timezone.now() + timedelta(hours=1)
    environment.save(
        update_fields=[
            "nomba_integration_mode",
            "nomba_account_id",
            "nomba_client_id",
            "nomba_client_secret_encrypted",
            "nomba_access_token_encrypted",
            "nomba_token_expires_at",
            "updated_at",
        ]
    )
    invoice = customer.invoices.get(number="INV-PORTAL-001")
    client = _signed_in_client(user)
    token, _session = _portal_token(
        client,
        customer,
        actions=["view_subscriptions", "view_invoices", "update_payment_method"],
    )
    checkout_link = f"https://checkout.nomba.test/order/123?token={'x' * 620}"
    seen = {}

    def fake_urlopen(req, timeout):
        seen["method"] = req.get_method()
        seen["url"] = req.full_url
        seen["body"] = json.loads(req.data.decode())
        return _NombaResponse(
            {
                "code": "00",
                "description": "created",
                "data": {
                    "checkoutLink": checkout_link,
                    "orderReference": "checkout-ref-123",
                },
            }
        )

    monkeypatch.setattr("apps.payments.integrations.nomba.client.request.urlopen", fake_urlopen)

    response = APIClient().post(
        "/api/v1/portal/payment-methods/checkout",
        data={"invoice_id": str(invoice.id)},
        format="json",
        HTTP_AUTHORIZATION=f"Portal {token}",
    )

    assert response.status_code == 201, response.content
    assert response.json() == {
        "checkout_url": checkout_link,
        "invoice_id": str(invoice.id),
        "order_reference": "checkout-ref-123",
        "processor": "nomba",
    }
    assert seen["method"] == "POST"
    assert seen["url"] == "https://sandbox.nomba.com/v1/checkout/order"
    assert seen["body"]["tokenizeCard"] is True
    assert seen["body"]["order"]["allowedPaymentMethods"] == ["Card"]
    assert seen["body"]["order"]["callbackUrl"] == "https://example.test/nomba/callback"
    assert seen["body"]["order"]["orderMetaData"]["invoice_id"] == str(invoice.id)
    attempt = PaymentAttempt.objects.get(invoice=invoice)
    assert attempt.status == PaymentAttempt.Status.PENDING
    assert attempt.amount_minor == invoice.amount_due_minor
    assert attempt.processor_reference == "checkout-ref-123"
    assert attempt.idempotency_key == f"checkout:{invoice.id}"
    assert seen["body"]["order"]["orderMetaData"]["payment_attempt_id"] == str(attempt.id)
    assert "cardNumber" not in json.dumps(seen["body"])
    assert "cvc" not in json.dumps(seen["body"]).lower()
    invoice.refresh_from_db()
    assert invoice.hosted_payment_url == checkout_link
    assert invoice.metadata["nomba_checkout_id"] == "123"
    assert attempt.metadata["nomba_checkout_id"] == "123"
    assert len(invoice.hosted_payment_url) > 500


def test_portal_rejects_direct_nomba_card_token_attachment():
    user, customer = _setup_workspace()
    client = _signed_in_client(user)
    token, _session = _portal_token(
        client,
        customer,
        actions=["view_subscriptions", "view_invoices", "update_payment_method"],
    )

    response = APIClient().post(
        "/api/v1/portal/payment-methods",
        data={"provider": "nomba", "token": "tok_from_browser"},
        format="json",
        HTTP_AUTHORIZATION=f"Portal {token}",
    )

    assert response.status_code == 400, response.content
    assert response.json()["reason"] == "Use the hosted Nomba checkout endpoint to attach Nomba cards."


def test_portal_checkout_records_failed_attempt_when_nomba_returns_no_url(monkeypatch):
    user, customer = _setup_workspace()
    environment = customer.environment
    environment.nomba_integration_mode = Environment.NombaIntegrationMode.BYOK
    environment.nomba_account_id = "acct_123"
    environment.nomba_client_id = "client_123"
    environment.nomba_client_secret = "secret_123"
    environment.nomba_access_token = "access-token"
    environment.nomba_token_expires_at = timezone.now() + timedelta(hours=1)
    environment.save(
        update_fields=[
            "nomba_integration_mode",
            "nomba_account_id",
            "nomba_client_id",
            "nomba_client_secret_encrypted",
            "nomba_access_token_encrypted",
            "nomba_token_expires_at",
            "updated_at",
        ]
    )
    invoice = customer.invoices.get(number="INV-PORTAL-001")
    client = _signed_in_client(user)
    token, _session = _portal_token(
        client,
        customer,
        actions=["view_subscriptions", "view_invoices", "update_payment_method"],
    )

    def fake_urlopen(req, timeout):
        return _NombaResponse({"code": "400", "description": "Bad checkout request", "data": {}})

    monkeypatch.setattr("apps.payments.integrations.nomba.client.request.urlopen", fake_urlopen)

    response = APIClient().post(
        "/api/v1/portal/payment-methods/checkout",
        data={"invoice_id": str(invoice.id)},
        format="json",
        HTTP_AUTHORIZATION=f"Portal {token}",
    )

    assert response.status_code == 502, response.content
    attempt = PaymentAttempt.objects.get(invoice=invoice)
    assert attempt.status == PaymentAttempt.Status.FAILED
    assert attempt.failure_code == "400"
    assert attempt.failure_message == "Bad checkout request"


def test_portal_checkout_confirm_polls_nomba_and_saves_tokenized_card(monkeypatch):
    user, customer = _setup_workspace()
    environment = customer.environment
    environment.nomba_integration_mode = Environment.NombaIntegrationMode.BYOK
    environment.nomba_account_id = "acct_123"
    environment.nomba_client_id = "client_123"
    environment.nomba_client_secret = "secret_123"
    environment.nomba_access_token = "access-token"
    environment.nomba_token_expires_at = timezone.now() + timedelta(hours=1)
    environment.save(
        update_fields=[
            "nomba_integration_mode",
            "nomba_account_id",
            "nomba_client_id",
            "nomba_client_secret_encrypted",
            "nomba_access_token_encrypted",
            "nomba_token_expires_at",
            "updated_at",
        ]
    )
    invoice = customer.invoices.get(number="INV-PORTAL-001")
    order_reference = f"checkout-{invoice.id}"
    invoice.metadata = {"nomba_checkout_order_reference": order_reference}
    invoice.save(update_fields=["metadata", "updated_at"])
    client = _signed_in_client(user)
    token, _session = _portal_token(
        client,
        customer,
        actions=["view_subscriptions", "view_invoices", "update_payment_method"],
    )
    seen = {}

    def fake_urlopen(req, timeout):
        seen["method"] = req.get_method()
        seen["url"] = req.full_url
        return _NombaResponse(
            {
                "code": "00",
                "description": "checkout order fetched",
                "data": {
                    "orderReference": order_reference,
                    "amount": "15000.00",
                    "currency": "NGN",
                    "orderMetaData": {
                        "invoice_id": str(invoice.id),
                        "customer_id": str(customer.id),
                        "subscription_id": str(invoice.subscription_id),
                    },
                    "transaction": {
                        "transactionId": "txn_poll_123",
                        "transactionAmount": "15000.00",
                        "responseCode": "00",
                        "responseMessage": "Successful",
                    },
                    "tokenizedCardData": {
                        "tokenKey": "tok_nomba_poll_saved_card",
                        "cardType": "Visa",
                        "cardPan": "411111******4242",
                        "tokenExpirationDate": "12/30",
                    },
                },
            }
        )

    monkeypatch.setattr("apps.payments.integrations.nomba.client.request.urlopen", fake_urlopen)

    response = APIClient().post(
        "/api/v1/portal/payment-methods/checkout/confirm",
        data={"order_reference": order_reference, "invoice_id": str(invoice.id)},
        format="json",
        HTTP_AUTHORIZATION=f"Portal {token}",
    )

    assert response.status_code == 200, response.content
    assert response.json()["confirmed"] is True
    assert response.json()["invoice_paid"] is True
    assert response.json()["payment_method_attached"] is True
    assert seen["method"] == "GET"
    assert seen["url"] == f"https://sandbox.nomba.com/v1/checkout/order/{order_reference}"
    payment_method = PaymentMethod.objects.get(
        customer=customer,
        provider=PaymentMethod.Provider.NOMBA,
    )
    assert payment_method.token == "tok_nomba_poll_saved_card"
    assert payment_method.is_default is True
    invoice.refresh_from_db()
    assert invoice.status == Invoice.Status.PAID
    attempt = PaymentAttempt.objects.get(invoice=invoice)
    assert attempt.status == PaymentAttempt.Status.SUCCEEDED
    assert attempt.processor_reference == "txn_poll_123"
    assert attempt.amount_minor == 1_500_000


def test_portal_checkout_confirm_polls_with_checkout_id_from_hosted_url(monkeypatch):
    user, customer = _setup_workspace()
    environment = customer.environment
    environment.nomba_integration_mode = Environment.NombaIntegrationMode.BYOK
    environment.nomba_account_id = "acct_123"
    environment.nomba_client_id = "client_123"
    environment.nomba_client_secret = "secret_123"
    environment.nomba_access_token = "access-token"
    environment.nomba_token_expires_at = timezone.now() + timedelta(hours=1)
    environment.save(
        update_fields=[
            "nomba_integration_mode",
            "nomba_account_id",
            "nomba_client_id",
            "nomba_client_secret_encrypted",
            "nomba_access_token_encrypted",
            "nomba_token_expires_at",
            "updated_at",
        ]
    )
    invoice = customer.invoices.get(number="INV-PORTAL-001")
    checkout_id = "QMojVVIswaIri_iA6YONMcbjLOBR32-CvIArUO_lT9Szr_BGxp65Mgvx"
    nomba_reference = "358ce347-db87-468e-ad19-1c8fee5220bb"
    invoice.hosted_payment_url = f"https://pay.nomba.com/sandbox/{checkout_id}"
    invoice.metadata = {"nomba_checkout_order_reference": nomba_reference}
    invoice.save(update_fields=["hosted_payment_url", "metadata", "updated_at"])
    client = _signed_in_client(user)
    token, _session = _portal_token(
        client,
        customer,
        actions=["view_subscriptions", "view_invoices", "update_payment_method"],
    )
    seen = []

    def fake_urlopen(req, timeout):
        seen.append(req.full_url)
        assert req.full_url.endswith(f"/v1/checkout/order/{checkout_id}")
        return _NombaResponse(
            {
                "code": "00",
                "description": "checkout order fetched",
                "data": {
                    "orderReference": nomba_reference,
                    "amount": "15000.00",
                    "currency": "NGN",
                    "orderMetaData": {
                        "invoice_id": str(invoice.id),
                        "customer_id": str(customer.id),
                    },
                    "transaction": {
                        "transactionId": "txn_checkout_id_123",
                        "transactionAmount": "15000.00",
                        "responseCode": "00",
                    },
                    "tokenizedCardData": {
                        "tokenKey": "tok_nomba_poll_saved_card",
                        "cardType": "Visa",
                        "cardPan": "411111******4242",
                    },
                },
            }
        )

    monkeypatch.setattr("apps.payments.integrations.nomba.client.request.urlopen", fake_urlopen)

    response = APIClient().post(
        "/api/v1/portal/payment-methods/checkout/confirm",
        data={"order_reference": nomba_reference, "invoice_id": str(invoice.id)},
        format="json",
        HTTP_AUTHORIZATION=f"Portal {token}",
    )

    assert response.status_code == 200, response.content
    assert response.json()["confirmed"] is True
    assert seen == [f"https://sandbox.nomba.com/v1/checkout/order/{checkout_id}"]


def test_portal_checkout_confirm_uses_transaction_lookup_when_order_is_structural(monkeypatch):
    user, customer = _setup_workspace()
    environment = customer.environment
    environment.nomba_integration_mode = Environment.NombaIntegrationMode.BYOK
    environment.nomba_account_id = "acct_123"
    environment.nomba_client_id = "client_123"
    environment.nomba_client_secret = "secret_123"
    environment.nomba_access_token = "access-token"
    environment.nomba_token_expires_at = timezone.now() + timedelta(hours=1)
    environment.save(
        update_fields=[
            "nomba_integration_mode",
            "nomba_account_id",
            "nomba_client_id",
            "nomba_client_secret_encrypted",
            "nomba_access_token_encrypted",
            "nomba_token_expires_at",
            "updated_at",
        ]
    )
    invoice = customer.invoices.get(number="INV-PORTAL-001")
    checkout_id = "QMojVVIswaIri_iA6YONMcbjLOBR32-CvIArUO_lT9Szr_BGxp65Mgvx"
    nomba_reference = "7b1d57a3-ecea-4fb2-be74-4f4f26f0f229"
    local_reference = f"checkout-{invoice.id}"
    invoice.hosted_payment_url = f"https://pay.nomba.com/sandbox/{checkout_id}"
    invoice.metadata = {
        "nomba_checkout_id": checkout_id,
        "nomba_checkout_order_reference": nomba_reference,
    }
    invoice.save(update_fields=["hosted_payment_url", "metadata", "updated_at"])
    client = _signed_in_client(user)
    token, _session = _portal_token(
        client,
        customer,
        actions=["view_subscriptions", "view_invoices", "update_payment_method"],
    )
    seen = []

    def fake_urlopen(req, timeout):
        seen.append(req.full_url)
        if "/v1/checkout/order/" in req.full_url:
            return _NombaResponse(
                {
                    "code": "00",
                    "description": "order details fetched successful",
                    "data": {
                        "order": {
                            "accountId": "acct_123",
                            "amount": "15000.00",
                            "currency": "NGN",
                            "orderId": nomba_reference,
                            "orderReference": local_reference,
                            "orderMetaData": {
                                "invoice_id": str(invoice.id),
                                "customer_id": str(customer.id),
                            },
                        }
                    },
                }
            )
        return _NombaResponse(
            {
                "code": "00",
                "description": "checkout transaction fetched",
                "data": {
                    "success": True,
                    "message": "success",
                    "transactionDetails": {
                        "transactionId": "txn_lookup_123",
                        "amount": "15000.00",
                        "status": "SUCCESS",
                    },
                },
            }
        )

    monkeypatch.setattr("apps.payments.integrations.nomba.client.request.urlopen", fake_urlopen)

    response = APIClient().post(
        "/api/v1/portal/payment-methods/checkout/confirm",
        data={"order_reference": nomba_reference, "invoice_id": str(invoice.id)},
        format="json",
        HTTP_AUTHORIZATION=f"Portal {token}",
    )

    assert response.status_code == 200, response.content
    assert response.json()["confirmed"] is True
    assert seen == [
        f"https://sandbox.nomba.com/v1/checkout/order/{checkout_id}",
        f"https://sandbox.nomba.com/v1/checkout/transaction?idType=ORDER_ID&id={checkout_id}",
    ]
    invoice.refresh_from_db()
    assert invoice.status == Invoice.Status.PAID
    attempt = PaymentAttempt.objects.get(invoice=invoice)
    assert attempt.status == PaymentAttempt.Status.SUCCEEDED
    assert attempt.processor_reference == "txn_lookup_123"


def test_portal_checkout_confirm_returns_pending_when_nomba_rejects_lookup_refs(monkeypatch):
    user, customer = _setup_workspace()
    environment = customer.environment
    environment.nomba_integration_mode = Environment.NombaIntegrationMode.BYOK
    environment.nomba_account_id = "acct_123"
    environment.nomba_client_id = "client_123"
    environment.nomba_client_secret = "secret_123"
    environment.nomba_access_token = "access-token"
    environment.nomba_token_expires_at = timezone.now() + timedelta(hours=1)
    environment.save(
        update_fields=[
            "nomba_integration_mode",
            "nomba_account_id",
            "nomba_client_id",
            "nomba_client_secret_encrypted",
            "nomba_access_token_encrypted",
            "nomba_token_expires_at",
            "updated_at",
        ]
    )
    invoice = customer.invoices.get(number="INV-PORTAL-001")
    nomba_reference = "358ce347-db87-468e-ad19-1c8fee5220bb"
    invoice.metadata = {"nomba_checkout_order_reference": nomba_reference}
    invoice.save(update_fields=["metadata", "updated_at"])
    client = _signed_in_client(user)
    token, _session = _portal_token(
        client,
        customer,
        actions=["view_subscriptions", "view_invoices", "update_payment_method"],
    )

    def fake_urlopen(req, timeout):
        return _NombaResponse({"code": "400", "description": "Tag mismatch!", "status": False})

    monkeypatch.setattr("apps.payments.integrations.nomba.client.request.urlopen", fake_urlopen)

    response = APIClient().post(
        "/api/v1/portal/payment-methods/checkout/confirm",
        data={"order_reference": nomba_reference, "invoice_id": str(invoice.id)},
        format="json",
        HTTP_AUTHORIZATION=f"Portal {token}",
    )

    assert response.status_code == 202, response.content
    assert response.json()["confirmed"] is False
    assert response.json()["status"] == "pending"


def test_portal_checkout_confirm_prefers_stored_nomba_reference(monkeypatch):
    user, customer = _setup_workspace()
    environment = customer.environment
    environment.nomba_integration_mode = Environment.NombaIntegrationMode.BYOK
    environment.nomba_account_id = "acct_123"
    environment.nomba_client_id = "client_123"
    environment.nomba_client_secret = "secret_123"
    environment.nomba_access_token = "access-token"
    environment.nomba_token_expires_at = timezone.now() + timedelta(hours=1)
    environment.save(
        update_fields=[
            "nomba_integration_mode",
            "nomba_account_id",
            "nomba_client_id",
            "nomba_client_secret_encrypted",
            "nomba_access_token_encrypted",
            "nomba_token_expires_at",
            "updated_at",
        ]
    )
    invoice = customer.invoices.get(number="INV-PORTAL-001")
    browser_reference = f"checkout-{invoice.id}"
    nomba_reference = "48933b85-b994-45b7-abf7-e46e007b3d4f"
    invoice.metadata = {"nomba_checkout_order_reference": nomba_reference}
    invoice.save(update_fields=["metadata", "updated_at"])
    client = _signed_in_client(user)
    token, _session = _portal_token(
        client,
        customer,
        actions=["view_subscriptions", "view_invoices", "update_payment_method"],
    )
    seen = []

    def fake_urlopen(req, timeout):
        seen.append(req.full_url)
        return _NombaResponse(
            {
                "code": "00",
                "description": "checkout order fetched",
                "data": {
                    "orderReference": nomba_reference,
                    "amount": "15000.00",
                    "currency": "NGN",
                    "orderMetaData": {
                        "invoice_id": str(invoice.id),
                        "customer_id": str(customer.id),
                    },
                    "transaction": {
                        "transactionId": "txn_poll_456",
                        "transactionAmount": "15000.00",
                        "responseCode": "00",
                    },
                    "tokenizedCardData": {
                        "tokenKey": "tok_nomba_poll_saved_card",
                        "cardType": "Visa",
                        "cardPan": "411111******4242",
                    },
                },
            }
        )

    monkeypatch.setattr("apps.payments.integrations.nomba.client.request.urlopen", fake_urlopen)

    response = APIClient().post(
        "/api/v1/portal/payment-methods/checkout/confirm",
        data={"order_reference": browser_reference, "invoice_id": str(invoice.id)},
        format="json",
        HTTP_AUTHORIZATION=f"Portal {token}",
    )

    assert response.status_code == 200, response.content
    assert response.json()["confirmed"] is True
    assert seen == [f"https://sandbox.nomba.com/v1/checkout/order/{nomba_reference}"]
    attempt = PaymentAttempt.objects.get(invoice=invoice)
    assert attempt.status == PaymentAttempt.Status.SUCCEEDED
    assert attempt.processor_reference == "txn_poll_456"
