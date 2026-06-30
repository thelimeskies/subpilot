"""Seed the Acme Learning Hub demo dataset described in
[docs/delivery/demo-scenario-and-seed-data.md](file:///Users/mac/Desktop/Projects/HackathonxNomba/docs/delivery/demo-scenario-and-seed-data.md).

The command is idempotent — re-running it brings the database to the same
known state without raising on duplicates. Used by the hackathon judges'
demo and by the integration smoke test.

Usage::

    python manage.py seed_demo
    python manage.py seed_demo --merchant-slug acme

The merchant slug defaults to ``acme`` to match
[`seed_auth.py`](file:///Users/mac/Desktop/Projects/HackathonxNomba/backend/apps/accounts/management/commands/seed_auth.py)
so the FE demo accounts and the business data point at the same merchant.
"""
from __future__ import annotations

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import ApiKey, Environment, Merchant, Role, TeamMember, User
from apps.accounts.services.api_keys import create_api_key
from apps.catalog.models import Plan
from apps.catalog.services.create_plan import create_plan
from apps.catalog.services.create_price_version import create_price_version
from apps.catalog.services.create_product import create_product
from apps.catalog.services.plan_lifecycle import activate_plan
from apps.customers.models import Customer
from apps.customers.services.create_customer import create_customer
from apps.customers.services.payment_methods import attach_payment_method
from apps.dunning.models import DunningPolicy
from apps.dunning.services.policies import create_dunning_policy
from apps.events.services.endpoints import create_webhook_endpoint
from apps.platform_admin.models import (
    KycLevel,
    KycReview,
    KycStatus,
    SupportTicket,
    SupportTicketPriority,
    SupportTicketStatus,
)
from apps.subscriptions.services.activate_subscription import activate_subscription
from apps.subscriptions.services.create_subscription import create_subscription
from apps.subscriptions.services.lifecycle import (
    cancel_subscription,
    mark_past_due,
    mark_recovered,
)

TEAM_USERS = [
    ("tola@acme.test",   "Tola Adeyemi",   Role.OWNER),
    ("miriam@acme.test", "Miriam Okoro",   Role.BILLING_ADMIN),
    ("femi@acme.test",   "Femi Johnson",   Role.DEVELOPER),
    ("halima@acme.test", "Halima Yusuf",   Role.FINANCE),
    ("david@acme.test",  "David Eze",      Role.SUPPORT),
]

# Plans table — see demo-scenario-and-seed-data.md#L37-L41.
PLANS = [
    {
        "name": "Starter",
        "amount_minor": 5_000 * 100,       # NGN 5,000 -> kobo
        "interval_unit": "month",
        "interval_count": 1,
        "trial_days": 7,
        "policy": "Default SaaS Recovery",
    },
    {
        "name": "Pro",
        "amount_minor": 15_000 * 100,      # NGN 15,000
        "interval_unit": "month",
        "interval_count": 1,
        "trial_days": 14,
        "policy": "Default SaaS Recovery",
    },
    {
        "name": "Business",
        "amount_minor": 150_000 * 100,     # NGN 150,000
        "interval_unit": "year",
        "interval_count": 1,
        "trial_days": 0,
        "policy": "Gentle Enterprise Recovery",
    },
]

CUSTOMERS = [
    {"name": "Ada Okafor",     "email": "ada@example.com",     "plan": "Pro",      "scenario": "active"},
    {"name": "Chinedu Bello",  "email": "chinedu@example.com", "plan": "Pro",      "scenario": "past_due"},
    {"name": "Zainab Musa",    "email": "zainab@example.com",  "plan": "Starter",  "scenario": "trialing"},
    {"name": "Tunde Martins",  "email": "tunde@example.com",   "plan": "Business", "scenario": "canceling"},
    {"name": "Kemi Lawal",     "email": "kemi@example.com",    "plan": "Pro",      "scenario": "active"},
]


