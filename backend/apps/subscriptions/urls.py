"""Subscriptions URL routes."""
from __future__ import annotations

from rest_framework.routers import DefaultRouter

from .views import SubscriptionViewSet

router = DefaultRouter()
router.register(r"subscriptions", SubscriptionViewSet, basename="subscription")

urlpatterns = router.urls
