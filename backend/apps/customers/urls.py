"""Customers URL routes."""
from __future__ import annotations

from rest_framework.routers import DefaultRouter

from .views import CustomerViewSet, PaymentMethodViewSet, PortalSessionViewSet

router = DefaultRouter()
router.register(r"customers", CustomerViewSet, basename="customer")
router.register(r"payment-methods", PaymentMethodViewSet, basename="payment-method")
router.register(r"portal-sessions", PortalSessionViewSet, basename="portal-session")

urlpatterns = router.urls
