"""Events REST views: webhook endpoints, event log, deliveries, replay."""
from __future__ import annotations

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.permissions import HasCapability
from apps.common.permissions import HasTenantContext
from apps.common.viewsets import TenantScopedViewSet

from .models import WebhookDelivery, WebhookEndpoint, WebhookEvent
from .selectors import list_deliveries, list_endpoints, list_events
from .serializers import (
    CreateWebhookEndpointPayload,
    UpdateWebhookEndpointPayload,
    WebhookDeliverySerializer,
    WebhookEndpointSerializer,
    WebhookEventSerializer,
)
from .services import (
    create_webhook_endpoint,
    replay_event,
    retry_delivery,
    rotate_webhook_secret,
    update_webhook_endpoint,
)


class WebhookEndpointViewSet(TenantScopedViewSet):
    serializer_class = WebhookEndpointSerializer
    queryset = WebhookEndpoint.objects.all()

    def get_base_queryset(self):
        return list_endpoints(merchant=self.request.merchant, environment=self.request.environment)

    def get_permissions(self):
        if self.action in {"list", "retrieve"}:
            return [IsAuthenticated(), HasTenantContext(), HasCapability("view_event_logs")()]
        return [IsAuthenticated(), HasTenantContext(), HasCapability("manage_webhook_endpoints")()]

    def create(self, request, *args, **kwargs):
        s = CreateWebhookEndpointPayload(data=request.data)
        s.is_valid(raise_exception=True)
        endpoint, secret = create_webhook_endpoint(
            merchant=request.merchant,
            environment=request.environment,
            actor_user=request.user,
            request=request,
            **s.validated_data,
        )
        return Response(
            {
                "endpoint": WebhookEndpointSerializer(endpoint).data,
                "secret": secret,
            },
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        return self._patch(request, partial=False)

    def partial_update(self, request, *args, **kwargs):
        return self._patch(request, partial=True)

    def _patch(self, request, partial: bool):
        endpoint = self.get_object()
        s = UpdateWebhookEndpointPayload(data=request.data, partial=partial)
        s.is_valid(raise_exception=True)
        endpoint = update_webhook_endpoint(
            endpoint=endpoint,
            actor_user=request.user,
            request=request,
            **s.validated_data,
        )
        return Response(WebhookEndpointSerializer(endpoint).data)

    @action(detail=True, methods=["post"], url_path="rotate-secret")
    def rotate_secret(self, request, pk=None):
        endpoint = self.get_object()
        plaintext = rotate_webhook_secret(
            endpoint=endpoint, actor_user=request.user, request=request
        )
        return Response(
            {
                "endpoint": WebhookEndpointSerializer(endpoint).data,
                "secret": plaintext,
            }
        )


class WebhookEventViewSet(TenantScopedViewSet):
    serializer_class = WebhookEventSerializer
    queryset = WebhookEvent.objects.all()
    http_method_names = ["get", "head", "options", "post"]

    def get_base_queryset(self):
        event_type = self.request.query_params.get("event_type")
        return list_events(
            merchant=self.request.merchant,
            environment=self.request.environment,
            event_type=event_type,
        )

    def get_permissions(self):
        if self.action == "replay":
            return [IsAuthenticated(), HasTenantContext(), HasCapability("replay_webhooks")()]
        return [IsAuthenticated(), HasTenantContext(), HasCapability("view_event_logs")()]

    @action(detail=True, methods=["post"])
    def replay(self, request, pk=None):
        event = self.get_object()
        deliveries = replay_event(
            event=event, actor_user=request.user, request=request
        )
        return Response(
            {
                "event": WebhookEventSerializer(event).data,
                "deliveries": WebhookDeliverySerializer(deliveries, many=True).data,
            },
            status=status.HTTP_202_ACCEPTED,
        )


class WebhookDeliveryViewSet(TenantScopedViewSet):
    serializer_class = WebhookDeliverySerializer
    queryset = WebhookDelivery.objects.all()
    http_method_names = ["get", "head", "options", "post"]

    def get_base_queryset(self):
        event_id = self.request.query_params.get("event_id")
        return list_deliveries(
            merchant=self.request.merchant,
            environment=self.request.environment,
            event_id=event_id,
        )

    def get_object(self):
        # Custom guard because base ``WebhookDelivery`` lacks merchant/environment FKs.
        delivery = WebhookDelivery.objects.select_related(
            "webhook_event__merchant", "webhook_event__environment", "endpoint"
        ).get(pk=self.kwargs["pk"])
        if (
            delivery.webhook_event.merchant_id != self.request.merchant.id
            or delivery.webhook_event.environment_id != self.request.environment.id
        ):
            from rest_framework.exceptions import NotFound

            raise NotFound()
        return delivery

    def get_permissions(self):
        if self.action == "retry":
            return [IsAuthenticated(), HasTenantContext(), HasCapability("replay_webhooks")()]
        return [IsAuthenticated(), HasTenantContext(), HasCapability("view_event_logs")()]

    @action(detail=True, methods=["post"])
    def retry(self, request, pk=None):
        delivery = self.get_object()
        delivery = retry_delivery(delivery=delivery, request=request)
        return Response(WebhookDeliverySerializer(delivery).data)
