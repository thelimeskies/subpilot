"""Cross-tenant support tickets + KYC endpoints (S8).

- ``GET  /api/v1/platform/tickets`` — paginated cross-tenant ticket list.
- ``POST /api/v1/platform/tickets`` — create a ticket.
- ``GET  /api/v1/platform/tickets/<id>`` — ticket detail with replies.
- ``PATCH /api/v1/platform/tickets/<id>`` — update status/priority/assignee.
- ``POST /api/v1/platform/tickets/<id>/replies`` — append a reply.
- ``GET   /api/v1/platform/kyc/<merchant_id>`` — KYC review for a merchant.
- ``PATCH /api/v1/platform/kyc/<merchant_id>`` — update KYC fields.
"""
from __future__ import annotations

from drf_spectacular.utils import OpenApiParameter, OpenApiTypes, extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from ..authentication import PlatformAdminAuthentication
from ..permissions import IsPlatformAdmin
from ..selectors.support import (
    get_or_create_kyc,
    get_ticket,
    list_tickets_cross_tenant,
    project_kyc,
    project_ticket,
    project_ticket_detail,
)
from ..services.support import (
    InvalidTicketFieldError,
    KycNotFoundError,
    TicketNotFoundError,
    add_reply,
    create_ticket,
    update_kyc,
    update_ticket,
)


def _to_int(value, default: int) -> int:
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _bad(reason: str, code: int = 400) -> Response:
    return Response({"ok": False, "reason": reason}, status=code)


def _not_found(reason: str = "Not found.") -> Response:
    return Response({"ok": False, "reason": reason}, status=404)


class PlatformTicketsView(APIView):
    """List + create support tickets (cross-tenant)."""

    permission_classes = [IsPlatformAdmin]
    authentication_classes = [PlatformAdminAuthentication]

    @extend_schema(
        tags=["Platform Admin"],
        parameters=[
            OpenApiParameter("status", OpenApiTypes.STR, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("priority", OpenApiTypes.STR, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("merchant_id", OpenApiTypes.STR, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("assignee_id", OpenApiTypes.STR, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("q", OpenApiTypes.STR, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("page", OpenApiTypes.INT, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("page_size", OpenApiTypes.INT, OpenApiParameter.QUERY, required=False),
        ],
        responses=OpenApiTypes.OBJECT,
    )
    def get(self, request):
        page = max(1, _to_int(request.query_params.get("page"), 1))
        page_size = min(100, max(1, _to_int(request.query_params.get("page_size"), 25)))
        offset = (page - 1) * page_size
        items, total = list_tickets_cross_tenant(
            status=request.query_params.get("status") or None,
            priority=request.query_params.get("priority") or None,
            merchant_id=request.query_params.get("merchant_id") or None,
            assignee_id=request.query_params.get("assignee_id") or None,
            q=request.query_params.get("q") or None,
            limit=page_size,
            offset=offset,
        )
        return Response(
            {
                "ok": True,
                "page": page,
                "pageSize": page_size,
                "total": total,
                "results": [project_ticket(t) for t in items],
            }
        )

    @extend_schema(tags=["Platform Admin"], responses=OpenApiTypes.OBJECT)
    def post(self, request):
        data = request.data if isinstance(request.data, dict) else {}
        try:
            ticket = create_ticket(
                merchant_id=data.get("merchant_id") or data.get("merchantId") or "",
                subject=data.get("subject") or "",
                body=data.get("body") or "",
                priority=data.get("priority") or "normal",
                requester_email=data.get("requester_email") or data.get("requesterEmail") or "",
                admin=getattr(request, "platform_admin", None),
                request=request,
            )
        except InvalidTicketFieldError as exc:
            return _bad(str(exc))
        return Response({"ok": True, "ticket": project_ticket_detail(ticket)}, status=201)


class PlatformTicketDetailView(APIView):
    """Ticket detail + update."""

    permission_classes = [IsPlatformAdmin]
    authentication_classes = [PlatformAdminAuthentication]

    @extend_schema(tags=["Platform Admin"], responses=OpenApiTypes.OBJECT)
    def get(self, request, ticket_id):
        t = get_ticket(ticket_id)
        if t is None:
            return _not_found("Ticket not found.")
        return Response({"ok": True, "ticket": project_ticket_detail(t)})

    @extend_schema(tags=["Platform Admin"], responses=OpenApiTypes.OBJECT)
    def patch(self, request, ticket_id):
        data = request.data if isinstance(request.data, dict) else {}
        try:
            ticket = update_ticket(
                ticket_id=ticket_id,
                admin=getattr(request, "platform_admin", None),
                request=request,
                status=data.get("status"),
                priority=data.get("priority"),
                assignee_id=data.get("assignee_id") if "assignee_id" in data else data.get("assigneeId"),
            )
        except TicketNotFoundError:
            return _not_found("Ticket not found.")
        except InvalidTicketFieldError as exc:
            return _bad(str(exc))
        return Response({"ok": True, "ticket": project_ticket_detail(ticket)})


class PlatformTicketRepliesView(APIView):
    """Append a reply to a ticket."""

    permission_classes = [IsPlatformAdmin]
    authentication_classes = [PlatformAdminAuthentication]

    @extend_schema(tags=["Platform Admin"], responses=OpenApiTypes.OBJECT)
    def post(self, request, ticket_id):
        data = request.data if isinstance(request.data, dict) else {}
        try:
            reply = add_reply(
                ticket_id=ticket_id,
                body=data.get("body") or "",
                admin=getattr(request, "platform_admin", None),
                request=request,
            )
        except TicketNotFoundError:
            return _not_found("Ticket not found.")
        except InvalidTicketFieldError as exc:
            return _bad(str(exc))
        return Response(
            {
                "ok": True,
                "reply": {
                    "id": str(reply.id),
                    "body": reply.body,
                    "createdAt": reply.created_at.isoformat() if reply.created_at else "",
                },
            },
            status=201,
        )


class PlatformKycView(APIView):
    """KYC review for a single merchant."""

    permission_classes = [IsPlatformAdmin]
    authentication_classes = [PlatformAdminAuthentication]

    @extend_schema(tags=["Platform Admin"], responses=OpenApiTypes.OBJECT)
    def get(self, request, merchant_id):
        review = get_or_create_kyc(merchant_id)
        if review is None:
            return _not_found("Merchant not found.")
        return Response({"ok": True, "kyc": project_kyc(review)})

    @extend_schema(tags=["Platform Admin"], responses=OpenApiTypes.OBJECT)
    def patch(self, request, merchant_id):
        data = request.data if isinstance(request.data, dict) else {}
        try:
            review = update_kyc(
                merchant_id=merchant_id,
                admin=getattr(request, "platform_admin", None),
                request=request,
                status=data.get("status"),
                level=data.get("level"),
                notes=data.get("notes"),
                flags=data.get("flags") if "flags" in data else None,
                documents=data.get("documents") if "documents" in data else None,
            )
        except KycNotFoundError:
            return _not_found("Merchant not found.")
        except InvalidTicketFieldError as exc:
            return _bad(str(exc))
        return Response({"ok": True, "kyc": project_kyc(review)})


__all__ = [
    "PlatformTicketsView",
    "PlatformTicketDetailView",
    "PlatformTicketRepliesView",
    "PlatformKycView",
]
