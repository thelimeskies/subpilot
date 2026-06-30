"""Tenant-scoped audit log API."""
from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import HasCapability
from apps.common.permissions import HasTenantContext

from .models import AuditLog
from .serializers import AuditLogSerializer


@extend_schema(responses=AuditLogSerializer(many=True))
class AuditLogListView(APIView):
    permission_classes = [IsAuthenticated, HasTenantContext, HasCapability("view_audit_logs")]

    def get(self, request):
        rows = (
            AuditLog.objects.filter(merchant=request.merchant)
            .select_related("actor_user")
            .order_by("-occurred_at")[:100]
        )
        return Response(AuditLogSerializer(rows, many=True).data)
