"""Customer-portal REST views.

The portal is consumed by the customer (not the merchant). Authentication is
via the :class:`PortalSessionAuthentication` Bearer-style scheme. The session
constrains what is visible (one customer's data) and what is callable
(``allowed_actions``).

Endpoints (all under /api/v1/portal/):

  GET  context              -> session metadata, customer, subs, invoices
  GET  invoices             -> the customer's invoices
  GET  payment-methods      -> the customer's payment methods (no token)
  POST payment-methods      -> attach a new payment method
  POST payment-methods/<id>/set-default
  POST invoices/<id>/pay    -> charge the (default) payment method
  POST subscriptions/<id>/cancel -> schedule or perform customer cancellation
"""
from __future__ import annotations

from django.shortcuts import get_object_or_404
from django.http import HttpResponse
from drf_spectacular.utils import OpenApiTypes, extend_schema
from rest_framework import status
from rest_framework.permissions import BasePermission
from rest_framework.renderers import BaseRenderer
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.invoices.models import Invoice
from apps.invoices.serializers import InvoiceSerializer
from apps.invoices.services.delivery import build_invoice_pdf
from apps.payments.services import charge_invoice as charge_invoice_service
from apps.subscriptions.models import Subscription
from apps.subscriptions.serializers import CancelSubscriptionPayload, ChangePlanPayload, SubscriptionSerializer
from apps.subscriptions.services.change_plan import change_plan as change_plan_service, preview_change as preview_change_service
from apps.subscriptions.services.create_subscription import create_subscription as create_subscription_service
from apps.subscriptions.services.activate_subscription import activate_subscription as activate_subscription_service
from apps.subscriptions.services.lifecycle import cancel_subscription as cancel_subscription_service
from apps.catalog.models import Plan
from apps.catalog.selectors import active_price_version
from apps.common.exceptions import ServiceError

from .models import Customer, PaymentMethod, PortalSession
from .portal_auth import PortalSessionAuthentication
from .serializers import (
    AttachPaymentMethodPayload,
    CustomerSerializer,
    PaymentMethodSerializer,
    PortalSessionSerializer,
)
from .services.payment_methods import attach_payment_method, set_default_payment_method


class HasPortalAction(BasePermission):
    """Require the resolved portal session to permit a specific action."""

    required_action = ""

    def has_permission(self, request, view):
        session: PortalSession | None = getattr(request, "portal_session", None)
        required = getattr(view, "portal_action", "") or self.required_action
        if session is None:
            return False
        if not required:
            return True
        return required in (session.allowed_actions or [])


class _PortalView(APIView):
    authentication_classes = [PortalSessionAuthentication]
    permission_classes = [HasPortalAction]
    portal_action = ""


class PdfRenderer(BaseRenderer):
    media_type = "application/pdf"
    format = "pdf"
    charset = None
    render_style = "binary"

    def render(self, data, accepted_media_type=None, renderer_context=None):
        return data


