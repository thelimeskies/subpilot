"""Cross-tenant Merchant list selector for the platform admin.

The shape produced here matches the FE [Merchant](file:///Users/mac/Desktop/Projects/HackathonxNomba/apps/subpilot-admin/src/data/seed.ts#L4-L19)
interface so the UI can swap from the seed list with no UI changes.

Computed fields (failed_invoices, mrr_minor, recovery_rate, monthly_volume)
require per-row aggregation. We do it in Python after a single
``prefetch_related`` pass so list size <= 200 stays well under the perf
budget (the FE already pages at 10/page).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import timedelta

from django.db.models import Count, Q, Sum
from django.utils import timezone

from apps.accounts.models import Environment, Merchant, Role, TeamMember
from apps.analytics.selectors import _normalise_to_monthly_minor  # noqa: PLC2701
from apps.dunning.models import DunningRun
from apps.invoices.models import Invoice
from apps.payments.models import BalanceTransaction
from apps.subscriptions.models import Subscription, SubscriptionItem


@dataclass(frozen=True)
class MerchantListItem:
    id: str
    name: str
    owner: str
    owner_email: str
    plan: str
    mrr_minor: int
    currency: str
    status: str  # Healthy / At risk / Suspended
    failed_invoices: int
    recovery_rate_pct: float
    environment: str  # Live / Test
    created_at: str  # ISO 8601
    region: str
    monthly_volume_minor: int
    active_subscriptions: int

    def as_dict(self) -> dict:
        return asdict(self)


# --- Filter helpers --------------------------------------------------------


_PLAN_BUCKETS = {
    "Starter": ["starter", "essentials", "lite"],
    "Growth": ["growth", "scale", "pro"],
    "Enterprise": ["enterprise", "platform", "max"],
    "Internal": ["internal", "test", "demo"],
}


def _plan_bucket(plan_name: str | None) -> str:
    if not plan_name:
        return "Starter"
    lc = plan_name.lower()
    for bucket, needles in _PLAN_BUCKETS.items():
        for needle in needles:
            if needle in lc:
                return bucket
    return "Growth"  # safe default


def _derive_status(merchant_status: str, failed: int) -> str:
    if merchant_status == Merchant.Status.SUSPENDED:
        return "Suspended"
    if merchant_status == Merchant.Status.CLOSED:
        return "Suspended"
    if failed > 0:
        return "At risk"
    return "Healthy"


def _derive_region(industry: str | None) -> str:
    """The Merchant model has no explicit region; we approximate using the
    NGN/`industry` defaults so the FE renders a sane string."""
    if industry:
        return f"Nigeria · {industry.title()}"
    return "Lagos, NG"


# --- The selector ---------------------------------------------------------


def list_merchants(
    *,
    status: str | None = None,
    plan: str | None = None,
    region: str | None = None,
    environment: str | None = None,
    q: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[MerchantListItem], int]:
    """Return ``(items, total_count)`` matching the filter set.

    All filters are optional. ``q`` matches merchant name, slug, or
    owner email/display_name (case-insensitive ``icontains``).
    """
    qs = Merchant.objects.all().order_by("-created_at")

    # --- DB-side filters -------------------------------------------------
    if status:
        # Map FE status back to DB.
        if status.lower() == "suspended":
            qs = qs.filter(status__in=[Merchant.Status.SUSPENDED, Merchant.Status.CLOSED])
        elif status.lower() == "active" or status.lower() == "healthy":
            qs = qs.filter(status=Merchant.Status.ACTIVE)

    if q:
        # Owner-side join via the explicit reverse 'team_members' related_name.
        owner_match = Q(team_members__user__email__icontains=q) | Q(
            team_members__user__display_name__icontains=q
        )
        qs = qs.filter(Q(name__icontains=q) | Q(slug__icontains=q) | owner_match).distinct()

    if region:
        qs = qs.filter(industry__icontains=region)

    # NOTE: Most tenant FKs to Merchant use ``related_name="+"`` (no reverse
    # accessor), so we cannot annotate counts directly on the Merchant
    # queryset. Instead we count via reverse aggregations below.
    total = qs.count()

    # Slice for pagination after the count.
    page = list(qs[offset : offset + limit])

    if not page:
        return [], total

    merchant_ids = [m.id for m in page]

    # --- Per-merchant aggregations (separate queries grouped by merchant) ---
    active_subs_by_merchant: dict[str, int] = {}
    for row in (
        Subscription.objects.filter(
            merchant_id__in=merchant_ids, status=Subscription.Status.ACTIVE
        )
        .values("merchant_id")
        .annotate(n=Count("id"))
    ):
        active_subs_by_merchant[str(row["merchant_id"])] = int(row["n"] or 0)

    failed_invoices_by_merchant: dict[str, int] = {}
    for row in (
        Invoice.objects.filter(
            merchant_id__in=merchant_ids,
            status=Invoice.Status.OPEN,
            dunning_runs__status=DunningRun.Status.ACTIVE,
        )
        .values("merchant_id")
        .annotate(n=Count("id", distinct=True))
    ):
        failed_invoices_by_merchant[str(row["merchant_id"])] = int(row["n"] or 0)

    # --- Batch prefetches -----------------------------------------------
    # Owner + team
    owner_by_merchant: dict[str, tuple[str, str]] = {}
    for tm in (
        TeamMember.objects.filter(
            merchant_id__in=merchant_ids, role=Role.OWNER, status=TeamMember.Status.ACTIVE
        )
        .select_related("user")
        .order_by("-created_at")
    ):
        # First-seen wins (most-recent owner activation).
        owner_by_merchant.setdefault(
            str(tm.merchant_id),
            (
                (tm.user.display_name or tm.user.email or "Owner"),
                (tm.user.email or ""),
            ),
        )

    # Environments — choose Live > Test
    env_by_merchant: dict[str, str] = {}
    for env in Environment.objects.filter(merchant_id__in=merchant_ids):
        existing = env_by_merchant.get(str(env.merchant_id))
        if env.mode == Environment.Mode.LIVE:
            env_by_merchant[str(env.merchant_id)] = "Live"
        elif existing != "Live":
            env_by_merchant[str(env.merchant_id)] = "Test"

    # Plan — biggest active plan name
    plan_by_merchant: dict[str, str] = {}
    for sub in (
        Subscription.objects.filter(
            merchant_id__in=merchant_ids,
            status__in=[Subscription.Status.ACTIVE, Subscription.Status.TRIALING],
        )
        .select_related("plan")
        .order_by("-created_at")
    ):
        plan_by_merchant.setdefault(
            str(sub.merchant_id), sub.plan.name if sub.plan else "Starter"
        )

    # MRR per merchant — Python loop with normalised intervals.
    mrr_by_merchant: dict[str, tuple[int, str]] = {mid: (0, "NGN") for mid in map(str, merchant_ids)}
    items = (
        SubscriptionItem.objects.filter(
            subscription__merchant_id__in=merchant_ids,
            subscription__status__in=[
                Subscription.Status.ACTIVE,
                Subscription.Status.TRIALING,
                Subscription.Status.PAST_DUE,
            ],
            status=SubscriptionItem.Status.ACTIVE,
        )
        .select_related("price_version", "subscription")
    )
    for item in items:
        pv = item.price_version
        if pv is None:
            continue
        mid = str(item.subscription.merchant_id)
        line = pv.amount_minor * max(1, int(item.quantity or 1))
        normalised = _normalise_to_monthly_minor(line, pv.interval_unit, pv.interval_count)
        existing_total, existing_curr = mrr_by_merchant.get(mid, (0, "NGN"))
        mrr_by_merchant[mid] = (existing_total + normalised, pv.currency or existing_curr)

    # Monthly volume — sum of captured charge movements in last 30 days.
    cutoff = timezone.now() - timedelta(days=30)
    volume_rows = (
        BalanceTransaction.objects.filter(
            merchant_id__in=merchant_ids,
            type=BalanceTransaction.Type.CHARGE,
            created_at__gte=cutoff,
        )
        .values("merchant_id")
        .annotate(total=Sum("signed_amount_minor"))
    )
    volume_by_merchant = {
        str(row["merchant_id"]): int(row["total"] or 0) for row in volume_rows
    }

    # Recovery rate — terminated dunning runs in last 30 days, % recovered.
    runs = (
        DunningRun.objects.filter(merchant_id__in=merchant_ids, updated_at__gte=cutoff)
        .values("merchant_id")
        .annotate(
            recovered=Count("id", filter=Q(status=DunningRun.Status.RECOVERED)),
            terminated=Count(
                "id",
                filter=Q(
                    status__in=[
                        DunningRun.Status.RECOVERED,
                        DunningRun.Status.EXHAUSTED,
                        DunningRun.Status.CANCELED,
                    ]
                ),
            ),
        )
    )
    recovery_by_merchant: dict[str, float] = {}
    for row in runs:
        mid = str(row["merchant_id"])
        terminated = int(row["terminated"] or 0)
        if terminated:
            recovery_by_merchant[mid] = round(100.0 * int(row["recovered"] or 0) / terminated, 2)
        else:
            recovery_by_merchant[mid] = 0.0

    # --- Project ---------------------------------------------------------
    items_out: list[MerchantListItem] = []
    for m in page:
        mid = str(m.id)
        owner_name, owner_email = owner_by_merchant.get(mid, ("—", ""))
        mrr_minor, currency = mrr_by_merchant.get(mid, (0, m.default_currency or "NGN"))
        plan_name = _plan_bucket(plan_by_merchant.get(mid))
        failed = failed_invoices_by_merchant.get(mid, 0)
        active_subs = active_subs_by_merchant.get(mid, 0)

        item_status = _derive_status(m.status, failed)

        # Apply post-filters (plan / environment / status mapped from FE values).
        if plan and plan_name.lower() != plan.lower():
            continue
        env_label = env_by_merchant.get(mid, "Test")
        if environment and env_label.lower() != environment.lower():
            continue
        if status and status.lower() in {"healthy", "at risk", "at_risk"}:
            if item_status.lower().replace(" ", "_") != status.lower().replace(" ", "_"):
                continue

        items_out.append(
            MerchantListItem(
                id=mid,
                name=m.name,
                owner=owner_name,
                owner_email=owner_email,
                plan=plan_name,
                mrr_minor=mrr_minor,
                currency=currency,
                status=item_status,
                failed_invoices=failed,
                recovery_rate_pct=recovery_by_merchant.get(mid, 0.0),
                environment=env_label,
                created_at=m.created_at.isoformat() if m.created_at else "",
                region=_derive_region(m.industry),
                monthly_volume_minor=volume_by_merchant.get(mid, 0),
                active_subscriptions=active_subs,
            )
        )

    return items_out, total