class Command(BaseCommand):
    help = "Seed the Acme Learning Hub demo data set (idempotent)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--merchant-slug", default="acme",
            help="Merchant slug to attach demo data to (default: acme).",
        )
        parser.add_argument(
            "--password",
            default=getattr(settings, "DEMO_ACCOUNT_PASSWORD", "replace-with-local-demo-password"),
            help="Password to assign to seeded demo team users.",
        )

    def handle(self, *args, **options):
        slug = options["merchant_slug"]
        self.demo_password = options["password"]
        with transaction.atomic():
            merchant, environment = self._ensure_merchant(slug)
            self._ensure_team(merchant)
            policies = self._ensure_policies(merchant, environment)
            plans = self._ensure_plans(merchant, environment, policies)
            customers = self._ensure_customers(merchant, environment)
            self._ensure_subscriptions(merchant, environment, plans, customers)
            self._ensure_webhook_endpoint(merchant, environment)
            self._ensure_api_keys(merchant)
            self._ensure_support_seed(merchant)
            self._ensure_merchant_config(merchant)

        self.stdout.write(self.style.SUCCESS(
            f"\nDemo seeded for merchant '{merchant.name}' (slug={merchant.slug}). "
            f"Plans: {len(PLANS)}  Customers: {len(CUSTOMERS)}"
        ))

    # ------------------------------------------------------------------
    # Steps
    # ------------------------------------------------------------------

    def _ensure_merchant(self, slug: str) -> tuple[Merchant, Environment]:
        merchant, _ = Merchant.objects.get_or_create(
            slug=slug,
            defaults={"name": "Acme Learning Hub", "default_currency": "NGN"},
        )
        if merchant.name != "Acme Learning Hub":
            merchant.name = "Acme Learning Hub"
            merchant.default_currency = "NGN"
            merchant.save(update_fields=["name", "default_currency", "updated_at"])
        env, _ = Environment.objects.get_or_create(
            merchant=merchant, mode=Environment.Mode.TEST
        )
        Environment.objects.get_or_create(merchant=merchant, mode=Environment.Mode.LIVE)
        self.stdout.write(f"merchant : {merchant.name} ({merchant.slug})  env=test")
        return merchant, env

    def _ensure_team(self, merchant: Merchant) -> None:
        for email, name, role in TEAM_USERS:
            user, _ = User.objects.get_or_create(
                email=email,
                defaults={
                    "username": email,
                    "display_name": name,
                    "email_verified": True,
                    "onboarding_complete": True,
                    "mfa_enabled": False,
                },
            )
            user.set_password(self.demo_password)
            user.display_name = name
            user.email_verified = True
            user.save()
            TeamMember.objects.update_or_create(
                merchant=merchant, user=user,
                defaults={"role": role, "status": TeamMember.Status.ACTIVE},
            )
        self.stdout.write(f"team     : {len(TEAM_USERS)} members ensured")

    def _ensure_policies(self, merchant, environment) -> dict[str, DunningPolicy]:
        out: dict[str, DunningPolicy] = {}
        existing = DunningPolicy.objects.filter(
            merchant=merchant, environment=environment, name="Default SaaS Recovery"
        ).first()
        if existing is None:
            existing = create_dunning_policy(
                merchant=merchant, environment=environment,
                name="Default SaaS Recovery",
                retry_offsets_days=[0, 1, 3, 7, 14],
                grace_period_days=7,
                final_action=DunningPolicy.FinalAction.PAUSE,
                notify_email=True, notify_sms=True, notify_webhook=True,
            )
        out["Default SaaS Recovery"] = existing

        gentle = DunningPolicy.objects.filter(
            merchant=merchant, environment=environment, name="Gentle Enterprise Recovery"
        ).first()
        if gentle is None:
            gentle = create_dunning_policy(
                merchant=merchant, environment=environment,
                name="Gentle Enterprise Recovery",
                retry_offsets_days=[1, 3, 7, 14, 21],
                grace_period_days=21,
                final_action=DunningPolicy.FinalAction.MARK_UNCOLLECTIBLE,
                notify_email=True, notify_sms=False, notify_webhook=True,
            )
        out["Gentle Enterprise Recovery"] = gentle
        self.stdout.write(f"policies : {len(out)} dunning policies ensured")
        return out

    def _ensure_plans(self, merchant, environment, policies) -> dict[str, Plan]:
        product = self._ensure_product(merchant, environment)
        out: dict[str, Plan] = {}
        for spec in PLANS:
            plan = Plan.objects.filter(
                merchant=merchant, environment=environment,
                product=product, name=spec["name"],
            ).first()
            if plan is None:
                plan = create_plan(
                    merchant=merchant, environment=environment,
                    product=product, name=spec["name"],
                    description=f"{spec['name']} tier — Acme Learning Hub",
                    trial_days=spec["trial_days"],
                    dunning_policy=policies[spec["policy"]],
                )
            # Always make sure there is an active price version.
            from apps.catalog.models import PriceVersion
            has_pv = PriceVersion.objects.filter(plan=plan, active_to__isnull=True).exists()
            if not has_pv:
                create_price_version(
                    plan=plan,
                    amount_minor=spec["amount_minor"],
                    currency="NGN",
                    interval_unit=spec["interval_unit"],
                    interval_count=spec["interval_count"],
                )
            if plan.status != Plan.Status.ACTIVE:
                activate_plan(plan=plan)
            out[spec["name"]] = plan
        self.stdout.write(f"plans    : {len(out)} active plans ensured")
        return out

    def _ensure_product(self, merchant, environment):
        from apps.catalog.models import Product
        product = Product.objects.filter(
            merchant=merchant, environment=environment, name="Acme Learning Hub Subscriptions"
        ).first()
        if product is None:
            product = create_product(
                merchant=merchant, environment=environment,
                name="Acme Learning Hub Subscriptions",
                description="Online education platform subscriptions.",
            )
        return product

    def _ensure_customers(self, merchant, environment) -> dict[str, Customer]:
        out: dict[str, Customer] = {}
        for spec in CUSTOMERS:
            customer = Customer.objects.filter(
                merchant=merchant, environment=environment, email=spec["email"]
            ).first()
            if customer is None:
                customer = create_customer(
                    merchant=merchant, environment=environment,
                    email=spec["email"], name=spec["name"],
                    metadata={"demo_scenario": spec["scenario"]},
                )
            out[spec["email"]] = customer
        self.stdout.write(f"customers: {len(out)} customers ensured")
        return out

    def _ensure_subscriptions(self, merchant, environment, plans, customers) -> None:
        from apps.customers.models import PaymentMethod
        from apps.subscriptions.models import Subscription

        for spec in CUSTOMERS:
            customer = customers[spec["email"]]
            plan = plans[spec["plan"]]

            # Skip if subscription already exists.
            sub = Subscription.objects.filter(
                merchant=merchant, environment=environment,
                customer=customer, plan=plan,
            ).first()
            if sub is not None:
                continue

            # Attach a default mock payment method.
            pm = PaymentMethod.objects.filter(
                customer=customer, status=PaymentMethod.Status.ACTIVE
            ).first()
            if pm is None:
                pm = attach_payment_method(
                    customer=customer,
                    provider=PaymentMethod.Provider.NOMBA,
                    token=f"tok_demo_{customer.email.split('@')[0]}",
                    brand="visa", last4="4242",
                    exp_month=12, exp_year=timezone.now().year + 2,
                    set_default=True,
                )

            sub = create_subscription(
                merchant=merchant, environment=environment,
                customer=customer, plan=plan,
                default_payment_method=pm,
                metadata={"demo_scenario": spec["scenario"]},
            )

            scenario = spec["scenario"]
            if scenario == "trialing":
                activate_subscription(subscription=sub, with_trial=True)
            elif scenario == "canceling":
                activate_subscription(subscription=sub)
                cancel_subscription(subscription=sub, at_period_end=True, reason="demo")
            elif scenario == "past_due":
                activate_subscription(subscription=sub)
                mark_past_due(subscription=sub)
            elif scenario == "recovered":
                activate_subscription(subscription=sub)
                mark_past_due(subscription=sub)
                mark_recovered(subscription=sub)
            else:  # active
                activate_subscription(subscription=sub)

        self.stdout.write(f"subs     : {len(CUSTOMERS)} subscription scenarios ensured")

    def _ensure_webhook_endpoint(self, merchant, environment) -> None:
        from apps.events.models import WebhookEndpoint
        existing = WebhookEndpoint.objects.filter(
            merchant=merchant, environment=environment,
            url="https://example.test/webhooks/subpilot",
        ).first()
        if existing is not None:
            return
        endpoint, plaintext = create_webhook_endpoint(
            merchant=merchant, environment=environment,
            url="https://example.test/webhooks/subpilot",
            description="Demo webhook endpoint",
            event_filters=["*"],
        )
        # Stash the plaintext in metadata-like field so the demo can reference it.
        # In real life we'd hand this to the developer once and never again.
        self.stdout.write(
            f"webhook  : endpoint {endpoint.id}  secret={plaintext[:20]}…"
        )

    def _ensure_api_keys(self, merchant: Merchant) -> None:
        specs = [
            ("Production server", Environment.Mode.LIVE, ["read", "write"]),
            ("Billing worker", Environment.Mode.LIVE, ["read", "write", "admin"]),
            ("Local development", Environment.Mode.TEST, ["read", "write"]),
        ]
        ensured = 0
        for name, mode, scopes in specs:
            environment = Environment.objects.filter(merchant=merchant, mode=mode).first()
            if environment is None:
                continue
            existing = ApiKey.objects.filter(
                merchant=merchant,
                environment=environment,
                name=name,
                status=ApiKey.Status.ACTIVE,
            ).first()
            if existing is None:
                create_api_key(
                    merchant=merchant,
                    environment=environment,
                    name=name,
                    scopes=scopes,
                )
            ensured += 1
        self.stdout.write(f"api keys : {ensured} active developer keys ensured")

    def _ensure_support_seed(self, merchant: Merchant) -> None:
        ticket_specs = [
            ("Webhook signature verification rejecting events", SupportTicketPriority.HIGH, SupportTicketStatus.OPEN),
            ("Need to bulk-replay 12 dunning events", SupportTicketPriority.NORMAL, SupportTicketStatus.IN_PROGRESS),
            ("Adapter B latency spikes during peak hours", SupportTicketPriority.NORMAL, SupportTicketStatus.RESOLVED),
        ]
        created = 0
        for subject, priority, status in ticket_specs:
            existing = SupportTicket.objects.filter(merchant=merchant, subject=subject).first()
            if existing is None:
                SupportTicket.objects.create(
                    merchant=merchant,
                    subject=subject,
                    body=f"Seeded ticket — {subject}",
                    priority=priority,
                    status=status,
                    requester_email="owner@acme.test",
                )
                created += 1
        kyc, kyc_created = KycReview.objects.get_or_create(
            merchant=merchant,
            defaults={
                "status": KycStatus.VERIFIED,
                "level": KycLevel.TIER_2,
                "documents": [
                    {"kind": "CAC", "status": "Approved", "uploadedAt": "2025-11-04"},
                    {"kind": "BVN", "status": "Approved", "uploadedAt": "2025-11-04"},
                    {"kind": "Director ID", "status": "Approved", "uploadedAt": "2025-11-05"},
                ],
                "flags": [],
                "notes": "Seeded — clean history.",
                "submitted_at": timezone.now(),
                "reviewed_at": timezone.now(),
            },
        )
        self.stdout.write(
            f"support  : {created} new tickets, KYC review {'created' if kyc_created else 'present'}"
        )

    def _ensure_merchant_config(self, merchant: Merchant) -> None:
        """Idempotent per-merchant config row (S13).

        Default flag set is the catalog default — we don't seed any
        per-merchant overrides so the demo reflects platform defaults.
        Limits + retry policy are populated with realistic numbers so the
        FE Config tab shows non-empty values out of the box.
        """
        from apps.platform_admin.models import MerchantConfig

        defaults = {
            "feature_flags": {},  # all flags resolve via catalog defaults
            "limits": {
                "monthly_volume_cap_minor": 5_000_000_000,  # NGN 50m
                "max_ticket_minor": 25_000_000,             # NGN 250,000
                "high_risk_mcc": False,
                "payout_cadence": "daily",
                "notification_channels": ["email", "slack"],
                "currency": merchant.default_currency or "NGN",
            },
            "retry_policy": {
                "attempts": 4,
                "backoff": "exponential",
                "cooldown_hours": 6,
            },
        }
        config, created = MerchantConfig.objects.get_or_create(
            merchant=merchant, defaults=defaults
        )
        self.stdout.write(
            f"config   : merchant config {'created' if created else 'present'}"
        )
