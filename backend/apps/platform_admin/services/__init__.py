"""Service layer for the platform admin app.

Re-exports a small surface so views stay thin.
"""
from .auth import (  # noqa: F401
    InvalidCredentialsError,
    SuspendedAdminError,
    sign_in,
    sign_out,
)
