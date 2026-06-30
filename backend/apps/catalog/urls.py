"""Catalog URL routes."""
from __future__ import annotations

from rest_framework.routers import DefaultRouter

from .views import PlanViewSet, PriceVersionListView, ProductViewSet

router = DefaultRouter()
router.register(r"products", ProductViewSet, basename="product")
router.register(r"plans", PlanViewSet, basename="plan")
router.register(r"price-versions", PriceVersionListView, basename="price-version")

urlpatterns = router.urls
