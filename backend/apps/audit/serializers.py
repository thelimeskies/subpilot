"""Serializers for merchant audit log reads."""
from __future__ import annotations

from rest_framework import serializers

from .models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditLog
        fields = (
            "id",
            "actor_label",
            "actor_role",
            "action",
            "target_type",
            "target_id",
            "metadata",
            "ip_address",
            "occurred_at",
        )
        read_only_fields = fields
