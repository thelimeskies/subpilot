"""Reset the demo merchant — wipes all the rows :command:`seed_demo` creates
and then re-seeds them. Useful between hackathon demo runs.

Usage::

    python manage.py reset_demo
    python manage.py reset_demo --merchant-slug acme --no-reseed

Only deletes data scoped to the demo merchant. Other tenants are untouched.
"""
from __future__ import annotations

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import Merchant


class Command(BaseCommand):
    help = "Wipe + re-seed the demo merchant's domain data (idempotent)."

    def add_arguments(self, parser):
        parser.add_argument("--merchant-slug", default="acme")
        parser.add_argument(
            "--no-reseed",
            action="store_true",
            help="Wipe but don't run seed_demo afterwards.",
        )

    def handle(self, *args, **options):
        slug = options["merchant_slug"]
        try:
            merchant = Merchant.objects.get(slug=slug)
        except Merchant.DoesNotExist:
            self.stdout.write(self.style.WARNING(
                f"No merchant with slug={slug!r}; nothing to reset."
            ))
            if not options["no_reseed"]:
                call_command("seed_demo", merchant_slug=slug)
            return

        with transaction.atomic():
            self._wipe(merchant)

        self.stdout.write(self.style.SUCCESS(
            f"Wiped demo data for merchant '{merchant.name}'."
        ))

        if not options["no_reseed"]:
            call_command("seed_demo", merchant_slug=slug)

    # ------------------------------------------------------------------

    def _wipe(self, merchant) -> None:
        # Order matters: delete leaves first, then trunks. We rely on
        # Django's CASCADE/PROTECT rules to keep referential integrity.
        from apps.customers.models import Customer, PaymentMethod, PortalSession
        from apps.dunning.models import DunningPolicy, DunningRun, NotificationLog
        from apps.events.models import (
            WebhookDelivery, WebhookEndpoint, WebhookEvent,
        )
        from apps.invoices.models import CreditNote, Invoice, InvoiceLineItem
        from apps.payments.models import PaymentAttempt
        from apps.subscriptions.models import (
            Subscription, SubscriptionEvent, SubscriptionItem,
        )
        from apps.catalog.models import Plan, PlanFeature, PriceVersion, Product

        scope = {"merchant": merchant}

        # Webhooks
        WebhookDelivery.objects.filter(webhook_event__merchant=merchant).delete()
        WebhookEvent.objects.filter(**scope).delete()
        WebhookEndpoint.objects.filter(**scope).delete()

        # Dunning
        NotificationLog.objects.filter(dunning_run__merchant=merchant).delete()
        DunningRun.objects.filter(**scope).delete()
        # Policies are referenced by Plans (PROTECT), so handle below after Plans.

        # Payments
        PaymentAttempt.objects.filter(**scope).delete()

        # Invoices
        InvoiceLineItem.objects.filter(invoice__merchant=merchant).delete()
        CreditNote.objects.filter(**scope).delete()
        Invoice.objects.filter(**scope).delete()

        # Subscriptions
        SubscriptionEvent.objects.filter(subscription__merchant=merchant).delete()
        SubscriptionItem.objects.filter(subscription__merchant=merchant).delete()
        Subscription.objects.filter(**scope).delete()

        # Customers + portal sessions
        PortalSession.objects.filter(customer__merchant=merchant).delete()
        PaymentMethod.objects.filter(**scope).delete()
        Customer.objects.filter(**scope).delete()

        # Catalog (Plan -> PriceVersion + features cascade; Plan first frees DunningPolicy).
        PlanFeature.objects.filter(plan__merchant=merchant).delete()
        PriceVersion.objects.filter(plan__merchant=merchant).delete()
        Plan.objects.filter(**scope).delete()
        Product.objects.filter(**scope).delete()

        # Now safe to drop dunning policies.
        DunningPolicy.objects.filter(**scope).delete()
