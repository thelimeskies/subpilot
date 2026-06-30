"""Shared model mixins.

- :class:`UUIDPrimaryKey`     - canonical UUID primary key on every domain row.
- :class:`TimestampedModel`   - ``created_at``/``updated_at`` audit fields.
- :class:`TenantScopedModel`  - ``merchant`` + ``environment`` foreign keys.

Concrete domain models compose these mixins. ``TenantScopedModel`` deliberately
uses string references so this module does not import the ``accounts`` app
during Django startup (avoids circular imports).
"""
from __future__ import annotations

import uuid

from django.db import models


class UUIDPrimaryKey(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class TenantScopedModel(models.Model):
    """Adds tenant-scoping FKs. Querysets must always filter by these."""

    merchant = models.ForeignKey(
        "accounts.Merchant",
        on_delete=models.CASCADE,
        related_name="+",
    )
    environment = models.ForeignKey(
        "accounts.Environment",
        on_delete=models.CASCADE,
        related_name="+",
    )

    class Meta:
        abstract = True


class BaseDomainModel(UUIDPrimaryKey, TimestampedModel):
    """Convenience mixin for non-tenant-scoped domain models."""

    class Meta:
        abstract = True


class TenantDomainModel(UUIDPrimaryKey, TimestampedModel, TenantScopedModel):
    """Convenience mixin for tenant-scoped domain models."""

    class Meta:
        abstract = True
