"""Root URL configuration."""
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)


def health(_request):
    return JsonResponse({"status": "ok", "service": "subpilot-api"})


api_v1_patterns = [
    path("health", health, name="health"),
    path("auth/", include("apps.accounts.urls")),
    path("", include("apps.accounts.api_urls")),
    path("catalog/", include("apps.catalog.urls")),
    path("", include("apps.customers.urls")),
    path("", include("apps.subscriptions.urls")),
    path("", include("apps.invoices.urls")),
    path("", include("apps.payments.urls")),
    path("", include("apps.dunning.urls")),
    path("", include("apps.events.urls")),
    path("", include("apps.analytics.urls")),
    path("", include("apps.audit.urls")),
    path("portal/", include("apps.customers.portal_urls")),
    path("platform/", include("apps.platform_admin.urls")),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include((api_v1_patterns, "v1"))),
    # OpenAPI
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]
