"""DRF authentication for the platform admin console.

Reads the platform admin id stashed in Django's session under the
``_platform_admin_id`` key. The same Django session backend is used as
for the merchant dashboard, but the storage key is distinct so the two
auth domains can never accidentally cross.
"""
from __future__ import annotations

from rest_framework import authentication

from .models import PlatformAdmin, PlatformAdminStatus

SESSION_KEY = "_platform_admin_id"


class PlatformAdminAuthentication(authentication.BaseAuthentication):
    """Resolve a ``PlatformAdmin`` from the Django session.

    Returns ``(platform_admin, None)`` on success — DRF will then expose
    the admin as ``request.user``. The admin satisfies the duck-typed
    user interface (``is_authenticated``, ``is_active``…) needed by
    ``IsAuthenticated``.
    """

    def authenticate(self, request):
        session = getattr(request, "session", None)
        if session is None:
            return None
        admin_id = session.get(SESSION_KEY)
        if not admin_id:
            return None
        try:
            admin = PlatformAdmin.objects.get(pk=admin_id)
        except PlatformAdmin.DoesNotExist:
            # Stale session — clear and bail.
            session.pop(SESSION_KEY, None)
            return None
        if admin.status != PlatformAdminStatus.ACTIVE:
            session.pop(SESSION_KEY, None)
            return None
        # Mirror as request.platform_admin for views that prefer the explicit name.
        request.platform_admin = admin
        return (admin, None)

    def authenticate_header(self, request):
        return 'Session realm="platform-admin"'
