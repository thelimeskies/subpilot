"""Create a SubPilot Platform Operator (internal staff user).

Reads ``PLATFORM_ADMIN_EMAIL`` and ``PLATFORM_ADMIN_PASSWORD`` from env. Idempotent.
"""
from __future__ import annotations

import os

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.models import User


class Command(BaseCommand):
    help = "Create or update a SubPilot Platform Operator (Django staff user)."

    def add_arguments(self, parser):
        parser.add_argument("--email", default=os.environ.get("PLATFORM_ADMIN_EMAIL", "admin@example.test"))
        parser.add_argument("--password", default=os.environ.get("PLATFORM_ADMIN_PASSWORD", ""))
        parser.add_argument("--name", default="SubPilot Platform Operator")

    @transaction.atomic
    def handle(self, *args, **options):
        email = options["email"].strip().lower()
        password = options["password"]
        name = options["name"]
        if not password:
            raise CommandError("Set PLATFORM_ADMIN_PASSWORD or pass --password.")

        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                "username": email,
                "display_name": name,
                "email_verified": True,
                "is_staff": True,
                "is_superuser": True,
            },
        )
        user.set_password(password)
        user.is_staff = True
        user.is_superuser = True
        user.email_verified = True
        user.display_name = name
        user.save()

        self.stdout.write(self.style.SUCCESS(
            f"{'Created' if created else 'Updated'} platform operator {email}"
        ))
