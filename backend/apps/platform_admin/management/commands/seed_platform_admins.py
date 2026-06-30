"""Seed three demo platform admin accounts matching the FE prototype.

Idempotent — re-running brings the DB to the same known state. Mirrors
the demo accounts shown on
[SignInPage.tsx](file:///Users/mac/Desktop/Projects/HackathonxNomba/apps/subpilot-admin/src/auth/SignInPage.tsx#L7-L11).
"""
from __future__ import annotations

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.platform_admin.models import PlatformAdmin, PlatformAdminRole, PlatformAdminStatus

ADMINS = [
    ("owner@subpilot.dev", "Ada Okafor", PlatformAdminRole.OWNER),
    ("ops@subpilot.dev", "Tunde Martins", PlatformAdminRole.OPERATOR),
    ("support@subpilot.dev", "Zainab Musa", PlatformAdminRole.SUPPORT),
]


class Command(BaseCommand):
    help = "Seed the three demo PlatformAdmin accounts (idempotent)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--password",
            default=getattr(settings, "DEMO_ACCOUNT_PASSWORD", "replace-with-local-demo-password"),
            help="Password to assign to seeded platform admin users.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        demo_password = options["password"]
        for email, name, role in ADMINS:
            email = email.strip().lower()
            admin, created = PlatformAdmin.objects.get_or_create(
                email=email,
                defaults={
                    "display_name": name,
                    "role": role,
                    "status": PlatformAdminStatus.ACTIVE,
                },
            )
            admin.display_name = name
            admin.role = role
            admin.status = PlatformAdminStatus.ACTIVE
            admin.set_password(demo_password)
            admin.save()
            self.stdout.write(self.style.SUCCESS(
                f"{'Created' if created else 'Updated'} platform admin {email} ({role})"
            ))
