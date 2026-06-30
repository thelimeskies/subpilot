"""Write actions for support tickets + KYC reviews (S8).

All actions emit ``platform.support.*`` / ``platform.kyc.*`` audit log entries
via :func:`apps.audit.services.log_event.log_event`.
"""
from __future__ import annotations

from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone

from apps.audit.services.log_event import log_event

from ..models import (
    KycReview,
    PlatformAdmin,
    SupportTicket,
    SupportTicketReply,
)
from ..selectors.support import (
    get_or_create_kyc,
    get_ticket,
    normalize_kyc_level,
    normalize_kyc_status,
    normalize_ticket_priority,
    normalize_ticket_status,
)


class TicketNotFoundError(LookupError):
    pass


class KycNotFoundError(LookupError):
    pass


class InvalidTicketFieldError(ValueError):
    pass


def _actor_label(admin: PlatformAdmin | None) -> str:
    if admin is None:
        return "platform-admin"
    return admin.email or admin.display_name or "platform-admin"


def _resolve_ticket(ticket_id: str) -> SupportTicket:
    t = get_ticket(ticket_id)
    if t is None:
        raise TicketNotFoundError("Ticket not found.")
    return t


def _resolve_assignee(value: str | None) -> PlatformAdmin | None:
    if value is None or value == "":
        return None
    try:
        return PlatformAdmin.objects.get(pk=value)
    except (PlatformAdmin.DoesNotExist, ValueError):
        return None


@dataclass(frozen=True)
class TicketActionResult:
    ticket_id: str
    status: str
    priority: str
    assignee_id: str | None


@transaction.atomic
def create_ticket(
    *,
    merchant_id: str,
    subject: str,
    body: str = "",
    priority: str = "normal",
    requester_email: str = "",
    admin: PlatformAdmin | None,
    request=None,
) -> SupportTicket:
    from apps.accounts.models import Merchant

    try:
        merchant = Merchant.objects.get(pk=merchant_id)
    except (Merchant.DoesNotExist, ValueError) as exc:
        raise InvalidTicketFieldError("merchant_id is invalid.") from exc
    norm_priority = normalize_ticket_priority(priority) or "normal"
    if not subject or not subject.strip():
        raise InvalidTicketFieldError("subject is required.")
    ticket = SupportTicket.objects.create(
        merchant=merchant,
        subject=subject.strip()[:256],
        body=body or "",
        priority=norm_priority,
        requester_email=(requester_email or "").strip()[:254],
    )
    log_event(
        action="platform.support.ticket.create",
        actor_user=None,
        actor_label=_actor_label(admin),
        actor_role="platform_admin",
        merchant=merchant,
        target_type="support_ticket",
        target_id=str(ticket.id),
        metadata={
            "subject": ticket.subject,
            "priority": ticket.priority,
        },
        request=request,
    )
    return ticket


@transaction.atomic
def update_ticket(
    *,
    ticket_id: str,
    admin: PlatformAdmin | None,
    request=None,
    status: str | None = None,
    priority: str | None = None,
    assignee_id: str | None = None,
) -> SupportTicket:
    ticket = _resolve_ticket(ticket_id)
    changed: dict[str, tuple] = {}

    if status is not None:
        norm_status = normalize_ticket_status(status)
        if norm_status is None:
            raise InvalidTicketFieldError("status is invalid.")
        if ticket.status != norm_status:
            changed["status"] = (ticket.status, norm_status)
            ticket.status = norm_status

    if priority is not None:
        norm_priority = normalize_ticket_priority(priority)
        if norm_priority is None:
            raise InvalidTicketFieldError("priority is invalid.")
        if ticket.priority != norm_priority:
            changed["priority"] = (ticket.priority, norm_priority)
            ticket.priority = norm_priority

    if assignee_id is not None:
        if assignee_id == "":
            new_assignee = None
        else:
            new_assignee = _resolve_assignee(assignee_id)
            if new_assignee is None:
                raise InvalidTicketFieldError("assignee is invalid.")
        if (ticket.assignee_id or None) != (new_assignee.pk if new_assignee else None):
            changed["assignee_id"] = (
                str(ticket.assignee_id) if ticket.assignee_id else None,
                str(new_assignee.pk) if new_assignee else None,
            )
            ticket.assignee = new_assignee

    if changed:
        ticket.save()
        log_event(
            action="platform.support.ticket.update",
            actor_user=None,
            actor_label=_actor_label(admin),
            actor_role="platform_admin",
            merchant=ticket.merchant,
            target_type="support_ticket",
            target_id=str(ticket.id),
            metadata={
                "changes": {k: {"from": v[0], "to": v[1]} for k, v in changed.items()},
            },
            request=request,
        )
    return ticket


