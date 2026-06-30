"""Invoices REST views."""
from __future__ import annotations

import csv
import uuid

from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.permissions import HasCapability
from apps.audit.services.log_event import log_event
from apps.common.permissions import HasTenantContext
from apps.common.viewsets import TenantScopedViewSet
from apps.customers.models import Customer
from apps.subscriptions.models import Subscription

from .models import Invoice
from .selectors import invoices_for
from .serializers import (
    ApplyCreditPayload,
    ApplyCreditResponseSerializer,
    CreditNoteSerializer,
    CreateInvoicePayload,
    InvoiceSerializer,
    MarkPaidPayload,
    MarkUncollectiblePayload,
    SendInvoiceReminderPayload,
    VoidInvoicePayload,
)
from .services.create_invoice import create_invoice
from .services.create_renewal_invoice import create_renewal_invoice
from .services.lifecycle import (
    apply_credit_note,
    finalize_invoice,
    mark_manual_payment,
    mark_uncollectible,
    void_invoice,
)
from .services.delivery import build_invoice_pdf, send_invoice_reminder


class InvoiceViewSet(TenantScopedViewSet):
    serializer_class = InvoiceSerializer
    queryset = Invoice.objects.all()
    http_method_names = ["get", "head", "options", "post"]

    def get_base_queryset(self):
        return invoices_for(self.request.merchant, self.request.environment)

    def get_permissions(self):
        if self.action in {"list", "retrieve"}:
            return [
                IsAuthenticated(),
                HasTenantContext(),
                HasCapability("view_dashboard")(),
            ]
        if self.action == "void":
            return [IsAuthenticated(), HasTenantContext(), HasCapability("void_invoice")()]
        if self.action == "apply_credit":
            return [
                IsAuthenticated(),
                HasTenantContext(),
                HasCapability("apply_credit_note")(),
            ]
        if self.action == "send_reminder":
            return [IsAuthenticated(), HasTenantContext(), HasCapability("retry_invoice")()]
        if self.action in {"pdf", "export"}:
            return [IsAuthenticated(), HasTenantContext(), HasCapability("export_invoices")()]
        if self.action == "uncollectible":
            return [
                IsAuthenticated(),
                HasTenantContext(),
                HasCapability("mark_uncollectible")(),
            ]
        if self.action in {"create", "renew"}:
            return [
                IsAuthenticated(),
                HasTenantContext(),
                HasCapability("create_subscription")(),
            ]
        if self.action in {"finalize", "pay"}:
            return [IsAuthenticated(), HasTenantContext(), HasCapability("retry_invoice")()]
        return [IsAuthenticated(), HasTenantContext()]

    def create(self, request, *args, **kwargs):
        s = CreateInvoicePayload(data=request.data)
        s.is_valid(raise_exception=True)
        customer = get_object_or_404(
            Customer,
            id=s.validated_data["customer_id"],
            merchant=request.merchant,
            environment=request.environment,
        )
        subscription = None
        if s.validated_data.get("subscription_id"):
            subscription = get_object_or_404(
                Subscription,
                id=s.validated_data["subscription_id"],
                merchant=request.merchant,
                environment=request.environment,
            )
        invoice = create_invoice(
            merchant=request.merchant,
            environment=request.environment,
            customer=customer,
            currency=s.validated_data["currency"],
            line_items=s.validated_data["line_items"],
            subscription=subscription,
            due_at=s.validated_data.get("due_at"),
            metadata=s.validated_data.get("metadata") or {},
            actor_user=request.user,
            request=request,
        )
        return Response(InvoiceSerializer(invoice).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def finalize(self, request, pk=None):
        inv = self.get_object()
        inv = finalize_invoice(invoice=inv, actor_user=request.user, request=request)
        return Response(InvoiceSerializer(inv).data)

    @action(detail=True, methods=["post"])
    def void(self, request, pk=None):
        inv = self.get_object()
        s = VoidInvoicePayload(data=request.data)
        s.is_valid(raise_exception=True)
        inv = void_invoice(
            invoice=inv,
            reason=s.validated_data.get("reason", ""),
            actor_user=request.user,
            request=request,
        )
        return Response(InvoiceSerializer(inv).data)

    @action(detail=True, methods=["post"])
    def uncollectible(self, request, pk=None):
        inv = self.get_object()
        s = MarkUncollectiblePayload(data=request.data)
        s.is_valid(raise_exception=True)
        inv = mark_uncollectible(
            invoice=inv,
            reason=s.validated_data.get("reason", ""),
            actor_user=request.user,
            request=request,
        )
        return Response(InvoiceSerializer(inv).data)

    @action(detail=True, methods=["post"])
    def pay(self, request, pk=None):
        inv = self.get_object()
        s = MarkPaidPayload(data=request.data)
        s.is_valid(raise_exception=True)
        inv = mark_manual_payment(
            invoice=inv,
            paid_amount_minor=s.validated_data.get("paid_amount_minor"),
            paid_at=s.validated_data.get("paid_at"),
            actor_user=request.user,
            request=request,
        )
        return Response(InvoiceSerializer(inv).data)

    @action(detail=True, methods=["post"], url_path="apply-credit")
    def apply_credit(self, request, pk=None):
        inv = self.get_object()
        s = ApplyCreditPayload(data=request.data)
        s.is_valid(raise_exception=True)
        inv, credit_note = apply_credit_note(
            invoice=inv,
            amount_minor=s.validated_data["amount_minor"],
            reason=s.validated_data.get("reason", "other"),
            note=s.validated_data.get("note", ""),
            actor_user=request.user,
            request=request,
        )
        return Response(
            {
                "invoice": InvoiceSerializer(inv).data,
                "credit_note": CreditNoteSerializer(credit_note).data,
            }
        )

    @action(detail=True, methods=["post"], url_path="send-reminder")
    def send_reminder(self, request, pk=None):
        inv = self.get_object()
        s = SendInvoiceReminderPayload(data=request.data)
        s.is_valid(raise_exception=True)
        result = send_invoice_reminder(
            invoice=inv,
            channel=s.validated_data["channel"],
            message=s.validated_data["message"],
            actor_user=request.user,
            request=request,
        )
        return Response(result, status=status.HTTP_202_ACCEPTED)

    @action(detail=True, methods=["get"], url_path="pdf")
    def pdf(self, request, pk=None):
        inv = self.get_object()
        response = HttpResponse(build_invoice_pdf(inv), content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{inv.number}.pdf"'
        return response

    @action(detail=False, methods=["get"], url_path="export")
    def export(self, request):
        qs = self._export_queryset(request)
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="subpilot-invoices.csv"'
        writer = csv.writer(response)
        writer.writerow(
            [
                "invoice_id",
                "number",
                "customer_name",
                "customer_email",
                "status",
                "currency",
                "subtotal_minor",
                "total_minor",
                "amount_due_minor",
                "amount_paid_minor",
                "due_at",
                "paid_at",
                "created_at",
            ]
        )
        count = 0
        for invoice in qs:
            amount_paid_minor = max(0, invoice.total_minor - invoice.amount_due_minor)
            writer.writerow(
                [
                    str(invoice.id),
                    invoice.number,
                    invoice.customer.name,
                    invoice.customer.email,
                    self._export_status(invoice),
                    invoice.currency,
                    invoice.subtotal_minor,
                    invoice.total_minor,
                    invoice.amount_due_minor,
                    amount_paid_minor,
                    invoice.due_at.isoformat() if invoice.due_at else "",
                    invoice.paid_at.isoformat() if invoice.paid_at else "",
                    invoice.created_at.isoformat() if invoice.created_at else "",
                ]
            )
            count += 1

        log_event(
            action="invoices.exported",
            actor_user=request.user,
            merchant=request.merchant,
            environment=request.environment,
            target_type="invoice_export",
            target_id="csv",
            metadata={
                "row_count": count,
                "status": request.query_params.get("status", ""),
                "query": request.query_params.get("q", ""),
            },
            request=request,
        )
        return response

    def _export_queryset(self, request):
        qs = self.get_base_queryset().select_related("customer", "subscription").order_by("-created_at")
        status_param = (request.query_params.get("status") or "").strip()
        now = timezone.now()
        if status_param and status_param != "all":
            if status_param == "past_due":
                qs = qs.filter(status=Invoice.Status.OPEN, due_at__lt=now)
            elif status_param == "open":
                qs = qs.filter(status=Invoice.Status.OPEN).filter(Q(due_at__isnull=True) | Q(due_at__gte=now))
            else:
                qs = qs.filter(status=status_param)

        query = (request.query_params.get("q") or "").strip()
        if query:
            query_filter = (
                Q(number__icontains=query)
                | Q(customer__name__icontains=query)
                | Q(customer__email__icontains=query)
            )
            try:
                query_filter |= Q(id=uuid.UUID(query))
            except ValueError:
                pass
            qs = qs.filter(query_filter)
        return qs[:5000]

    def _export_status(self, invoice: Invoice) -> str:
        if (
            invoice.status == Invoice.Status.OPEN
            and invoice.due_at
            and invoice.due_at < timezone.now()
        ):
            return "past_due"
        return invoice.status

    @action(
        detail=False,
        methods=["post"],
        url_path=r"renew/(?P<subscription_id>[0-9a-f-]+)",
    )
    def renew(self, request, subscription_id=None):
        subscription = get_object_or_404(
            Subscription,
            id=subscription_id,
            merchant=request.merchant,
            environment=request.environment,
        )
        inv = create_renewal_invoice(
            subscription=subscription,
            actor_user=request.user,
            request=request,
        )
        return Response(InvoiceSerializer(inv).data, status=status.HTTP_201_CREATED)