class PortalContextView(_PortalView):
    portal_action = "view_subscriptions"

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request):
        session: PortalSession = request.portal_session
        customer = session.customer
        subs_qs = customer.subscriptions.all().order_by("-created_at")
        invoices_qs = customer.invoices.all().order_by("-created_at")[:25]
        from apps.subscriptions.serializers import SubscriptionSerializer

        return Response(
            {
                "session": PortalSessionSerializer(session).data,
                "customer": CustomerSerializer(customer).data,
                "subscriptions": SubscriptionSerializer(subs_qs, many=True).data,
                "invoices": InvoiceSerializer(invoices_qs, many=True).data,
                "payment_methods": PaymentMethodSerializer(
                    customer.payment_methods.exclude(status=PaymentMethod.Status.REVOKED),
                    many=True,
                ).data,
                "merchant": self._merchant_settings(session),
                "allowed_actions": session.allowed_actions or [],
            }
        )

    def _merchant_settings(self, session: PortalSession) -> dict:
        merchant = session.merchant
        metadata = merchant.metadata or {}
        org_meta = metadata.get("org") if isinstance(metadata.get("org"), dict) else {}
        settings = metadata.get("settings") if isinstance(metadata.get("settings"), dict) else {}
        branding = settings.get("branding") if isinstance(settings.get("branding"), dict) else {}
        portal = settings.get("portal") if isinstance(settings.get("portal"), dict) else {}
        return {
            "name": org_meta.get("trading_name") or merchant.name,
            "legal_name": org_meta.get("legal_name") or merchant.name,
            "brand_color": branding.get("primary_color") or org_meta.get("brand_color") or "#056058",
            "logo_url": branding.get("logo_url") or branding.get("logo_data") or None,
            "portal_subdomain": branding.get("portal_subdomain") or org_meta.get("portal_subdomain") or merchant.slug,
            "allow_cancel": portal.get("allow_cancel", True),
            "allow_pause": portal.get("allow_pause", True),
            "allow_change_plan": portal.get("allow_change_plan", True),
            "allow_subscribe": portal.get("allow_subscribe", True),
            "success_url": portal.get("success_url") or "",
            "cancel_url": portal.get("cancel_url") or "",
        }


class PortalInvoicesView(_PortalView):
    portal_action = "view_invoices"
    serializer_class = InvoiceSerializer

    def get(self, request):
        customer: Customer = request.portal_session.customer
        qs = customer.invoices.all().order_by("-created_at")
        return Response(InvoiceSerializer(qs, many=True).data)


class PortalPaymentMethodsView(_PortalView):
    portal_action = "update_payment_method"
    serializer_class = PaymentMethodSerializer

    def get(self, request):
        customer: Customer = request.portal_session.customer
        qs = customer.payment_methods.exclude(status=PaymentMethod.Status.REVOKED)
        return Response(PaymentMethodSerializer(qs, many=True).data)

    def post(self, request):
        customer: Customer = request.portal_session.customer
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
            set_default=s.validated_data.get("set_default", True),
            metadata=s.validated_data.get("metadata") or {},
            request=request,
        )
        return Response(PaymentMethodSerializer(pm).data, status=status.HTTP_201_CREATED)


class PortalSetDefaultPaymentMethodView(_PortalView):
    portal_action = "update_payment_method"
    serializer_class = PaymentMethodSerializer

    def post(self, request, pm_id: str):
        customer: Customer = request.portal_session.customer
        pm = get_object_or_404(PaymentMethod, id=pm_id, customer=customer)
        pm = set_default_payment_method(
            customer=customer, payment_method=pm, request=request
        )
        return Response(PaymentMethodSerializer(pm).data)


class PortalPayInvoiceView(_PortalView):
    portal_action = "pay_invoice"

    @extend_schema(request=None, responses=OpenApiTypes.OBJECT)
    def post(self, request, invoice_id: str):
        customer: Customer = request.portal_session.customer
        invoice = get_object_or_404(Invoice, id=invoice_id, customer=customer)
        outcome = charge_invoice_service(invoice=invoice, request=request)
        return Response(
            {
                "invoice": InvoiceSerializer(invoice).data,
                "success": outcome.result.success,
                "failure_code": outcome.result.failure_code,
                "failure_category": outcome.result.failure_category,
            },
            status=status.HTTP_200_OK if outcome.result.success else status.HTTP_402_PAYMENT_REQUIRED,
        )


