"""Audit URL routes."""
from __future__ import annotations

from django.urls import path

from .views import AuditLogListView


urlpatterns = [
    path("audit-logs/", AuditLogListView.as_view(), name="audit-log-list"),
]
