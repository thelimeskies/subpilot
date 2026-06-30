"""Subscriptions REST views."""
from __future__ import annotations

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.permissions import HasCapability
from apps.catalog.models import Plan
from apps.common.permissions import HasTenantContext
from apps.common.viewsets import TenantScopedViewSet
from apps.customers.models import Customer, PaymentMethod

from .models import Subscription
from .selectors import events_for, subscriptions_for
from .serializers import (
    AddSubscriptionNotePayload,
    ApplySubscriptionCreditPayload,
    ActivateSubscriptionPayload,
    CancelSubscriptionPayload,
    ChangePlanPayload,
    CreateSubscriptionPayload,
    PauseSubscriptionPayload,
    SetSubscriptionPaymentMethodPayload,
    SubscriptionEventSerializer,
    SubscriptionSerializer,
)
from .services.activate_subscription import activate_subscription
from .services.change_plan import change_plan, preview_change
from .services.create_subscription import create_subscription
from .services.credits import apply_subscription_credit
from .services.lifecycle import (
    cancel_subscription,
    pause_subscription,
    resume_subscription,
)
from .services.notes import add_subscription_note
from .services.payment_method import set_subscription_payment_method


class SubscriptionViewSet(TenantScopedViewSet):
    serializer_class = SubscriptionSerializer
    queryset = Subscription.objects.all()
    http_method_names = ["get", "head", "options", "post"]

    def get_base_queryset(self):
        return subscriptions_for(self.request.merchant, self.request.environment)

    def get_permissions(self):
        if self.action in {"list", "retrieve", "events", "preview_change"}:
            return [IsAuthenticated(), HasTenantContext()]
        if self.action in {"pause", "resume"}:
            return [
                IsAuthenticated(),
                HasTenantContext(),
                HasCapability("pause_resume_subscription")(),
            ]
        if self.action == "set_payment_method":
            return [
                IsAuthenticated(),
                HasTenantContext(),
                HasCapability("create_payment_method_session")(),
            ]
        if self.action == "add_note":
            return [
                IsAuthenticated(),
                HasTenantContext(),
                HasCapability("pause_resume_subscription")(),
            ]
        if self.action == "apply_credit":
            return [
                IsAuthenticated(),
                HasTenantContext(),
                HasCapability("apply_credit_note")(),
            ]
        if self.action == "cancel":
            return [
                IsAuthenticated(),
                HasTenantContext(),
                HasCapability("cancel_subscription")(),
            ]
        return [
            IsAuthenticated(),
            HasTenantContext(),
            HasCapability("create_subscription")(),
        ]

    def create(self, request, *args, **kwargs):
        s = CreateSubscriptionPayload(data=request.data)
        s.is_valid(raise_exception=True)
        customer = get_object_or_404(
            Customer,
            id=s.validated_data["customer_id"],
            merchant=request.merchant,
            environment=request.environment,
        )
        plan = get_object_or_404(
            Plan,
            id=s.validated_data["plan_id"],
            merchant=request.merchant,
            environment=request.environment,
        )
        pm = None
        if s.validated_data.get("default_payment_method_id"):
            pm = get_object_or_404(
                PaymentMethod,
                id=s.validated_data["default_payment_method_id"],
                merchant=request.merchant,
                environment=request.environment,
            )
        sub = create_subscription(
            merchant=request.merchant,
            environment=request.environment,
            customer=customer,
            plan=plan,
            quantity=s.validated_data.get("quantity", 1),
            default_payment_method=pm,
            metadata=s.validated_data.get("metadata") or {},
            actor_user=request.user,
            request=request,
        )
        return Response(SubscriptionSerializer(sub).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def activate(self, request, pk=None):
        sub = self.get_object()
        s = ActivateSubscriptionPayload(data=request.data)
        s.is_valid(raise_exception=True)
        sub = activate_subscription(
            subscription=sub,
            with_trial=s.validated_data.get("with_trial", False),
            actor_user=request.user,
            request=request,
        )
        return Response(SubscriptionSerializer(sub).data)

    @action(detail=True, methods=["post"])
    def pause(self, request, pk=None):
        sub = self.get_object()
        s = PauseSubscriptionPayload(data=request.data)
        s.is_valid(raise_exception=True)
        resume_at = s.validated_data.get("resume_at")
        if resume_at and resume_at <= timezone.localdate():
            return Response(
                {"detail": "resume_at must be a future date."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        sub = pause_subscription(
            subscription=sub,
            reason=s.validated_data.get("reason", ""),
            resume_at=resume_at,
            actor_user=request.user,
            request=request,
        )
        return Response(SubscriptionSerializer(sub).data)

    @action(detail=True, methods=["post"])
    def resume(self, request, pk=None):
        sub = self.get_object()
        sub = resume_subscription(
            subscription=sub, actor_user=request.user, request=request
        )
        return Response(SubscriptionSerializer(sub).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        sub = self.get_object()
        s = CancelSubscriptionPayload(data=request.data)
        s.is_valid(raise_exception=True)
        sub = cancel_subscription(
            subscription=sub,
            at_period_end=s.validated_data.get("at_period_end", True),
            reason=s.validated_data.get("reason", ""),
            actor_user=request.user,
            request=request,
        )
        return Response(SubscriptionSerializer(sub).data)

    @action(detail=True, methods=["post"], url_path="preview-change")
    def preview_change(self, request, pk=None):
        sub = self.get_object()
        s = ChangePlanPayload(data=request.data)
        s.is_valid(raise_exception=True)
        new_plan = get_object_or_404(
            Plan,
            id=s.validated_data["new_plan_id"],
            merchant=request.merchant,
            environment=request.environment,
        )
        preview = preview_change(subscription=sub, new_plan=new_plan)
        return Response(preview.to_dict())

    @action(detail=True, methods=["post"], url_path="change-plan")
    def change_plan(self, request, pk=None):
        sub = self.get_object()
        s = ChangePlanPayload(data=request.data)
        s.is_valid(raise_exception=True)
        new_plan = get_object_or_404(
            Plan,
            id=s.validated_data["new_plan_id"],
            merchant=request.merchant,
            environment=request.environment,
        )
        sub, preview = change_plan(
            subscription=sub,
            new_plan=new_plan,
            actor_user=request.user,
            request=request,
        )
        return Response(
            {"subscription": SubscriptionSerializer(sub).data, "preview": preview.to_dict()}
        )

    @action(detail=True, methods=["post"], url_path="payment-method")
    def set_payment_method(self, request, pk=None):
        sub = self.get_object()
        s = SetSubscriptionPaymentMethodPayload(data=request.data)
        s.is_valid(raise_exception=True)
        payment_method = get_object_or_404(
            PaymentMethod,
            id=s.validated_data["payment_method_id"],
            merchant=request.merchant,
            environment=request.environment,
            customer=sub.customer,
        )
        sub = set_subscription_payment_method(
            subscription=sub,
            payment_method=payment_method,
            actor_user=request.user,
            request=request,
        )
        return Response(SubscriptionSerializer(sub).data)

    @action(detail=True, methods=["post"], url_path="notes")
    def add_note(self, request, pk=None):
        sub = self.get_object()
        s = AddSubscriptionNotePayload(data=request.data)
        s.is_valid(raise_exception=True)
        sub = add_subscription_note(
            subscription=sub,
            note=s.validated_data["note"],
            actor_user=request.user,
            request=request,
        )
        return Response(SubscriptionSerializer(sub).data)

    @action(detail=True, methods=["post"], url_path="credits")
    def apply_credit(self, request, pk=None):
        sub = self.get_object()
        s = ApplySubscriptionCreditPayload(data=request.data)
        s.is_valid(raise_exception=True)
        sub = apply_subscription_credit(
            subscription=sub,
            amount_minor=s.validated_data["amount_minor"],
            note=s.validated_data.get("note", ""),
            actor_user=request.user,
            request=request,
        )
        return Response(SubscriptionSerializer(sub).data)

    @action(detail=True, methods=["get"])
    def events(self, request, pk=None):
        sub = self.get_object()
        qs = events_for(sub)
        return Response(SubscriptionEventSerializer(qs, many=True).data)