class PortalInvoicePdfView(_PortalView):
    portal_action = "view_invoices"
    renderer_classes = [PdfRenderer]

    @extend_schema(responses=OpenApiTypes.BINARY)
    def get(self, request, invoice_id: str):
        customer: Customer = request.portal_session.customer
        invoice = get_object_or_404(Invoice, id=invoice_id, customer=customer)
        response = HttpResponse(build_invoice_pdf(invoice), content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{invoice.number}.pdf"'
        return response


class PortalCancelSubscriptionView(_PortalView):
    portal_action = "cancel_subscription"
    serializer_class = SubscriptionSerializer

    @extend_schema(request=CancelSubscriptionPayload, responses=SubscriptionSerializer)
    def post(self, request, subscription_id: str):
        customer: Customer = request.portal_session.customer
        subscription = get_object_or_404(
            Subscription, id=subscription_id, customer=customer
        )
        s = CancelSubscriptionPayload(data=request.data)
        s.is_valid(raise_exception=True)
        subscription = cancel_subscription_service(
            subscription=subscription,
            at_period_end=s.validated_data["at_period_end"],
            reason=s.validated_data.get("reason", "Cancelled from customer portal"),
            request=request,
        )
        return Response(SubscriptionSerializer(subscription).data)


def _serialize_portal_plan(plan: Plan) -> dict:
    pv = active_price_version(plan)
    return {
        "id": str(plan.id),
        "name": plan.name,
        "description": plan.description or "",
        "product_name": plan.product.name if plan.product_id else "",
        "trial_days": plan.trial_days,
        "amount_minor": pv.amount_minor if pv else 0,
        "currency": pv.currency if pv else "",
        "interval_unit": pv.interval_unit if pv else "",
        "interval_count": pv.interval_count if pv else 1,
        "features": [
            {"label": f.label, "detail": f.detail}
            for f in plan.features.all().order_by("sort_order", "label")
        ],
    }


class PortalPlansView(_PortalView):
    """Available plans the customer can switch to (gated by allow_change_plan)."""

    portal_action = "change_plan"

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request):
        session: PortalSession = request.portal_session
        plans = (
            Plan.objects.filter(
                merchant=session.merchant,
                environment=session.environment,
                status=Plan.Status.ACTIVE,
            )
            .select_related("product")
            .prefetch_related("features", "price_versions")
            .order_by("product__name", "name")
        )
        current_plan_id = None
        active_sub = (
            session.customer.subscriptions.exclude(
                status__in=[Subscription.Status.CANCELED, Subscription.Status.EXPIRED]
            )
            .order_by("-created_at")
            .first()
        )
        if active_sub is not None:
            current_plan_id = str(active_sub.plan_id)
        return Response(
            {
                "current_plan_id": current_plan_id,
                "plans": [_serialize_portal_plan(p) for p in plans],
            }
        )


