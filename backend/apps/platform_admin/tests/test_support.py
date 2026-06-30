"""Tests for the support tickets + KYC endpoints (S8)."""
from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Environment, Merchant
from apps.audit.models import AuditLog
from apps.platform_admin.models import (
    KycLevel,
    KycReview,
    KycStatus,
    SupportTicket,
    SupportTicketPriority,
    SupportTicketReply,
    SupportTicketStatus,
)

pytestmark = pytest.mark.django_db


# --- Helpers ---------------------------------------------------------------


def _sign_in(client: APIClient, email: str) -> None:
    resp = client.post(
        "/api/v1/platform/auth/sign-in",
        data={"email": email, "password": "Subpilot1!"},
        format="json",
    )
    assert resp.status_code == 200, resp.content


def _seed_merchant(*, name: str = "Acme", slug: str = "acme") -> Merchant:
    m = Merchant.objects.create(name=name, slug=slug, default_currency="NGN")
    Environment.objects.create(merchant=m, mode=Environment.Mode.LIVE)
    return m


def _seed_ticket(
    merchant: Merchant,
    *,
    subject: str = "Subject",
    status: str = SupportTicketStatus.OPEN,
    priority: str = SupportTicketPriority.NORMAL,
) -> SupportTicket:
    return SupportTicket.objects.create(
        merchant=merchant,
        subject=subject,
        body="Body",
        priority=priority,
        status=status,
    )


# --- Permission gate -------------------------------------------------------


def test_tickets_list_requires_session():
    resp = APIClient().get("/api/v1/platform/tickets")
    assert resp.status_code in (401, 403)


def test_kyc_requires_session():
    m = _seed_merchant()
    resp = APIClient().get(f"/api/v1/platform/kyc/{m.id}")
    assert resp.status_code in (401, 403)


def test_tickets_list_blocks_merchant_user(django_user_model):
    user = django_user_model.objects.create(
        username="m@acme.test", email="m@acme.test", is_staff=True
    )
    user.set_password("Subpilot1!")
    user.save()
    client = APIClient()
    client.force_authenticate(user=user)
    resp = client.get("/api/v1/platform/tickets")
    assert resp.status_code in (401, 403)


def test_kyc_blocks_merchant_user(django_user_model):
    m = _seed_merchant()
    user = django_user_model.objects.create(
        username="m@acme.test", email="m@acme.test", is_staff=True
    )
    user.set_password("Subpilot1!")
    user.save()
    client = APIClient()
    client.force_authenticate(user=user)
    resp = client.get(f"/api/v1/platform/kyc/{m.id}")
    assert resp.status_code in (401, 403)


def test_ticket_create_blocks_merchant_user(django_user_model):
    m = _seed_merchant()
    user = django_user_model.objects.create(
        username="m@acme.test", email="m@acme.test", is_staff=True
    )
    user.set_password("Subpilot1!")
    user.save()
    client = APIClient()
    client.force_authenticate(user=user)
    resp = client.post(
        "/api/v1/platform/tickets",
        data={"merchant_id": str(m.id), "subject": "X"},
        format="json",
    )
    assert resp.status_code in (401, 403)


# --- Ticket list -----------------------------------------------------------


def test_tickets_list_returns_fe_shape(platform_admin_owner):
    m = _seed_merchant()
    _seed_ticket(m, subject="Webhook trouble", priority=SupportTicketPriority.HIGH)
    _seed_ticket(m, subject="Other", status=SupportTicketStatus.RESOLVED)
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    resp = client.get("/api/v1/platform/tickets?page_size=10")
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body["ok"] is True
    assert body["total"] >= 2
    row = body["results"][0]
    for key in (
        "id", "rawId", "subject", "merchant", "merchantId",
        "priority", "rawPriority", "status", "rawStatus",
        "assignee", "assigneeId", "updatedAt", "createdAt",
    ):
        assert key in row, f"missing {key!r}"
    statuses = {r["status"] for r in body["results"]}
    assert {"Open", "Resolved"} & statuses


def test_tickets_list_filter_status_and_priority(platform_admin_owner):
    m = _seed_merchant()
    _seed_ticket(m, subject="A", priority=SupportTicketPriority.URGENT)
    _seed_ticket(m, subject="B", status=SupportTicketStatus.RESOLVED)
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    resp = client.get("/api/v1/platform/tickets?status=open&priority=urgent")
    assert resp.status_code == 200
    body = resp.json()
    assert body["results"]
    assert all(r["status"] == "Open" for r in body["results"])
    assert all(r["priority"] == "Urgent" for r in body["results"])


def test_tickets_list_filter_by_merchant(platform_admin_owner):
    m1 = _seed_merchant(name="Acme", slug="acme")
    m2 = _seed_merchant(name="Other", slug="other")
    _seed_ticket(m1, subject="Acme issue")
    _seed_ticket(m2, subject="Other issue")
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    resp = client.get(f"/api/v1/platform/tickets?merchant_id={m1.id}")
    body = resp.json()
    assert resp.status_code == 200
    assert body["results"]
    assert all(r["merchantId"] == str(m1.id) for r in body["results"])


# --- Ticket create / detail / update / reply ------------------------------


