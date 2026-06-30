"""Dunning serializers."""
from __future__ import annotations

from rest_framework import serializers

from .models import DunningPolicy, DunningRun, NotificationLog


class DunningPolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = DunningPolicy
        fields = [
            "id",
            "name",
            "retry_offsets_days",
            "grace_period_days",
            "final_action",
            "notify_email",
            "notify_sms",
            "notify_webhook",
            "hard_failure_behavior",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class CreateDunningPolicyPayload(serializers.Serializer):
    name = serializers.CharField(max_length=200)
    retry_offsets_days = serializers.ListField(child=serializers.IntegerField(min_value=0, max_value=365))
    grace_period_days = serializers.IntegerField(min_value=0, default=0)
    final_action = serializers.ChoiceField(
        choices=DunningPolicy.FinalAction.choices, default=DunningPolicy.FinalAction.CANCEL
    )
    notify_email = serializers.BooleanField(default=True)
    notify_sms = serializers.BooleanField(default=False)
    notify_webhook = serializers.BooleanField(default=True)
    hard_failure_behavior = serializers.ChoiceField(
        choices=DunningPolicy.HardFailureBehavior.choices,
        default=DunningPolicy.HardFailureBehavior.STOP,
    )


class UpdateDunningPolicyPayload(serializers.Serializer):
    name = serializers.CharField(max_length=200, required=False)
    retry_offsets_days = serializers.ListField(
        child=serializers.IntegerField(min_value=0, max_value=365), required=False
    )
    grace_period_days = serializers.IntegerField(min_value=0, required=False)
    final_action = serializers.ChoiceField(
        choices=DunningPolicy.FinalAction.choices, required=False
    )
    notify_email = serializers.BooleanField(required=False)
    notify_sms = serializers.BooleanField(required=False)
    notify_webhook = serializers.BooleanField(required=False)
    hard_failure_behavior = serializers.ChoiceField(
        choices=DunningPolicy.HardFailureBehavior.choices, required=False
    )


class DunningRunSerializer(serializers.ModelSerializer):
    class Meta:
        model = DunningRun
        fields = [
            "id",
            "invoice",
            "subscription",
            "policy",
            "status",
            "attempt_count",
            "started_at",
            "next_retry_at",
            "recovered_at",
            "exhausted_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class NotificationLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationLog
        fields = [
            "id",
            "dunning_run",
            "channel",
            "status",
            "template_key",
            "sent_at",
            "failure_message",
            "created_at",
        ]
        read_only_fields = fields
