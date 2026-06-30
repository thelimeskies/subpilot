"""Dunning URL routes."""
from __future__ import annotations

from rest_framework.routers import DefaultRouter

from .views import DunningPolicyViewSet, DunningRunViewSet


router = DefaultRouter()
router.register(r"dunning-policies", DunningPolicyViewSet, basename="dunning-policy")
router.register(r"dunning-runs", DunningRunViewSet, basename="dunning-run")

urlpatterns = router.urls