def test_ticket_create_returns_201_and_audits(platform_admin_owner):
    m = _seed_merchant()
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    resp = client.post(
        "/api/v1/platform/tickets",
        data={
            "merchant_id": str(m.id),
            "subject": "Help with refunds",
            "body": "Please help",
            "priority": "high",
            "requester_email": "user@acme.test",
        },
        format="json",
    )
    assert resp.status_code == 201, resp.content
    body = resp.json()
    assert body["ok"] is True
    tid = body["ticket"]["rawId"]
    assert SupportTicket.objects.filter(pk=tid).exists()
    log = AuditLog.objects.filter(
        action="platform.support.ticket.create", target_id=tid
    ).first()
    assert log is not None
    assert log.actor_role == "platform_admin"


def test_ticket_create_invalid_merchant_returns_400(platform_admin_owner):
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    resp = client.post(
        "/api/v1/platform/tickets",
        data={"merchant_id": "00000000-0000-0000-0000-000000000000", "subject": "X"},
        format="json",
    )
    assert resp.status_code == 400


def test_ticket_detail_returns_replies(platform_admin_owner):
    m = _seed_merchant()
    t = _seed_ticket(m)
    SupportTicketReply.objects.create(ticket=t, author=platform_admin_owner, body="Hello")
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    resp = client.get(f"/api/v1/platform/tickets/{t.id}")
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body["ok"] is True
    assert isinstance(body["ticket"]["replies"], list)
    assert len(body["ticket"]["replies"]) == 1


def test_ticket_detail_unknown_404(platform_admin_owner):
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    resp = client.get("/api/v1/platform/tickets/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


def test_ticket_update_status_priority_and_audits(platform_admin_owner):
    m = _seed_merchant()
    t = _seed_ticket(m)
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    resp = client.patch(
        f"/api/v1/platform/tickets/{t.id}",
        data={"status": "resolved", "priority": "high"},
        format="json",
    )
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body["ticket"]["status"] == "Resolved"
    assert body["ticket"]["priority"] == "High"
    t.refresh_from_db()
    assert t.status == SupportTicketStatus.RESOLVED
    assert t.priority == SupportTicketPriority.HIGH
    log = AuditLog.objects.filter(
        action="platform.support.ticket.update", target_id=str(t.id)
    ).first()
    assert log is not None


def test_ticket_update_assignee(platform_admin_owner, platform_admin_operator):
    m = _seed_merchant()
    t = _seed_ticket(m)
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    resp = client.patch(
        f"/api/v1/platform/tickets/{t.id}",
        data={"assignee_id": str(platform_admin_operator.id)},
        format="json",
    )
    assert resp.status_code == 200
    t.refresh_from_db()
    assert t.assignee_id == platform_admin_operator.id


def test_ticket_reply_creates_row_and_audits(platform_admin_owner):
    m = _seed_merchant()
    t = _seed_ticket(m)
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    resp = client.post(
        f"/api/v1/platform/tickets/{t.id}/replies",
        data={"body": "Looking into it."},
        format="json",
    )
    assert resp.status_code == 201, resp.content
    assert SupportTicketReply.objects.filter(ticket=t).count() == 1
    log = AuditLog.objects.filter(
        action="platform.support.ticket.reply", target_id=str(t.id)
    ).first()
    assert log is not None


def test_ticket_reply_empty_body_400(platform_admin_owner):
    m = _seed_merchant()
    t = _seed_ticket(m)
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    resp = client.post(
        f"/api/v1/platform/tickets/{t.id}/replies",
        data={"body": ""},
        format="json",
    )
    assert resp.status_code == 400


# --- KYC -------------------------------------------------------------------


def test_kyc_get_creates_row_lazily(platform_admin_owner):
    m = _seed_merchant()
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    resp = client.get(f"/api/v1/platform/kyc/{m.id}")
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body["ok"] is True
    for key in (
        "merchantId", "merchant", "status", "rawStatus", "level", "rawLevel",
        "submittedAt", "reviewedAt", "reviewer", "documents", "flags", "notes",
    ):
        assert key in body["kyc"], f"missing {key!r}"
    assert KycReview.objects.filter(merchant=m).exists()


def test_kyc_unknown_merchant_404(platform_admin_owner):
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    resp = client.get("/api/v1/platform/kyc/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


def test_kyc_update_status_and_audits(platform_admin_owner):
    m = _seed_merchant()
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    resp = client.patch(
        f"/api/v1/platform/kyc/{m.id}",
        data={
            "status": "verified",
            "level": "tier_2",
            "notes": "All good",
            "flags": ["double-checked"],
        },
        format="json",
    )
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body["kyc"]["status"] == "Verified"
    assert body["kyc"]["level"] == "Tier 2"
    assert body["kyc"]["notes"] == "All good"
    assert body["kyc"]["flags"] == ["double-checked"]
    review = KycReview.objects.get(merchant=m)
    assert review.status == KycStatus.VERIFIED
    assert review.level == KycLevel.TIER_2
    assert review.reviewer_id == platform_admin_owner.id
    log = AuditLog.objects.filter(
        action="platform.kyc.update", target_id=str(review.id)
    ).first()
    assert log is not None
    assert log.merchant_id == m.id


def test_kyc_update_invalid_status_400(platform_admin_owner):
    m = _seed_merchant()
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    resp = client.patch(
        f"/api/v1/platform/kyc/{m.id}",
        data={"status": "bogus"},
        format="json",
    )
    assert resp.status_code == 400