class PortalPreviewChangePlanView(_PortalView):
    portal_action = "change_plan"

    @extend_schema(request=ChangePlanPayload, responses=OpenApiTypes.OBJECT)
    def post(self, request, subscription_id: str):
        customer: Customer = request.portal_session.customer
        subscription = get_object_or_404(
            Subscription, id=subscription_id, customer=customer
        )
        s = ChangePlanPayload(data=request.data)
        s.is_valid(raise_exception=True)
        new_plan = get_object_or_404(
            Plan,
            id=s.validated_data["new_plan_id"],
            merchant=request.merchant,
            environment=request.environment,
            status=Plan.Status.ACTIVE,
        )
        try:
            preview = preview_change_service(subscription=subscription, new_plan=new_plan)
        except ServiceError as exc:
            return Response({"reason": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(preview.to_dict())


class PortalChangePlanView(_PortalView):
    portal_action = "change_plan"
    serializer_class = SubscriptionSerializer

    @extend_schema(request=ChangePlanPayload, responses=OpenApiTypes.OBJECT)
    def post(self, request, subscription_id: str):
        customer: Customer = request.portal_session.customer
        subscription = get_object_or_404(
            Subscription, id=subscription_id, customer=customer
        )
        if subscription.status not in {
            Subscription.Status.ACTIVE,
            Subscription.Status.TRIALING,
            Subscription.Status.PAST_DUE,
        }:
            return Response(
                {"reason": "This subscription is not eligible for plan changes."},
                status=status.HTTP_409_CONFLICT,
            )
        s = ChangePlanPayload(data=request.data)
        s.is_valid(raise_exception=True)
        new_plan = get_object_or_404(
            Plan,
            id=s.validated_data["new_plan_id"],
            merchant=request.merchant,
            environment=request.environment,
            status=Plan.Status.ACTIVE,
        )
        if str(new_plan.id) == str(subscription.plan_id):
            return Response(
                {"reason": "This is already the active plan."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            subscription, preview = change_plan_service(
                subscription=subscription,
                new_plan=new_plan,
                actor_user=None,
                request=request,
            )
        except ServiceError as exc:
            return Response({"reason": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        # Portal-namespaced audit row so the customer's email is on the trail.
        from apps.audit.services.log_event import log_event

        log_event(
            action="portal.subscription_plan_changed",
            actor_label=customer.email,
            actor_role="customer_portal",
            merchant=subscription.merchant,
            environment=subscription.environment,
            target_type="subscription",
            target_id=str(subscription.id),
            metadata=preview.to_dict(),
            request=request,
        )
        return Response(
            {
                "subscription": SubscriptionSerializer(subscription).data,
                "preview": preview.to_dict(),
            }
        )


class PortalSubscribeView(_PortalView):
    """Customer self-service subscribe to a plan from the portal.

    Creates the subscription via ``create_subscription`` then activates it
    (with trial if the plan defines one) so it shows up immediately. Refuses
    if the customer already has a non-terminal subscription — plan changes
    must go through ``PortalChangePlanView`` instead.
    """

    portal_action = "subscribe"

    @extend_schema(request=OpenApiTypes.OBJECT, responses=OpenApiTypes.OBJECT)
    def post(self, request):
        session: PortalSession = request.portal_session
        customer: Customer = session.customer
        plan_id = (request.data or {}).get("plan_id")
        if not plan_id:
            return Response(
                {"reason": "plan_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        existing = (
            customer.subscriptions.exclude(
                status__in=[
                    Subscription.Status.CANCELED,
                    Subscription.Status.EXPIRED,
                ]
            )
            .order_by("-created_at")
            .first()
        )
        if existing is not None:
            return Response(
                {
                    "reason": (
                        "You already have an active subscription. "
                        "Use change plan to switch."
                    )
                },
                status=status.HTTP_409_CONFLICT,
            )
        plan = get_object_or_404(
            Plan,
            id=plan_id,
            merchant=session.merchant,
            environment=session.environment,
            status=Plan.Status.ACTIVE,
        )
        default_pm = (
            customer.payment_methods.exclude(status=PaymentMethod.Status.REVOKED)
            .order_by("-is_default", "-created_at")
            .first()
        )
        try:
            subscription = create_subscription_service(
                merchant=session.merchant,
                environment=session.environment,
                customer=customer,
                plan=plan,
                quantity=1,
                default_payment_method=default_pm,
                metadata={"source": "customer_portal"},
                actor_user=None,
                request=request,
            )
            subscription = activate_subscription_service(
                subscription=subscription,
                with_trial=plan.trial_days > 0,
                actor_user=None,
                request=request,
            )
        except ServiceError as exc:
            return Response({"reason": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        # Portal-namespaced audit row so the customer's email is on the trail.
        from apps.audit.services.log_event import log_event

        log_event(
            action="portal.subscription_created",
            actor_label=customer.email,
            actor_role="customer_portal",
            merchant=subscription.merchant,
            environment=subscription.environment,
            target_type="subscription",
            target_id=str(subscription.id),
            metadata={
                "plan_id": str(plan.id),
                "plan_name": plan.name,
                "with_trial": plan.trial_days > 0,
            },
            request=request,
        )
        return Response(
            {"subscription": SubscriptionSerializer(subscription).data},
            status=status.HTTP_201_CREATED,
        )
