"""Seed the five FE demo accounts verbatim from
[apps/merchant-dashboard/src/auth/AuthContext.tsx](file:///Users/mac/Desktop/Projects/HackathonxNomba/apps/merchant-dashboard/src/auth/AuthContext.tsx#L83-L159).

Idempotent — re-running this command upserts; the same emails always exist
afterwards.
"""
from __future__ import annotations

import pyotp
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import (
    Environment,
    Merchant,
    Role,
    TeamMember,
    User,
)

# fmt: off
# Mirrors AuthContext.tsx#L83-L159 plus the FE -> internal-role mapping.
DEMO_ACCOUNTS = [
    {
        "email": "owner@acme.test",
        "name": "Ada Okafor",
        "fe_role": "Owner",          "internal_role": Role.OWNER,
        "org_id_legacy": "org_acme", "org_name": "Acme Learning Hub",
        "mfa_enabled": True,
        "onboarding_complete": True,
    },
    {
        "email": "admin@fitplus.test",
        "name": "Tunde Martins",
        "fe_role": "Admin",          "internal_role": Role.BILLING_ADMIN,
        "org_id_legacy": "org_fitplus", "org_name": "FitPlus Studio",
        "mfa_enabled": True,
        "onboarding_complete": True,
    },
    {
        "email": "new@startup.test",
        "name": "Imani Bello",
        "fe_role": "Owner",          "internal_role": Role.OWNER,
        "org_id_legacy": "org_new",  "org_name": "Brand new Startup",
        "mfa_enabled": False,
        "onboarding_complete": False,
    },
    {
        "email": "finance@acme.test",
        "name": "Kemi Lawal",
        "fe_role": "Finance",        "internal_role": Role.FINANCE,
        "org_id_legacy": "org_acme", "org_name": "Acme Learning Hub",
        "mfa_enabled": True,
        "onboarding_complete": True,
    },
    {
        "email": "support@acme.test",
        "name": "Zainab Musa",
        "fe_role": "Support",        "internal_role": Role.SUPPORT,
        "org_id_legacy": "org_acme", "org_name": "Acme Learning Hub",
        "mfa_enabled": False,
        "onboarding_complete": True,
    },
]
# fmt: on


class Command(BaseCommand):
    help = "Seed the five frontend demo accounts (idempotent)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--password",
            default=getattr(settings, "DEMO_ACCOUNT_PASSWORD", "replace-with-local-demo-password"),
            help="Password to assign to all seeded demo accounts.",
        )

    def handle(self, *args, **options):
        demo_password = options["password"]
        merchants_by_legacy = {}

        with transaction.atomic():
            # 1. Ensure merchants exist (deduplicate by org_id_legacy).
            for entry in DEMO_ACCOUNTS:
                key = entry["org_id_legacy"]
                if key in merchants_by_legacy:
                    continue
                merchant, _created = Merchant.objects.get_or_create(
                    slug=key.replace("org_", "") or "workspace",
                    defaults={"name": entry["org_name"], "default_currency": "NGN"},
                )
                # Make sure name is correct on subsequent runs.
                if merchant.name != entry["org_name"]:
                    merchant.name = entry["org_name"]
                    merchant.save(update_fields=["name", "updated_at"])
                merchants_by_legacy[key] = merchant
                Environment.objects.get_or_create(merchant=merchant, mode=Environment.Mode.TEST)
                Environment.objects.get_or_create(merchant=merchant, mode=Environment.Mode.LIVE)

            # 2. Create / update users + team memberships.
            for entry in DEMO_ACCOUNTS:
                email = entry["email"]
                user, created = User.objects.get_or_create(
                    email=email,
                    defaults={
                        "username": email,
                        "display_name": entry["name"],
                        "email_verified": True,
                        "onboarding_complete": entry["onboarding_complete"],
                        "mfa_enabled": entry["mfa_enabled"],
                    },
                )
                # Always reset password to the canonical demo value, and ensure flags match.
                user.set_password(demo_password)
                user.display_name = entry["name"]
                user.email_verified = True
                user.onboarding_complete = entry["onboarding_complete"]
                user.mfa_enabled = entry["mfa_enabled"]
                if entry["mfa_enabled"] and not user.mfa_secret_encrypted:
                    user.mfa_secret = pyotp.random_base32()
                user.save()

                merchant = merchants_by_legacy[entry["org_id_legacy"]]
                TeamMember.objects.update_or_create(
                    merchant=merchant,
                    user=user,
                    defaults={
                        "role": entry["internal_role"],
                        "status": TeamMember.Status.ACTIVE,
                    },
                )

                self.stdout.write(self.style.SUCCESS(
                    f"  {'created' if created else 'updated'}  {email:<22}  "
                    f"role={entry['internal_role']:<14}  org={entry['org_name']}"
                ))

        self.stdout.write(self.style.SUCCESS(
            "\nSeeded %d demo accounts with the configured demo password.\nMFA bypass code: %s"
            % (len(DEMO_ACCOUNTS), getattr(settings, "DEMO_MFA_BYPASS_CODE", ""))
        ))
