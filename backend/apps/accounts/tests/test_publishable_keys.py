from rest_framework.test import APIClient

from apps.accounts.models import Environment, Merchant, Role, TeamMember, User


PASSWORD = "Subpilot1!"
ENDPOINT = "/api/v1/api-keys/publishable-key/"


def _owner():
    merchant = Merchant.objects.create(name="SDK Co", slug="sdk-co", default_currency="NGN")
    Environment.objects.create(merchant=merchant, mode=Environment.Mode.TEST)
    Environment.objects.create(merchant=merchant, mode=Environment.Mode.LIVE)
    user = User.objects.create_user(
        email="owner@sdk-co.test",
        password=PASSWORD,
        display_name="SDK Owner",
        email_verified=True,
        onboarding_complete=True,
    )
    TeamMember.objects.create(merchant=merchant, user=user, role=Role.OWNER)
    return user, merchant


def _client(user):
    client = APIClient()
    response = client.post(
        "/api/v1/auth/sign-in",
        data={"email": user.email, "password": PASSWORD},
        format="json",
    )
    assert response.status_code == 200, response.content
    assert response.json()["ok"] is True
    return client


def test_publishable_keys_are_returned_for_each_environment():
    user, _merchant = _owner()
    client = _client(user)

    response = client.get(ENDPOINT)

    assert response.status_code == 200, response.content
    keys = {item["mode"]: item["publishable_key"] for item in response.json()["keys"]}
    assert keys["test"].startswith("pk_test_")
    assert keys["live"].startswith("pk_live_")


def test_publishable_key_can_be_rotated_by_mode():
    user, _merchant = _owner()
    client = _client(user)
    original = client.get(ENDPOINT).json()["keys"]
    original_test = next(item["publishable_key"] for item in original if item["mode"] == "test")

    response = client.post(ENDPOINT, data={"mode": "test"}, format="json")

    assert response.status_code == 200, response.content
    body = response.json()
    assert body["mode"] == "test"
    assert body["publishable_key"].startswith("pk_test_")
    assert body["publishable_key"] != original_test
