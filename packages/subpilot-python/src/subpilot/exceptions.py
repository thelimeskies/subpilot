from __future__ import annotations

from typing import Any


class SubPilotError(Exception):
    """Base exception for the SubPilot Python package."""


class SubPilotConnectionError(SubPilotError):
    """Raised when the client cannot reach the API."""


class SubPilotAPIError(SubPilotError):
    """Raised for non-2xx API responses."""

    def __init__(self, message: str, *, status_code: int, payload: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload
