"""Shared DRF/domain exceptions."""
from __future__ import annotations

from rest_framework.exceptions import APIException


class ServiceError(APIException):
    """Generic service-layer error converted to a 400/422 by DRF."""

    status_code = 422
    default_code = "service_error"
    default_detail = "Request failed."


class ConflictError(APIException):
    status_code = 409
    default_code = "conflict"
    default_detail = "Conflict with existing resource."


class TenantMismatch(APIException):
    status_code = 404  # do not leak existence
    default_code = "not_found"
    default_detail = "Not found."
