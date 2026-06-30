"""DRF serializers for the platform admin console.

Each resource maps backend fields to the **exact** camelCase shapes
defined in
[apps/subpilot-admin/src/data/seed.ts](file:///Users/mac/Desktop/Projects/HackathonxNomba/apps/subpilot-admin/src/data/seed.ts)
so the frontend can drop in real API calls without changing TypeScript
types.
"""
from __future__ import annotations

from rest_framework import serializers

from .models import PlatformAdmin


# --- Auth ---------------------------------------------------------------

class SignInSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(min_length=1, write_only=True)


def admin_payload(admin: PlatformAdmin) -> dict:
    """Shape matching ``AdminUser`` in
    [auth/AuthContext.tsx](file:///Users/mac/Desktop/Projects/HackathonxNomba/apps/subpilot-admin/src/auth/AuthContext.tsx)."""
    role_to_fe = {
        "owner": "Owner",
        "operator": "Operator",
        "support": "Support",
        "read_only": "Read-only",
    }
    return {
        "id": str(admin.id),
        "name": admin.display_name or admin.email,
        "email": admin.email,
        "role": role_to_fe.get(admin.role, "Read-only"),
        "initials": admin.initials,
    }