@transaction.atomic
def add_reply(
    *,
    ticket_id: str,
    body: str,
    admin: PlatformAdmin | None,
    request=None,
) -> SupportTicketReply:
    ticket = _resolve_ticket(ticket_id)
    body = (body or "").strip()
    if not body:
        raise InvalidTicketFieldError("reply body is required.")
    reply = SupportTicketReply.objects.create(
        ticket=ticket,
        author=admin,
        body=body,
    )
    # Bump ticket updated_at so list ordering reflects the new activity.
    ticket.save(update_fields=["updated_at"])
    log_event(
        action="platform.support.ticket.reply",
        actor_user=None,
        actor_label=_actor_label(admin),
        actor_role="platform_admin",
        merchant=ticket.merchant,
        target_type="support_ticket",
        target_id=str(ticket.id),
        metadata={"reply_id": str(reply.id), "length": len(body)},
        request=request,
    )
    return reply


@dataclass(frozen=True)
class KycUpdateResult:
    merchant_id: str
    status: str
    level: str


@transaction.atomic
def update_kyc(
    *,
    merchant_id: str,
    admin: PlatformAdmin | None,
    request=None,
    status: str | None = None,
    level: str | None = None,
    notes: str | None = None,
    flags: list | None = None,
    documents: list | None = None,
) -> KycReview:
    review = get_or_create_kyc(merchant_id)
    if review is None:
        raise KycNotFoundError("Merchant not found.")

    changed: dict[str, tuple] = {}

    if status is not None:
        norm = normalize_kyc_status(status)
        if norm is None:
            raise InvalidTicketFieldError("status is invalid.")
        if review.status != norm:
            changed["status"] = (review.status, norm)
            review.status = norm
            review.reviewed_at = timezone.now()
            if admin is not None:
                review.reviewer = admin

    if level is not None:
        norm_level = normalize_kyc_level(level)
        if norm_level is None:
            raise InvalidTicketFieldError("level is invalid.")
        if review.level != norm_level:
            changed["level"] = (review.level, norm_level)
            review.level = norm_level

    if notes is not None and notes != review.notes:
        changed["notes"] = (review.notes, notes)
        review.notes = notes

    if flags is not None and list(flags) != list(review.flags or []):
        changed["flags"] = (review.flags, list(flags))
        review.flags = list(flags)

    if documents is not None and list(documents) != list(review.documents or []):
        changed["documents"] = (review.documents, list(documents))
        review.documents = list(documents)

    if changed:
        review.save()
        log_event(
            action="platform.kyc.update",
            actor_user=None,
            actor_label=_actor_label(admin),
            actor_role="platform_admin",
            merchant=review.merchant,
            target_type="kyc_review",
            target_id=str(review.id),
            metadata={
                "changes": {
                    k: {"from": v[0], "to": v[1]}
                    for k, v in changed.items()
                    if k in ("status", "level", "notes")
                },
                "flag_count": len(review.flags or []),
                "document_count": len(review.documents or []),
            },
            request=request,
        )
    return review


__all__ = [
    "TicketNotFoundError",
    "KycNotFoundError",
    "InvalidTicketFieldError",
    "create_ticket",
    "update_ticket",
    "add_reply",
    "update_kyc",
    "TicketActionResult",
    "KycUpdateResult",
]
