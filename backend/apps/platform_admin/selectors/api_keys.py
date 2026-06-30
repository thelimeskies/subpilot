"""Cross-tenant API-keys selector for the platform admin (S7).

Maps :class:`apps.accounts.models.ApiKey` rows onto the FE ``ApiKey`` shape
declared in
[seed.ts](file:///Users/mac/Desktop/Projects/HackathonxNomba/apps/subpilot-admin/src/data/seed.ts#L270-L322).

Internal → FE projections:
    status:   active   → "Active"
              revoked  → "Revoked"
    scope:    environment.mode "live" → "Live"
              environment.mode "test" → "Test"
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

from django.db.models import Q

from apps.accounts.models import ApiKey


# --- Status mapping --------------------------------------------------------


_FE_ACTIVE = "Active"
_FE_REVOKED = "Revoked"
_FE_LIVE = "Live"
_FE_TEST = "Test"


_FE_TO_INTERNAL_STATUS = {
    "active": ApiKey.Status.ACTIVE,
    "revoked": ApiKey.Status.REVOKED,
}

_FE_TO_INTERNAL_SCOPE = {
    "live": "live",
    "test": "test",
}


def _fe_status(api_key: ApiKey) -> str:
    return _FE_REVOKED if api_key.status == ApiKey.Status.REVOKED else _FE_ACTIVE


def _fe_scope(api_key: ApiKey) -> str:
    mode = (getattr(api_key.environment, "mode", "") or "").lower()
    return _FE_LIVE if mode == "live" else _FE_TEST


def _created_by_label(api_key: ApiKey) -> str:
    user = api_key.created_by
    if user is None:
        return "—"
    name = (getattr(user, "full_name", "") or "").strip()
    if name:
        return name
    return getattr(user, "email", "") or "—"


# --- Public API ------------------------------------------------------------


@dataclass(frozen=True)
class ApiKeyListItem:
    id: str
    raw_id: str
    label: str
    prefix: str
    scope: str
    raw_scope: str
    created_by: str
    created_at: str
    last_used: str
    status: str
    raw_status: str
    merchant_id: str
    merchant: str
    environment_id: str

    def as_dict(self) -> dict:
        return asdict(self)


def list_api_keys_cross_tenant(
    *,
    status: str | None = None,
    scope: str | None = None,
    merchant_id: str | None = None,
    environment_id: str | None = None,
    q: str | None = None,
    limit: int = 25,
    offset: int = 0,
) -> tuple[list[ApiKeyListItem], int]:
    """Cross-tenant paginated API-keys list. Returns ``(rows, total)``."""
    qs = (
        ApiKey.objects.select_related("merchant", "environment", "created_by")
        .order_by("-created_at")
    )

    fe_status = (status or "").strip().lower()
    if fe_status and fe_status not in {"all", ""}:
        internal = _FE_TO_INTERNAL_STATUS.get(fe_status)
        if internal is not None:
            qs = qs.filter(status=internal)
        else:
            qs = qs.filter(status=fe_status)

    fe_scope = (scope or "").strip().lower()
    if fe_scope and fe_scope not in {"all", ""}:
        mode = _FE_TO_INTERNAL_SCOPE.get(fe_scope, fe_scope)
        qs = qs.filter(environment__mode=mode)

    if merchant_id:
        qs = qs.filter(merchant_id=merchant_id)

    if environment_id:
        qs = qs.filter(environment_id=environment_id)

    if q:
        needle = q.strip()
        if needle:
            qs = qs.filter(
                Q(name__icontains=needle)
                | Q(key_prefix__icontains=needle)
                | Q(merchant__name__icontains=needle)
            )

    total = qs.count()

    rows: list[ApiKeyListItem] = []
    page = qs[offset : offset + limit]
    for k in page:
        rows.append(
            ApiKeyListItem(
                id=str(k.id),
                raw_id=str(k.id),
                label=k.name or "—",
                prefix=f"{k.key_prefix}…",
                scope=_fe_scope(k),
                raw_scope=(getattr(k.environment, "mode", "") or "").lower(),
                created_by=_created_by_label(k),
                created_at=k.created_at.isoformat() if k.created_at else "",
                last_used=k.last_used_at.isoformat() if k.last_used_at else "",
                status=_fe_status(k),
                raw_status=k.status,
                merchant_id=str(k.merchant_id) if k.merchant_id else "",
                merchant=getattr(k.merchant, "name", "") or "—",
                environment_id=str(k.environment_id) if k.environment_id else "",
            )
        )

    return rows, total


def get_api_key(api_key_id) -> ApiKey | None:
    """Cross-tenant lookup. Returns ``None`` if missing or invalid id."""
    try:
        return (
            ApiKey.objects.select_related("merchant", "environment", "created_by")
            .get(pk=api_key_id)
        )
    except (ApiKey.DoesNotExist, ValueError):
        return None


def project_api_key(item: ApiKeyListItem) -> dict:
    """Map an internal :class:`ApiKeyListItem` to the FE ApiKey dict."""
    return {
        "id": item.id,
        "rawId": item.raw_id,
        "label": item.label,
        "prefix": item.prefix,
        "scope": item.scope,
        "rawScope": item.raw_scope,
        "createdBy": item.created_by,
        "createdAt": item.created_at,
        "lastUsed": item.last_used,
        "status": item.status,
        "rawStatus": item.raw_status,
        "merchantId": item.merchant_id,
        "merchant": item.merchant,
        "environmentId": item.environment_id,
    }


__all__ = [
    "ApiKeyListItem",
    "list_api_keys_cross_tenant",
    "get_api_key",
    "project_api_key",
]
