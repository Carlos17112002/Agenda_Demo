from rest_framework import serializers

from apps.tenancy.models import Branch
from apps.tenancy.serializers import TenantOwnedSerializer, request_tenant
from .models import Service


class ServiceSerializer(TenantOwnedSerializer):
    branches = serializers.PrimaryKeyRelatedField(queryset=Branch.objects.all(), many=True, required=False)

    class Meta:
        model = Service
        fields = ["id", "company", "name", "description", "duration_minutes", "price",
                  "buffer_before_minutes", "buffer_after_minutes", "branches", "active",
                  "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_branches(self, branches):
        tenant = request_tenant(self.context["request"])
        if tenant is None:
            raise serializers.ValidationError("Selecciona una empresa.")
        if any(branch.company_id != tenant.id for branch in branches):
            raise serializers.ValidationError("Todas las sucursales deben pertenecer a la empresa activa.")
        return branches
