"""Platform Admin app — cross-tenant SubPilot operator console.

Isolated from the merchant ``accounts`` app: separate model
(``PlatformAdmin``), separate permission (``IsPlatformAdmin``), and a
distinct session key (``_platform_admin_id``). Never reuses the merchant
``User`` model nor the ``is_staff`` bypass at
[apps/accounts/middleware.py:49](file:///Users/mac/Desktop/Projects/HackathonxNomba/backend/apps/accounts/middleware.py#L49).
"""
