from rest_framework.test import APIClient

from apps.accounts.models import ApiKey, Environment, Merchant, User
from apps.customers.models import Customer


def _workspace():
    merchant = Merchant.objects.create(
        name="Developer API Co",
        slug="developer-api-co",
        default_currency="NGN",
    )
    environment = Environment.objects.create(merchant=merchant, mode=Environment.Mode.TEST)
    owner = User.objects.create_user(
        email="owner@developer-api.test",
        password="Subpilot1!",
        display_name="Developer API Owner",
        email_verified=True,
        onboarding_complete=True,
    )
    Customer.objects.create(
        merchant=merchant,
        environment=environment,
        email="existing@developer-api.test",
        name="Existing Customer",
    )
    return merchant, environment, owner


def _issue_key(merchant, environment, owner, scopes):
    secret = "secret-for-api-key-scope-test"
    api_key = ApiKey.objects.create(
        merchant=merchant,
        environment=environment,
        name="Scope test",
        key_prefix="nse_test_scope",
        key_hash=ApiKey.hash_secret(secret),
        scopes=scopes,
        created_by=owner,
    )
    return api_key, f"{api_key.key_prefix}_{secret}"


def test_api_key_read_scope_can_list_tenant_customers():
    merchant, environment, owner = _workspace()
    _api_key, plaintext = _issue_key(merchant, environment, owner, ["read"])

    response = APIClient().get(
        "/api/v1/customers/",
        HTTP_AUTHORIZATION=f"Bearer {plaintext}",
    )

    assert response.status_code == 200, response.content
    assert response.json()["results"][0]["email"] == "existing@developer-api.test"


def test_api_key_read_scope_cannot_create_customer():
    merchant, environment, owner = _workspace()
    _api_key, plaintext = _issue_key(merchant, environment, owner, ["read"])

    response = APIClient().post(
        "/api/v1/customers/",
        data={"email": "new@developer-api.test", "name": "New Customer"},
        format="json",
        HTTP_AUTHORIZATION=f"Bearer {plaintext}",
    )

    assert response.status_code == 403, response.content


def test_api_key_write_scope_can_create_customer():
    merchant, environment, owner = _workspace()
    _api_key, plaintext = _issue_key(merchant, environment, owner, ["read", "write"])

    response = APIClient().post(
        "/api/v1/customers/",
        data={"email": "new@developer-api.test", "name": "New Customer"},
        format="json",
        HTTP_AUTHORIZATION=f"Bearer {plaintext}",
    )

    assert response.status_code == 201, response.content
    assert response.json()["email"] == "new@developer-api.test"
