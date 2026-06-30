from rest_framework.test import APIClient

from apps.accounts.models import Environment, Merchant, Role, TeamMember, User
from apps.audit.models import AuditLog
from apps.catalog.models import Plan, PriceVersion, Product


PASSWORD = "Subpilot1!"
ENDPOINT = "/api/v1/onboarding/complete/"
DRAFT_ENDPOINT = "/api/v1/onboarding/draft/"


def _owner():
    merchant = Merchant.objects.create(name="Acme Draft", slug="acme-draft", default_currency="NGN")
    Environment.objects.create(merchant=merchant, mode=Environment.Mode.TEST)
    Environment.objects.create(merchant=merchant, mode=Environment.Mode.LIVE)
    user = User.objects.create_user(
        email="owner@acme-draft.test",
        password=PASSWORD,
        display_name="Ada Owner",
        email_verified=True,
        onboarding_complete=False,
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


def _payload(**overrides):
    payload = {
        "business": {
            "legalName": "Acme Learning Hub Ltd",
            "tradingName": "Acme Learning",
            "country": "Nigeria",
            "industry": "E-learning / education",
            "website": "https://acme.test",
            "description": "Cohort courses for operators.",
        },
        "kyc": {
            "rcNumber": "RC-123456",
            "directorIdName": "director-id.pdf",
            "directorIdData": "data:application/pdf;base64,abc",
            "addressProofName": "utility.pdf",
            "addressProofData": "data:application/pdf;base64,def",
        },
        "payout": {
            "bank": "GTBank",
            "accountNumber": "0123456789",
            "accountName": "Acme Learning Hub Ltd",
            "resolved": True,
            "settlementFrequency": "weekly",
        },
        "branding": {
            "primaryColor": "#056058",
            "logoData": "data:image/png;base64,logo",
            "subdomain": "acme-learning",
        },
        "plans": {"mode": "import"},
        "mfa": {"secret": "ABCDEFGHIJKLMNOP", "enabled": True},
        "team": [
            {"email": "finance@acme-draft.test", "role": "Finance"},
            {"email": "support@acme-draft.test", "role": "Support"},
        ],
    }
    payload.update(overrides)
    return payload


def test_complete_onboarding_requires_authentication():
    response = APIClient().post(ENDPOINT, data=_payload(), format="json")

    assert response.status_code in (401, 403)


def test_complete_onboarding_persists_workspace_and_imports_once():
    user, merchant = _owner()
    client = _client(user)

    response = client.post(ENDPOINT, data=_payload(), format="json")

    assert response.status_code == 200, response.content
    body = response.json()
    assert body["ok"] is True
    assert body["user"]["onboardingComplete"] is True
    assert body["user"]["mfaEnabled"] is True
    assert body["importedPlans"] == ["Starter", "Growth", "Scale"]
    assert body["invitedTeam"] == ["finance@acme-draft.test", "support@acme-draft.test"]

    user.refresh_from_db()
    merchant.refresh_from_db()
    assert user.onboarding_complete is True
    assert user.mfa_enabled is True
    assert merchant.name == "Acme Learning"
    assert merchant.industry == "E-learning / education"
    assert merchant.metadata["org"]["portal_subdomain"] == "acme-learning"
    assert merchant.metadata["settings"]["payouts"]["account_number"] == "0123456789"
    assert merchant.metadata["settings"]["branding"]["logo_data"] == "data:image/png;base64,logo"
    assert merchant.metadata["kyc"]["status"] == "pending_review"

    env = Environment.objects.get(merchant=merchant, mode=Environment.Mode.TEST)
    assert Product.objects.filter(merchant=merchant, environment=env).count() == 1
    assert Plan.objects.filter(merchant=merchant, environment=env, status=Plan.Status.ACTIVE).count() == 3
    assert PriceVersion.objects.filter(plan__merchant=merchant, plan__environment=env, active_to__isnull=True).count() == 3
    assert TeamMember.objects.filter(merchant=merchant, status=TeamMember.Status.INVITED).count() == 2
    assert AuditLog.objects.filter(action="accounts.onboarding_completed", merchant=merchant).exists()

    second = client.post(ENDPOINT, data=_payload(), format="json")

    assert second.status_code == 200, second.content
    assert Product.objects.filter(merchant=merchant, environment=env).count() == 1
    assert Plan.objects.filter(merchant=merchant, environment=env).count() == 3
    assert TeamMember.objects.filter(merchant=merchant, status=TeamMember.Status.INVITED).count() == 2


def test_onboarding_draft_saves_and_resumes_for_same_user_on_new_client():
    user, _merchant = _owner()
    client = _client(user)
    draft = {
        **_payload(),
        "version": 1,
        "currentStepId": "payout",
        "completedSteps": ["business", "kyc"],
        "completed": False,
    }

    saved = client.patch(DRAFT_ENDPOINT, data={"draft": draft}, format="json")

    assert saved.status_code == 200, saved.content
    assert saved.json()["draft"]["currentStepId"] == "payout"

    other_device = _client(user)
    resumed = other_device.get(DRAFT_ENDPOINT)

    assert resumed.status_code == 200, resumed.content
    body = resumed.json()
    assert body["draft"]["currentStepId"] == "payout"
    assert body["draft"]["completedSteps"] == ["business", "kyc"]
    assert body["draft"]["business"]["legalName"] == "Acme Learning Hub Ltd"


def test_complete_onboarding_clears_saved_draft():
    user, merchant = _owner()
    client = _client(user)
    draft = {
        **_payload(),
        "version": 1,
        "currentStepId": "finish",
        "completedSteps": ["business", "kyc", "payout", "branding", "plans", "mfa", "team"],
        "completed": False,
    }
    assert client.patch(DRAFT_ENDPOINT, data={"draft": draft}, format="json").status_code == 200

    response = client.post(ENDPOINT, data=_payload(), format="json")

    assert response.status_code == 200, response.content
    merchant.refresh_from_db()
    assert "onboarding_drafts" not in merchant.metadata


def test_complete_onboarding_rejects_unresolved_payout():
    user, _merchant = _owner()
    client = _client(user)
    payload = _payload(payout={**_payload()["payout"], "resolved": False})

    response = client.post(ENDPOINT, data=payload, format="json")

    assert response.status_code == 400
    assert response.json()["ok"] is False
    user.refresh_from_db()
    assert user.onboarding_complete is False
