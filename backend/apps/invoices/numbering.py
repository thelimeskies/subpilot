"""Invoice number generation.

Format: ``INV-{YYYYMM}-{merchant_short}-{seq:06d}``. Sequence is monotonic
per (merchant, environment, year-month) and uses ``select_for_update`` to
serialize concurrent allocations.
"""
from __future__ import annotations

from django.utils import timezone

from apps.common.db import atomic_with_retry

from .models import Invoice


@atomic_with_retry
def allocate_invoice_number(*, merchant, environment) -> str:
    now = timezone.now()
    yyyymm = now.strftime("%Y%m")
    prefix = f"INV-{yyyymm}-"
    short = str(merchant.id).split("-")[0][:8].upper()
    full_prefix = f"{prefix}{short}-"

    last = (
        Invoice.objects.select_for_update(skip_locked=False)
        .filter(
            merchant=merchant,
            environment=environment,
            number__startswith=full_prefix,
        )
        .order_by("-number")
        .first()
    )
    if last is None:
        seq = 1
    else:
        try:
            seq = int(last.number.rsplit("-", 1)[-1]) + 1
        except (ValueError, IndexError):
            seq = 1
    return f"{full_prefix}{seq:06d}"
