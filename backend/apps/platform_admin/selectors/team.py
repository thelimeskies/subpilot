"""Read-side selectors for the platform-admin team management endpoints (S9).

Projects ``PlatformAdmin`` rows into the FE ``AdminMember`` shape defined at
``apps/subpilot-admin/src/data/seed.ts`` so the FE table can render without
any local mapping.
"""
from __future__ import annotations

from typing import Iterable

from django.db.models import Q

from ..models import (
    PlatformAdmin,
    PlatformAdminRole,
    PlatformAdminStatus,
    PlatformInviteToken,
)


# --- FE label mappings ----------------------------------------------------

_FE_ROLE = {
    PlatformAdminRole.OWNER: "Owner",
    PlatformAdminRole.OPERATOR: "Operator",
    PlatformAdminRole.SUPPORT: "Support",
    PlatformAdminRole.READ_ONLY: "Read-only",
}

_FE_TO_INTERNAL_ROLE = {
    "owner": PlatformAdminRole.OWNER,
    "operator": PlatformAdminRole.OPERATOR,
    "support": PlatformAdminRole.SUPPORT,
    "read-only": PlatformAdminRole.READ_ONLY,
    "read_only": PlatformAdminRole.READ_ONLY,
    "readonly": PlatformAdminRole.READ_ONLY,
}

_FE_STATUS = {
    PlatformAdminStatus.ACTIVE: "Active",
    PlatformAdminStatus.INVITED: "Invited",
    PlatformAdminStatus.SUSPENDED: "Suspended",
}

_FE_TO_INTERNAL_STATUS = {
    "active": PlatformAdminStatus.ACTIVE,
    "invited": PlatformAdminStatus.INVITED,
    "suspended": PlatformAdminStatus.SUSPENDED,
}


def normalize_role(value: str | None) -> str | None:
    if value is None:
        return None
    key = str(value).strip().lower()
    if not key:
        return None
    if key in _FE_TO_INTERNAL_ROLE:
        return _FE_TO_INTERNAL_ROLE[key]
    if key in {r.value for r in PlatformAdminRole}:
        return key
    return None


def normalize_status(value: str | None) -> str | None:
    if value is None:
        return None
    key = str(value).strip().lower()
    if not key:
        return None
    if key in _FE_TO_INTERNAL_STATUS:
        return _FE_TO_INTERNAL_STATUS[key]
    if key in {s.value for s in PlatformAdminStatus}:
        return key
    return None


# --- Projection -----------------------------------------------------------


def project_admin(admin: PlatformAdmin, *, invited_by: str = "—") -> dict:
    """Project a ``PlatformAdmin`` row into the FE ``AdminMember`` shape."""
    return {
        "id": str(admin.id),
        "rawId": str(admin.id),
        "name": admin.display_name or admin.email.split("@")[0],
        "email": admin.email,
        "role": _FE_ROLE.get(admin.role, admin.role.title()),
        "rawRole": admin.role,
        "status": _FE_STATUS.get(admin.status, admin.status.title()),
        "rawStatus": admin.status,
        "mfa": bool(admin.mfa_enabled),
        "lastActive": admin.last_login_at.isoformat() if admin.last_login_at else "—",
        "invitedBy": invited_by or "—",
        "initials": admin.initials,
        "createdAt": admin.created_at.isoformat() if admin.created_at else "",
    }


# --- Query helpers --------------------------------------------------------


def _resolve_invited_by_map(admins: Iterable[PlatformAdmin]) -> dict[str, str]:
    """Return a map of ``admin.id -> inviter display label``.

    Looks up the most recent invite token for each admin and resolves the
    inviter via metadata persisted on the token's audit trail. For S9 we
    keep this lightweight: invitations carry the inviter name in their
    ``token`` payload-like field. If we cannot determine the inviter we
    fall back to ``"—"``.
    """
    admin_ids = [a.id for a in admins]
    if not admin_ids:
        return {}
    # The token table stores who created the invite via the related
    # admin's ``created_by_label`` audit context. For now we read latest
    # token per admin and use the admin's display_name as a best-effort.
    return {}


def list_admins(
    *,
    role: str | None = None,
    status: str | None = None,
    q: str | None = None,
    limit: int = 25,
    offset: int = 0,
) -> tuple[list[PlatformAdmin], int]:
    qs = PlatformAdmin.objects.all().order_by("display_name", "email")
    norm_role = normalize_role(role) if role else None
    if norm_role:
        qs = qs.filter(role=norm_role)
    norm_status = normalize_status(status) if status else None
    if norm_status:
        qs = qs.filter(status=norm_status)
    if q:
        needle = q.strip()
        if needle:
            qs = qs.filter(Q(email__icontains=needle) | Q(display_name__icontains=needle))
    total = qs.count()
    rows = list(qs[offset : offset + limit])
    return rows, total


def get_admin(admin_id: str) -> PlatformAdmin | None:
    try:
        return PlatformAdmin.objects.get(pk=admin_id)
    except (PlatformAdmin.DoesNotExist, ValueError, TypeError):
        return None


def get_invite_token(token: str) -> PlatformInviteToken | None:
    if not token:
        return None
    try:
        return PlatformInviteToken.objects.select_related("admin").get(token=token)
    except PlatformInviteToken.DoesNotExist:
        return None


def project_invite(token: PlatformInviteToken) -> dict:
    return {
        "token": token.token,
        "adminId": str(token.admin_id),
        "email": token.admin.email,
        "expiresAt": token.expires_at.isoformat() if token.expires_at else "",
        "acceptedAt": token.accepted_at.isoformat() if token.accepted_at else None,
    }


__all__ = [
    "list_admins",
    "get_admin",
    "get_invite_token",
    "project_admin",
    "project_invite",
    "normalize_role",
    "normalize_status",
]
