"""URL routes for the analytics app."""
from __future__ import annotations

from django.urls import path

from .views import DashboardLiveView, DashboardOverviewView

urlpatterns = [
    path("analytics/overview", DashboardOverviewView.as_view(), name="analytics-overview"),
    path("analytics/overview/live", DashboardLiveView.as_view(), name="analytics-overview-live"),
]
