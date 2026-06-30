"""Payments URL routes."""
from __future__ import annotations

from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import CentralNombaWebhookView, PaymentAttemptViewSet, ProcessorWebhookView

router = DefaultRouter()
router.register(r"payment-attempts", PaymentAttemptViewSet, basename="payment-attempt")

urlpatterns = list(router.urls) + [
    path(
        "payments/webhooks/nomba/",
        CentralNombaWebhookView.as_view(),
        name="processor-webhook-nomba-central",
    ),
    path(
        "payments/webhooks/<str:provider>/<uuid:merchant_id>/<str:mode>/",
        ProcessorWebhookView.as_view(),
        name="processor-webhook",
    ),
]
