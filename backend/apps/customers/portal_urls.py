"""Customer-portal URL routes (mounted under /api/v1/portal/)."""
from __future__ import annotations

from django.urls import path

from .portal_views import (
    PortalCancelSubscriptionView,
    PortalChangePlanView,
    PortalContextView,
    PortalInvoicePdfView,
    PortalInvoicesView,
    PortalPayInvoiceView,
    PortalPaymentMethodCheckoutView,
    PortalPaymentMethodsView,
    PortalPlansView,
    PortalPreviewChangePlanView,
    PortalSetDefaultPaymentMethodView,
    PortalSubscribeView,
)

urlpatterns = [
    path("context", PortalContextView.as_view(), name="portal-context"),
    path("plans", PortalPlansView.as_view(), name="portal-plans"),
    path("subscribe", PortalSubscribeView.as_view(), name="portal-subscribe"),
    path("invoices", PortalInvoicesView.as_view(), name="portal-invoices"),
    path(
        "invoices/<uuid:invoice_id>/pay",
        PortalPayInvoiceView.as_view(),
        name="portal-pay-invoice",
    ),
    path(
        "invoices/<uuid:invoice_id>/pdf",
        PortalInvoicePdfView.as_view(),
        name="portal-invoice-pdf",
    ),
    path(
        "subscriptions/<uuid:subscription_id>/cancel",
        PortalCancelSubscriptionView.as_view(),
        name="portal-cancel-subscription",
    ),
    path(
        "subscriptions/<uuid:subscription_id>/preview-change",
        PortalPreviewChangePlanView.as_view(),
        name="portal-preview-change-plan",
    ),
    path(
        "subscriptions/<uuid:subscription_id>/change-plan",
        PortalChangePlanView.as_view(),
        name="portal-change-plan",
    ),
    path(
        "payment-methods",
        PortalPaymentMethodsView.as_view(),
        name="portal-payment-methods",
    ),
    path(
        "payment-methods/checkout",
        PortalPaymentMethodCheckoutView.as_view(),
        name="portal-payment-method-checkout",
    ),
    path(
        "payment-methods/<uuid:pm_id>/set-default",
        PortalSetDefaultPaymentMethodView.as_view(),
        name="portal-set-default-pm",
    ),
]
