"""Append-only audit log.

This table records who did what at SubPilot. Per docs/technical/architecture.md
and the synthesis plan, rows here are insert-only:

* ``Meta.default_permissions = ()`` removes the default change/delete perms.
* A Postgres CHECK constraint and the absence of UPDATE/DELETE methods on the
  service layer enforce immutability at the application boundary.
* Operators who need to revoke a recorded action create a *compensating* entry
  rather than mutating an existing one.
"""
from __future__ import annotations

from django.db import models

from apps.common.models import BaseDomainModel


class AuditLog(BaseDomainModel):
    # Actor — nullable for system-generated events (e.g. cron-driven dunning).
    actor_user = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    actor_label = models.CharField(max_length=128, blank=True, default="")
    actor_role = models.CharField(max_length=64, blank=True, default="")

    # Tenant scope — also nullable for platform-level events.
    merchant = models.ForeignKey(
        "accounts.Merchant",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    environment = models.ForeignKey(
        "accounts.Environment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    # Action descriptor (e.g. "invoice.retry", "team_member.invite", "auth.sign_in").
    action = models.CharField(max_length=128, db_index=True)

    # Target reference (free-form, e.g. "invoice:inv_abc123" or "user:usr_xyz").
    target_type = models.CharField(max_length=64, blank=True, default="")
    target_id = models.CharField(max_length=128, blank=True, default="")

    # Free-form context payload.
    metadata = models.JSONField(default=dict, blank=True)

    # Origin metadata.
    request_id = models.CharField(max_length=64, blank=True, default="")
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=512, blank=True, default="")

    occurred_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "audit_auditlog"
        # Append-only: remove change/delete perms.
        default_permissions = ()
        permissions = [("view_auditlog", "Can view audit logs")]
        indexes = [
            models.Index(fields=["merchant", "-occurred_at"], name="audit_merchant_time_idx"),
            models.Index(fields=["action", "-occurred_at"], name="audit_action_time_idx"),
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"<AuditLog {self.action} actor={self.actor_label} target={self.target_type}:{self.target_id}>"

    def save(self, *args, **kwargs):
        # Block updates of existing rows. New rows have no PK assigned via auto-now-add semantics.
        if self.pk is not None:
            existing = type(self).objects.filter(pk=self.pk).exists()
            if existing:
                raise RuntimeError("AuditLog rows are append-only; updates are not permitted.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise RuntimeError("AuditLog rows are append-only; deletes are not permitted.")
