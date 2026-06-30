"""Celery email tasks — all routed to the ``notifications`` queue."""
from __future__ import annotations

from celery import shared_task

from apps.common.email import frontend_url, send_templated_email


@shared_task(name="apps.accounts.tasks.send_verification_email", queue="notifications")
def send_verification_email(*, email: str, token: str) -> dict:
    verify_link = f"{frontend_url('merchant')}/verify-email?token={token}"
    subject = "Verify your SubPilot email"
    send_templated_email(
        to=email,
        subject=subject,
        template="verify",
        context={"verify_link": verify_link, "token": token},
    )
    return {"to": email, "kind": "verify"}


@shared_task(name="apps.accounts.tasks.send_password_reset_email", queue="notifications")
def send_password_reset_email(*, email: str, token: str) -> dict:
    reset_link = f"{frontend_url('merchant')}/reset-password?token={token}"
    subject = "Reset your SubPilot password"
    send_templated_email(
        to=email,
        subject=subject,
        template="reset",
        context={"reset_link": reset_link, "token": token},
    )
    return {"to": email, "kind": "reset"}


@shared_task(name="apps.accounts.tasks.send_invitation_email", queue="notifications")
def send_invitation_email(*, email: str, org_name: str, invite_link: str) -> dict:
    subject = f"You've been invited to {org_name} on SubPilot"
    send_templated_email(
        to=email,
        subject=subject,
        template="invite",
        context={"org_name": org_name, "invite_link": invite_link},
    )
    return {"to": email, "kind": "invite"}


@shared_task(name="apps.accounts.tasks.send_welcome_email", queue="notifications")
def send_welcome_email(*, email: str, org_name: str) -> dict:
    subject = f"Welcome to SubPilot, {org_name}"
    send_templated_email(
        to=email,
        subject=subject,
        template="welcome",
        context={"org_name": org_name, "dashboard_link": frontend_url("merchant")},
    )
    return {"to": email, "kind": "welcome"}
