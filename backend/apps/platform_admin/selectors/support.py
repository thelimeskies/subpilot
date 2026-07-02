"""Cross-tenant support tickets + KYC selectors (S8).

Maps :class:`apps.platform_admin.models.SupportTicket` and ``KycReview`` rows
onto the FE shapes declared in
[seed.ts](file:///Users/mac/Desktop/Projects/HackathonxNomba/apps/subpilot-admin/src/data/seed.ts).

Internal → FE projections:
    ticket.status:    open         → "Open"
                      in_progress  → "Awaiting"
                      resolved     → "Resolved"
                      closed       → "Closed"
    ticket.priority:  low          → "Low"
                      normal       → "Normal"
                      high         → "High"
                      urgent       → "Urgent"
    kyc.status:       verified       → "Verified"
                      in_review      → "In review"
                      rejected       → "Rejected"
                      action_needed  → "Action needed"
    kyc.level:        tier_1 → "Tier 1"  (etc.)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from django.db.models import Q

from ..models import (
    KycLevel,
    KycReview,
    KycStatus,
    SupportTicket,
    SupportTicketPriority,
    SupportTicketReply,
    SupportTicketStatus,
)
from ..services.kyc_metadata import sync_merchant_kyc_review_from_metadata


# --- Ticket projections ----------------------------------------------------

_FE_TICKET_STATUS = {
    SupportTicketStatus.OPEN: "Open",
    SupportTicketStatus.IN_PROGRESS: "Awaiting",
    SupportTicketStatus.RESOLVED: "Resolved",
    SupportTicketStatus.CLOSED: "Closed",
}

_FE_TICKET_PRIORITY = {
    SupportTicketPriority.LOW: "Low",
    SupportTicketPriority.NORMAL: "Normal",
    SupportTicketPriority.HIGH: "High",
    SupportTicketPriority.URGENT: "Urgent",
}

_FE_TO_INTERNAL_STATUS = {
    "open": SupportTicketStatus.OPEN,
    "awaiting": SupportTicketStatus.IN_PROGRESS,
    "in_progress": SupportTicketStatus.IN_PROGRESS,
    "resolved": SupportTicketStatus.RESOLVED,
    "closed": SupportTicketStatus.CLOSED,
}

_FE_TO_INTERNAL_PRIORITY = {
    "low": SupportTicketPriority.LOW,
    "normal": SupportTicketPriority.NORMAL,
    "high": SupportTicketPriority.HIGH,
    "urgent": SupportTicketPriority.URGENT,
}


def normalize_ticket_status(value: str | None) -> str | None:
    if value is None:
        return None
    return _FE_TO_INTERNAL_STATUS.get(value.lower())


def normalize_ticket_priority(value: str | None) -> str | None:
    if value is None:
        return None
    return _FE_TO_INTERNAL_PRIORITY.get(value.lower())


def _short_id(pk: Any) -> str:
    s = str(pk).replace("-", "")
    return f"tic_{s[:8].upper()}"


def _assignee_label(ticket: SupportTicket) -> str:
    if ticket.assignee_id is None:
        return "Unassigned"
    a = ticket.assignee
    return a.display_name or a.email


def _author_label(reply: SupportTicketReply) -> str:
    if reply.author_id is None:
        return "Unknown"
    a = reply.author
    return a.display_name or a.email


@dataclass(frozen=True)
class TicketListItem:
    id: str
    raw_id: str
    subject: str
    merchant: str
    merchant_id: str
    priority: str
    raw_priority: str
    status: str
    raw_status: str
    assignee: str
    assignee_id: str | None
    updated_at: str
    created_at: str


def project_ticket(t: SupportTicket) -> dict:
    return {
        "id": _short_id(t.pk),
        "rawId": str(t.pk),
        "subject": t.subject,
        "merchant": t.merchant.name if t.merchant_id else "",
        "merchantId": str(t.merchant_id) if t.merchant_id else "",
        "priority": _FE_TICKET_PRIORITY.get(t.priority, t.priority),
        "rawPriority": t.priority,
        "status": _FE_TICKET_STATUS.get(t.status, t.status),
        "rawStatus": t.status,
        "assignee": _assignee_label(t),
        "assigneeId": str(t.assignee_id) if t.assignee_id else None,
        "requesterEmail": t.requester_email,
        "updatedAt": t.updated_at.isoformat() if t.updated_at else "",
        "createdAt": t.created_at.isoformat() if t.created_at else "",
    }


def project_ticket_detail(t: SupportTicket) -> dict:
    base = project_ticket(t)
    base["body"] = t.body
    base["replies"] = [
        {
            "id": str(r.pk),
            "author": _author_label(r),
            "authorId": str(r.author_id) if r.author_id else None,
            "body": r.body,
            "createdAt": r.created_at.isoformat() if r.created_at else "",
        }
        for r in t.replies.all().order_by("created_at")
    ]
    return base


def list_tickets_cross_tenant(
    *,
    status: str | None = None,
    priority: str | None = None,
    merchant_id: str | None = None,
    assignee_id: str | None = None,
    q: str | None = None,
    limit: int = 25,
    offset: int = 0,
) -> tuple[list[SupportTicket], int]:
    qs = SupportTicket.objects.select_related("merchant", "assignee").order_by("-updated_at")
    norm_status = normalize_ticket_status(status)
    if norm_status:
        qs = qs.filter(status=norm_status)
    norm_priority = normalize_ticket_priority(priority)
    if norm_priority:
        qs = qs.filter(priority=norm_priority)
    if merchant_id:
        qs = qs.filter(merchant_id=merchant_id)
    if assignee_id:
        qs = qs.filter(assignee_id=assignee_id)
    if q:
        qs = qs.filter(
            Q(subject__icontains=q)
            | Q(body__icontains=q)
            | Q(merchant__name__icontains=q)
        )
    total = qs.count()
    rows = list(qs[offset : offset + limit])
    return rows, total


def get_ticket(ticket_id: str) -> SupportTicket | None:
    try:
        return (
            SupportTicket.objects.select_related("merchant", "assignee")
            .prefetch_related("replies__author")
            .get(pk=ticket_id)
        )
    except (SupportTicket.DoesNotExist, ValueError):
        return None


# --- KYC projections -------------------------------------------------------

_FE_KYC_STATUS = {
    KycStatus.VERIFIED: "Verified",
    KycStatus.IN_REVIEW: "In review",
    KycStatus.REJECTED: "Rejected",
    KycStatus.ACTION_NEEDED: "Action needed",
}

_FE_KYC_LEVEL = {
    KycLevel.TIER_1: "Tier 1",
    KycLevel.TIER_2: "Tier 2",
    KycLevel.TIER_3: "Tier 3",
}

_FE_TO_INTERNAL_KYC_STATUS = {
    "verified": KycStatus.VERIFIED,
    "in review": KycStatus.IN_REVIEW,
    "in_review": KycStatus.IN_REVIEW,
    "rejected": KycStatus.REJECTED,
    "action needed": KycStatus.ACTION_NEEDED,
    "action_needed": KycStatus.ACTION_NEEDED,
}

_FE_TO_INTERNAL_KYC_LEVEL = {
    "tier 1": KycLevel.TIER_1,
    "tier_1": KycLevel.TIER_1,
    "tier 2": KycLevel.TIER_2,
    "tier_2": KycLevel.TIER_2,
    "tier 3": KycLevel.TIER_3,
    "tier_3": KycLevel.TIER_3,
}


def normalize_kyc_status(value: str | None) -> str | None:
    if value is None:
        return None
    return _FE_TO_INTERNAL_KYC_STATUS.get(value.lower())


def normalize_kyc_level(value: str | None) -> str | None:
    if value is None:
        return None
    return _FE_TO_INTERNAL_KYC_LEVEL.get(value.lower())


def _reviewer_label(review: KycReview) -> str | None:
    if review.reviewer_id is None:
        return None
    return review.reviewer.display_name or review.reviewer.email


def project_kyc(review: KycReview) -> dict:
    return {
        "merchantId": str(review.merchant_id),
        "merchant": review.merchant.name if review.merchant_id else "",
        "status": _FE_KYC_STATUS.get(review.status, review.status),
        "rawStatus": review.status,
        "level": _FE_KYC_LEVEL.get(review.level, review.level),
        "rawLevel": review.level,
        "submittedAt": review.submitted_at.isoformat() if review.submitted_at else None,
        "reviewedAt": review.reviewed_at.isoformat() if review.reviewed_at else None,
        "reviewer": _reviewer_label(review),
        "documents": list(review.documents or []),
        "flags": list(review.flags or []),
        "notes": review.notes,
    }


def get_or_create_kyc(merchant_id: str) -> KycReview | None:
    from apps.accounts.models import Merchant

    try:
        merchant = Merchant.objects.get(pk=merchant_id)
    except (Merchant.DoesNotExist, ValueError):
        return None
    synced = sync_merchant_kyc_review_from_metadata(merchant)
    if synced is not None:
        return synced
    review, _ = KycReview.objects.select_related("merchant", "reviewer").get_or_create(
        merchant=merchant
    )
    return review


__all__ = [
    "TicketListItem",
    "list_tickets_cross_tenant",
    "get_ticket",
    "project_ticket",
    "project_ticket_detail",
    "normalize_ticket_status",
    "normalize_ticket_priority",
    "project_kyc",
    "get_or_create_kyc",
    "normalize_kyc_status",
    "normalize_kyc_level",
]
