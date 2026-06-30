"""URL routes for the accounts app — mounted under ``/api/v1/auth/`` by ``config.urls``."""
from django.urls import path

from . import views

urlpatterns = [
    path("sign-up", views.SignUpView.as_view(), name="sign-up"),
    path("sign-in", views.SignInView.as_view(), name="sign-in"),
    path("sign-out", views.SignOutView.as_view(), name="sign-out"),
    path("verify-email", views.VerifyEmailView.as_view(), name="verify-email"),
    path("request-reset", views.RequestResetView.as_view(), name="request-reset"),
    path("reset-password", views.ResetPasswordView.as_view(), name="reset-password"),
    path("verify-mfa", views.VerifyMfaView.as_view(), name="verify-mfa"),
    path("me", views.MeView.as_view(), name="me"),
    path("impersonate", views.ImpersonateConsumeView.as_view(), name="impersonate"),
]
