"""Customers REST views: Customer, PaymentMethod, PortalSession."""
from __future__ import annotations

from datetime import timedelta

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.permissions import HasCapability
from apps.accounts.services.features import disabled_response, get_flag
from apps.audit.services.log_event import log_event
from apps.common.exceptions import TenantMismatch
from apps.common.permissions import HasTenantContext
from apps.common.viewsets import TenantScopedViewSet

from .models import Customer, PaymentMethod, PortalSession
from .selectors import customers_for, payment_methods_for, portal_sessions_for
from .serializers import (
    AttachPaymentMethodPayload,
    CreateCustomerPayload,
    CreatePortalSessionPayload,
    CustomerSerializer,
    MergeCustomerPayload,
    PaymentMethodSerializer,
    PortalSessionCreateResponseSerializer,
    PortalSessionSerializer,
    UpdateCustomerPayload,
)
from .services.create_customer import create_customer
from .services.create_portal_session import (
    create_portal_session,
    portal_session_url,
    send_customer_blocked_email,
    send_portal_session_email,
)
from .services.payment_methods import attach_payment_method, set_default_payment_method


class CustomerViewSet(TenantScopedViewSet):
    serializer_class = CustomerSerializer
    queryset = Customer.objects.all()

    def get_base_queryset(self):
        return customers_for(self.request.merchant, self.request.environment)

    def get_permissions(self):
        if self.action in {"list", "retrieve"}:
            return [IsAuthenticated(), HasTenantContext(), HasCapability("view_customers")()]
        if self.action == "payment_methods":
            if self.request.method == "GET":
                return [
                    IsAuthenticated(),
                    HasTenantContext(),
                    HasCapability("view_payment_methods_masked")(),
                ]
            return [
                IsAuthenticated(),
                HasTenantContext(),
                HasCapability("create_payment_method_session")(),
            ]
        return [IsAuthenticated(), HasTenantContext(), HasCapability("create_customer")()]

    def create(self, request, *args, **kwargs):
        s = CreateCustomerPayload(data=request.data)
        s.is_valid(raise_exception=True)
        customer = create_customer(
            merchant=request.merchant,
            environment=request.environment,
            email=s.validated_data["email"],
            name=s.validated_data.get("name", ""),
            phone=s.validated_data.get("phone", ""),
            external_id=s.validated_data.get("external_id", ""),
            metadata=s.validated_data.get("metadata") or {},
            actor_user=request.user,
            request=request,
        )
        return Response(CustomerSerializer(customer).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        return self._update_customer(request)

    def partial_update(self, request, *args, **kwargs):
        return self._update_customer(request)

    @action(detail=True, methods=["post"], url_path="archive")
    def archive(self, request, pk=None):
        customer = self.get_object()
        from apps.subscriptions.models import Subscription
        from apps.subscriptions.services.lifecycle import pause_subscription

        with transaction.atomic():
            customer = (
                Customer.objects.select_for_update()
                .filter(
                    id=customer.id,
                    merchant=request.merchant,
                    environment=request.environment,
                )
                .get()
            )
            pauseable = (
                Subscription.objects.select_for_update()
                .filter(
                    customer=customer,
                    status__in=[
                        Subscription.Status.ACTIVE,
                        Subscription.Status.TRIALING,
                        Subscription.Status.PAST_DUE,
                    ],
                )
                .order_by("created_at")
            )
            paused_count = 0
            for subscription in pauseable:
                pause_subscription(
                    subscription=subscription,
                    reason="Customer blocked from merchant dashboard",
                    actor_user=request.user,
                    request=request,
                )
                paused_count += 1
            customer.status = Customer.Status.ARCHIVED
            customer.save(update_fields=["status", "updated_at"])
        self._log_customer_event(request, customer, "customers.customer_archived")
        send_customer_blocked_email(
            customer=customer,
            paused_subscription_count=paused_count,
            actor_user=request.user,
            request=request,
        )
        body = CustomerSerializer(customer).data
        body["paused_subscriptions"] = paused_count
        body["email_sent"] = True
        return Response(body)

    @action(detail=True, methods=["post"], url_path="reactivate")
    def reactivate(self, request, pk=None):
        customer = self.get_object()
        customer.status = Customer.Status.ACTIVE
        customer.save(update_fields=["status", "updated_at"])
        self._log_customer_event(request, customer, "customers.customer_reactivated")
        return Response(CustomerSerializer(customer).data)

    @action(detail=True, methods=["post"], url_path="merge")
    def merge(self, request, pk=None):
        source = self.get_object()
        s = MergeCustomerPayload(data=request.data or {})
        s.is_valid(raise_exception=True)
        target = get_object_or_404(
            Customer,
            id=s.validated_data["target_customer_id"],
            merchant=request.merchant,
            environment=request.environment,
        )
        if target.id == source.id:
            return Response(
                {"detail": "Choose a different target customer."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from apps.invoices.models import Invoice
        from apps.subscriptions.models import Subscription

        with transaction.atomic():
            source = (
                Customer.objects.select_for_update()
                .filter(id=source.id, merchant=request.merchant, environment=request.environment)
                .get()
            )
            target = (
                Customer.objects.select_for_update()
                .filter(id=target.id, merchant=request.merchant, environment=request.environment)
                .get()
            )

            subscription_count = Subscription.objects.filter(customer=source).update(customer=target)
            invoice_count = Invoice.objects.filter(customer=source).update(customer=target)
            portal_session_count = PortalSession.objects.filter(customer=source).update(customer=target)

            source_methods = PaymentMethod.objects.select_for_update().filter(customer=source)
            payment_method_count = source_methods.count()
            target_has_default = PaymentMethod.objects.filter(
                customer=target,
                status=PaymentMethod.Status.ACTIVE,
                is_default=True,
            ).exists()
            if target_has_default:
                source_methods.filter(
                    status=PaymentMethod.Status.ACTIVE,
                    is_default=True,
                ).update(is_default=False)
            source_methods.update(customer=target)

            source_metadata = dict(source.metadata or {})
            source_metadata["merged_into_customer_id"] = str(target.id)
            source_metadata["merged_into_customer_email"] = target.email
            source_metadata["merged_at"] = timezone.now().isoformat()
            source.status = Customer.Status.ARCHIVED
            source.metadata = source_metadata
            source.save(update_fields=["status", "metadata", "updated_at"])

        log_event(
            action="customers.customer_merged",
            actor_user=request.user,
            merchant=request.merchant,
            environment=request.environment,
            target_type="customer",
            target_id=str(target.id),
            metadata={
                "source_customer_id": str(source.id),
                "source_customer_email": source.email,
                "target_customer_id": str(target.id),
                "target_customer_email": target.email,
                "counts": {
                    "subscriptions": subscription_count,
                    "invoices": invoice_count,
                    "payment_methods": payment_method_count,
                    "portal_sessions": portal_session_count,
                },
            },
            request=request,
        )

        return Response(
            {
                "ok": True,
                "source_customer_id": str(source.id),
                "target_customer_id": str(target.id),
                "counts": {
                    "subscriptions": subscription_count,
                    "invoices": invoice_count,
                    "payment_methods": payment_method_count,
                    "portal_sessions": portal_session_count,
                },
                "target": CustomerSerializer(target).data,
            }
        )

    @action(
        detail=True,
        methods=["get", "post"],
        url_path="payment-methods",
        url_name="payment-methods",
    )
    def payment_methods(self, request, pk=None):
        customer = self.get_object()
        if request.method == "GET":
            qs = payment_methods_for(customer)
            return Response(PaymentMethodSerializer(qs, many=True).data)
        # Feature-flag gate (S13). ``tokenized_cards`` defaults on; admins can
        # disable per-merchant from the platform-admin Config sheet.
        if not get_flag(request.merchant, "tokenized_cards"):
            return disabled_response("tokenized_cards")
        s = AttachPaymentMethodPayload(data=request.data)
        s.is_valid(raise_exception=True)
        pm = attach_payment_method(
            customer=customer,
            provider=s.validated_data["provider"],
            token=s.validated_data["token"],
            brand=s.validated_data.get("brand", ""),
            last4=s.validated_data.get("last4", ""),
            exp_month=s.validated_data.get("exp_month"),
            exp_year=s.validated_data.get("exp_year"),
            fingerprint=s.validated_data.get("fingerprint", ""),
            set_default=s.validated_data.get("set_default", False),
            metadata=s.validated_data.get("metadata") or {},
            actor_user=request.user,
            request=request,
        )
        return Response(PaymentMethodSerializer(pm).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"], url_path="portal-sessions")
    def portal_sessions(self, request, pk=None):
        customer = self.get_object()
        qs = portal_sessions_for(customer)
        return Response(PortalSessionSerializer(qs, many=True).data)

    @action(
        detail=True,
        methods=["post"],
        url_path="portal-sessions",
        url_name="create-portal-session",
    )
    def create_portal_session(self, request, pk=None):
        for perm in [HasCapability("create_payment_method_session")()]:
            if not perm.has_permission(request, self):
                self.permission_denied(request, message=getattr(perm, "message", None))
        customer = self.get_object()
        s = CreatePortalSessionPayload(data=request.data)
        s.is_valid(raise_exception=True)

        subscription = None
        if s.validated_data.get("subscription_id"):
            from apps.subscriptions.models import Subscription  # local import: avoid cycles

            subscription = get_object_or_404(
                Subscription,
                id=s.validated_data["subscription_id"],
                merchant=request.merchant,
                environment=request.environment,
            )

        invoice = None
        if s.validated_data.get("invoice_id"):
            from apps.invoices.models import Invoice  # local import: avoid cycles

            invoice = get_object_or_404(
                Invoice,
                id=s.validated_data["invoice_id"],
                merchant=request.merchant,
                environment=request.environment,
            )

        ttl = None
        if s.validated_data.get("ttl_minutes") is not None:
            ttl = timedelta(minutes=s.validated_data["ttl_minutes"])

        kwargs = dict(
            customer=customer,
            subscription=subscription,
            invoice=invoice,
            allowed_actions=self._portal_allowed_actions(
                request.merchant,
                s.validated_data.get("allowed_actions"),
            ),
            return_url=s.validated_data.get("return_url", ""),
            actor_user=request.user,
            request=request,
        )
        if ttl is not None:
            kwargs["ttl"] = ttl
        session, plaintext = create_portal_session(**kwargs)
        email_queued = False
        if s.validated_data.get("send_email"):
            send_portal_session_email(
                customer=customer,
                session=session,
                token=plaintext,
                actor_user=request.user,
                request=request,
            )
            email_queued = True
        body = PortalSessionCreateResponseSerializer(
            {
                "session": session,
                "token": plaintext,
                "url": portal_session_url(plaintext),
                "email_queued": email_queued,
            }
        ).data
        return Response(body, status=status.HTTP_201_CREATED)

    def _portal_allowed_actions(self, merchant, requested: list[str] | None) -> list[str]:
        defaults = [
            "view_subscriptions",
            "view_invoices",
            "update_payment_method",
            "pay_invoice",
        ]
        actions = list(requested or defaults)
        metadata = merchant.metadata or {}
        settings = metadata.get("settings") if isinstance(metadata.get("settings"), dict) else {}
        portal = settings.get("portal") if isinstance(settings.get("portal"), dict) else {}
        if portal.get("allow_cancel", True):
            if "cancel_subscription" not in actions:
                actions.append("cancel_subscription")
        else:
            actions = [action for action in actions if action != "cancel_subscription"]
        if portal.get("allow_change_plan", True):
            if "change_plan" not in actions:
                actions.append("change_plan")
        else:
            actions = [action for action in actions if action != "change_plan"]
        if portal.get("allow_subscribe", True):
            if "subscribe" not in actions:
                actions.append("subscribe")
        else:
            actions = [action for action in actions if action != "subscribe"]
        return actions

    def _update_customer(self, request):
        customer = self.get_object()
        s = UpdateCustomerPayload(data=request.data or {}, partial=True)
        s.is_valid(raise_exception=True)
        data = s.validated_data
        update_fields = []
        for field in ("email", "name", "phone", "external_id", "status"):
            if field in data:
                value = data[field]
                if field == "email":
                    value = value.strip().lower()
                setattr(customer, field, value)
                update_fields.append(field)
        if "metadata" in data:
            metadata = dict(customer.metadata or {})
            metadata.update(data["metadata"] or {})
            customer.metadata = metadata
            update_fields.append("metadata")
        if update_fields:
            update_fields.append("updated_at")
            customer.save(update_fields=update_fields)
            self._log_customer_event(request, customer, "customers.customer_updated")
        return Response(CustomerSerializer(customer).data)

    def _log_customer_event(self, request, customer: Customer, action_name: str) -> None:
        log_event(
            action=action_name,
            actor_user=request.user,
            merchant=request.merchant,
            environment=request.environment,
            target_type="customer",
            target_id=str(customer.id),
            metadata={"email": customer.email, "status": customer.status},
            request=request,
        )


class PaymentMethodViewSet(TenantScopedViewSet):
    serializer_class = PaymentMethodSerializer
    queryset = PaymentMethod.objects.all()
    http_method_names = ["get", "head", "options", "post"]

    def get_base_queryset(self):
        return PaymentMethod.objects.filter(
            merchant=self.request.merchant, environment=self.request.environment
        ).select_related("customer")

    def get_permissions(self):
        if self.action in {"list", "retrieve"}:
            return [
                IsAuthenticated(),
                HasTenantContext(),
                HasCapability("view_payment_methods_masked")(),
            ]
        return [
            IsAuthenticated(),
            HasTenantContext(),
            HasCapability("create_payment_method_session")(),
        ]

    @action(detail=True, methods=["post"], url_path="set-default")
    def set_default(self, request, pk=None):
        pm = self.get_object()
        pm = set_default_payment_method(
            customer=pm.customer,
            payment_method=pm,
            actor_user=request.user,
            request=request,
        )
        return Response(PaymentMethodSerializer(pm).data)


class PortalSessionViewSet(TenantScopedViewSet):
    """Read-only listing of portal sessions for the tenant (audit/debugging)."""

    serializer_class = PortalSessionSerializer
    queryset = PortalSession.objects.all()
    http_method_names = ["get", "head", "options"]

    def get_base_queryset(self):
        return PortalSession.objects.filter(
            merchant=self.request.merchant, environment=self.request.environment
        ).select_related("customer")

    def get_permissions(self):
        return [IsAuthenticated(), HasTenantContext(), HasCapability("view_customers")()]
