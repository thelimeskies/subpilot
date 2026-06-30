"""Events URL routes."""
from __future__ import annotations

from rest_framework.routers import DefaultRouter

from .views import WebhookDeliveryViewSet, WebhookEndpointViewSet, WebhookEventViewSet


router = DefaultRouter()
router.register(r"webhook-endpoints", WebhookEndpointViewSet, basename="webhook-endpoint")
router.register(r"events", WebhookEventViewSet, basename="webhook-event")
router.register(r"webhook-deliveries", WebhookDeliveryViewSet, basename="webhook-delivery")

urlpatterns = router.urls
