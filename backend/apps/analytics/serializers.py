"""Analytics serializers — read-only DTOs for the dashboard overview."""
from __future__ import annotations

from rest_framework import serializers


class DashboardOverviewSerializer(serializers.Serializer):
    mrr_minor = serializers.IntegerField()
    active_subscriptions = serializers.IntegerField()
    trialing_subscriptions = serializers.IntegerField()
    past_due_subscriptions = serializers.IntegerField()
    revenue_at_risk_minor = serializers.IntegerField()
    collected_revenue_minor = serializers.IntegerField()
    recovery_rate_pct = serializers.FloatField()
    open_invoices_minor = serializers.IntegerField()
    currency = serializers.CharField()
