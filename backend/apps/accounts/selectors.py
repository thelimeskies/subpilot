"""Read-only query helpers (selectors).

Per docs/delivery/django-file-by-file-build-plan.md: query composition lives
here, not in views or serializers.
"""
from __future__ import annotations

from .models import Environment, TeamMember


def current_team_member(user, merchant) -> TeamMember | None:
    if user is None or merchant is None:
        return None
    return (
        TeamMember.objects.select_related("merchant")
        .filter(user=user, merchant=merchant, status=TeamMember.Status.ACTIVE)
        .first()
    )


def environment_for(merchant, mode: str = "test") -> Environment | None:
    return Environment.objects.filter(merchant=merchant, mode=mode).first()
