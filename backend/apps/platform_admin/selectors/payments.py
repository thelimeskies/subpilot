"""Cross-tenant Payments selector for the platform admin.

Maps :class:`apps.payments.models.PaymentAttempt` rows onto the FE
``Payment`` shape declared in
[seed.ts](file:///Users/mac/Desktop/Projects/HackathonxNomba/apps/subpilot-admin/src/data/seed.ts#L120-L131).

The platform admin needs cross-tenant visibility, so we deliberately
bypass the tenant scoping middleware here and ``select_related`` the
merchant + invoice + customer + method graph in one query.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Iterable

from django.db.models import Q

from apps.payments.models import PaymentAttempt

from ..services.formatting import format_compact_money


# --- Status mapping --------------------------------------------------------


_FE_STATUS_CAPTURED = "Captured"
_FE_STATUS_FAILED = "Failed"
_FE_STATUS_RECOVERED = "Recovered"
_FE_STATUS_REFUNDED = "Refunded"


def _derive_fe_status(attempt: PaymentAttempt) -> str:
    """Translate internal status to the FE label.

    - SUCCEEDED on attempt 1            -> Captured
    - SUCCEEDED on attempt > 1          -> Recovered (dunning win)
    - FAILED / ABANDONED                -> Failed
    - PENDING                           -> Captured (in-flight, treat optimistically)
    - Invoice metadata refunded_at set  -> Refunded (overrides above)
    """
    invoice = getattr(attempt, "invoice", None)
    metadata = getattr(invoice, "metadata", None) or {}
    if isinstance(metadata, dict) and metadata.get("refunded_at"):
        return _FE_STATUS_REFUNDED
    if attempt.status == PaymentAttempt.Status.SUCCEEDED:
        if attempt.attempt_number and attempt.attempt_number > 1:
            return _FE_STATUS_RECOVERED
        return _FE_STATUS_CAPTURED
    if attempt.status in (PaymentAttempt.Status.FAILED, PaymentAttempt.Status.ABANDONED):
        return _FE_STATUS_FAILED
    return _FE_STATUS_CAPTURED


# --- Helpers ---------------------------------------------------------------


_STATUS_ALIASES = {
    "captured": [PaymentAttempt.Status.SUCCEEDED],
    "succeeded": [PaymentAttempt.Status.SUCCEEDED],
    "recovered": [PaymentAttempt.Status.SUCCEEDED],  # filtered post-hoc
    "failed": [PaymentAttempt.Status.FAILED, PaymentAttempt.Status.ABANDONED],
    "refunded": [PaymentAttempt.Status.SUCCEEDED],  # filtered post-hoc
}


def _short_id(value: str | int, prefix: str) -> str:
    raw = str(value).replace("-", "")
    return f"{prefix}_{raw[:12].upper()}"


def _payment_method_label(method) -> str:
    if method is None:
        return "—"
    brand = (getattr(method, "brand", "") or "").strip()
    last4 = (getattr(method, "last4", "") or "").strip()
    if brand and last4:
        return f"{brand} •• {last4}"
    if brand:
        return brand
    if last4:
        return f"•• {last4}"
    provider = (getattr(method, "provider", "") or "").strip()
    return provider.title() if provider else "—"


def _gateway_label(method) -> str:
    """Map provider to the FE 'Adapter A' / 'Adapter B' bucket."""
    provider = (getattr(method, "provider", "") or "").lower() if method else ""
    if provider == "mock":
        return "Adapter B"
    return "Adapter A"


def _failure_reason(attempt: PaymentAttempt) -> str | None:
    code = (attempt.failure_code or "").strip()
    if not code:
        return None
    msg = (attempt.failure_message or "").strip()
    if msg:
        return f"{code}: {msg}"
    return code


# --- Public API ------------------------------------------------------------


@dataclass(frozen=True)
class PaymentListItem:
    id: str
    raw_id: str
    merchant_id: str
    merchant: str
    customer: str
    amount: str
    amount_minor: int
    currency: str
    status: str
    raw_status: str
    method: str
    reason: str | None
    occurred_at: str
    gateway: str
    invoice_id: str | None
    invoice_number: str | None

    def as_dict(self) -> dict:
        return asdict(self)


def list_payments_cross_tenant(
    *,
    status: str | None = None,
    merchant_id: str | None = None,
    method: str | None = None,
    gateway: str | None = None,
    q: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = 25,
    offset: int = 0,
) -> tuple[list[PaymentListItem], int]:
    """Cross-tenant paginated payments list. Returns ``(rows, total)``."""
    qs = (
        PaymentAttempt.objects.select_related(
            "merchant",
            "invoice",
            "invoice__customer",
            "payment_method",
            "environment",
        )
        .order_by("-created_at")
    )

    fe_status = (status or "").strip().lower()
    if fe_status and fe_status not in {"all", ""}:
        internal = _STATUS_ALIASES.get(fe_status)
        if internal:
            qs = qs.filter(status__in=internal)
        else:
            qs = qs.filter(status=fe_status)

    if merchant_id:
        qs = qs.filter(merchant_id=merchant_id)

    if gateway:
        glabel = gateway.strip().lower()
        if glabel in {"adapter a", "nomba"}:
            qs = qs.filter(payment_method__provider="nomba")
        elif glabel in {"adapter b", "mock"}:
            qs = qs.filter(payment_method__provider="mock")

    if method:
        qs = qs.filter(payment_method__brand__iexact=method)

    if date_from is not None:
        qs = qs.filter(created_at__gte=date_from)
    if date_to is not None:
        qs = qs.filter(created_at__lte=date_to)

    if q:
        needle = q.strip()
        if needle:
            qs = qs.filter(
                Q(processor_reference__icontains=needle)
                | Q(merchant__name__icontains=needle)
                | Q(invoice__customer__email__icontains=needle)
                | Q(invoice__customer__name__icontains=needle)
                | Q(invoice__number__icontains=needle)
            )

    total = qs.count()

    rows: list[PaymentListItem] = []
    page = qs[offset : offset + limit]
    for attempt in page:
        merchant = attempt.merchant
        invoice = attempt.invoice
        customer = getattr(invoice, "customer", None)
        method_obj = attempt.payment_method

        cust_label = ""
        if customer is not None:
            cust_label = getattr(customer, "email", "") or getattr(customer, "name", "") or ""

        fe_status = _derive_fe_status(attempt)
        # Apply post-hoc filtering for the synthetic FE buckets that don't
        # cleanly map to a single internal status (Recovered / Refunded).
        if status:
            wanted = status.strip().lower()
            if wanted == "recovered" and fe_status != "Recovered":
                continue
            if wanted == "refunded" and fe_status != "Refunded":
                continue
            if wanted == "captured" and fe_status != "Captured":
                continue

        rows.append(
            PaymentListItem(
                id=_short_id(attempt.id, "pay"),
                raw_id=str(attempt.id),
                merchant_id=str(merchant.id) if merchant else "",
                merchant=getattr(merchant, "name", "") or "—",
                customer=cust_label or "—",
                amount=format_compact_money(attempt.amount_minor or 0, attempt.currency or "NGN"),
                amount_minor=attempt.amount_minor or 0,
                currency=(attempt.currency or "NGN").upper(),
                status=fe_status,
                raw_status=attempt.status,
                method=_payment_method_label(method_obj),
                reason=_failure_reason(attempt),
                occurred_at=attempt.created_at.isoformat() if attempt.created_at else "",
                gateway=_gateway_label(method_obj),
                invoice_id=str(invoice.id) if invoice else None,
                invoice_number=getattr(invoice, "number", None),
            )
        )

    return rows, total


def get_payment_attempt(payment_id) -> PaymentAttempt | None:
    """Cross-tenant lookup by primary key. Returns ``None`` if missing."""
    try:
        return (
            PaymentAttempt.objects.select_related("merchant", "invoice", "payment_method")
            .get(id=payment_id)
        )
    except (PaymentAttempt.DoesNotExist, ValueError):
        return None


def project_payment(item: PaymentListItem) -> dict:
    """Map an internal :class:`PaymentListItem` to the FE Payment dict."""
    return {
        "id": item.id,
        "rawId": item.raw_id,
        "merchantId": item.merchant_id,
        "merchant": item.merchant,
        "customer": item.customer,
        "amount": item.amount,
        "status": item.status,
        "rawStatus": item.raw_status,
        "method": item.method,
        "reason": item.reason,
        "occurredAt": item.occurred_at,
        "gateway": item.gateway,
        "invoiceId": item.invoice_id,
        "invoiceNumber": item.invoice_number,
        "raw": {
            "amountMinor": item.amount_minor,
            "currency": item.currency,
        },
    }


__all__ = [
    "PaymentListItem",
    "list_payments_cross_tenant",
    "get_payment_attempt",
    "project_payment",
]
