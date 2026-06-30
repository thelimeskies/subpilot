"""Dunning REST views."""
from __future__ import annotations

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.accounts.permissions import HasCapability
from apps.common.permissions import HasTenantContext
from apps.common.viewsets import TenantScopedViewSet

from .models import DunningPolicy, DunningRun
from .selectors import policies_for, runs_for
from .serializers import (
    CreateDunningPolicyPayload,
    DunningPolicySerializer,
    DunningRunSerializer,
    UpdateDunningPolicyPayload,
)
from .services import (
    cancel_dunning_run,
    create_dunning_policy,
    pause_dunning_run,
    resume_dunning_run,
    update_dunning_policy,
)


class DunningPolicyViewSet(TenantScopedViewSet):
    serializer_class = DunningPolicySerializer
    queryset = DunningPolicy.objects.all()

    def get_base_queryset(self):
        return policies_for(self.request.merchant, self.request.environment)

    def get_permissions(self):
        if self.action in {"list", "retrieve"}:
            return [
                IsAuthenticated(),
                HasTenantContext(),
                HasCapability("view_dashboard")(),
            ]
        return [
            IsAuthenticated(),
            HasTenantContext(),
            HasCapability("manage_dunning_policies")(),
        ]

    def create(self, request, *args, **kwargs):
        s = CreateDunningPolicyPayload(data=request.data)
        s.is_valid(raise_exception=True)
        policy = create_dunning_policy(
            merchant=request.merchant,
            environment=request.environment,
            actor_user=request.user,
            request=request,
            **s.validated_data,
        )
        return Response(DunningPolicySerializer(policy).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        return self._update(request, partial=False)

    def partial_update(self, request, *args, **kwargs):
        return self._update(request, partial=True)

    def _update(self, request, partial: bool):
        policy = self.get_object()
        s = UpdateDunningPolicyPayload(data=request.data, partial=partial)
        s.is_valid(raise_exception=True)
        policy = update_dunning_policy(
            policy=policy,
            actor_user=request.user,
            request=request,
            **s.validated_data,
        )
        return Response(DunningPolicySerializer(policy).data)


class DunningRunViewSet(TenantScopedViewSet):
    serializer_class = DunningRunSerializer
    queryset = DunningRun.objects.all()
    http_method_names = ["get", "head", "options", "post"]

    def get_base_queryset(self):
        return runs_for(self.request.merchant, self.request.environment)

    def get_permissions(self):
        if self.action in {"list", "retrieve"}:
            return [
                IsAuthenticated(),
                HasTenantContext(),
                HasCapability("view_dashboard")(),
            ]
        return [
            IsAuthenticated(),
            HasTenantContext(),
            HasCapability("manage_dunning_policies")(),
        ]

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        run = self.get_object()
        reason = (request.data or {}).get("reason", "")
        run = cancel_dunning_run(
            run=run, reason=reason, actor_user=request.user, request=request
        )
        return Response(DunningRunSerializer(run).data)

    @action(detail=True, methods=["post"])
    def pause(self, request, pk=None):
        run = self.get_object()
        reason = (request.data or {}).get("reason", "")
        paused_until_raw = (request.data or {}).get("paused_until")
        paused_until = None
        if paused_until_raw:
            paused_until = parse_datetime(str(paused_until_raw))
            if paused_until is None:
                return Response(
                    {"detail": "paused_until must be an ISO-8601 datetime."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if timezone.is_naive(paused_until):
                paused_until = timezone.make_aware(paused_until, timezone.get_current_timezone())
            if paused_until <= timezone.now():
                return Response(
                    {"detail": "paused_until must be in the future."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        run = pause_dunning_run(
            run=run,
            reason=reason,
            paused_until=paused_until,
            actor_user=request.user,
            request=request,
        )
        return Response(DunningRunSerializer(run).data)

    @action(detail=True, methods=["post"])
    def resume(self, request, pk=None):
        run = self.get_object()
        run = resume_dunning_run(run=run, actor_user=request.user, request=request)
        return Response(DunningRunSerializer(run).data)
