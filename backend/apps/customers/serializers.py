from rest_framework import serializers

from apps.tenancy.serializers import TenantOwnedSerializer
from .models import Customer


class CustomerSerializer(TenantOwnedSerializer):
    display_name = serializers.SerializerMethodField()

    class Meta:
        model = Customer
        fields = ["id", "company", "first_name", "last_name", "display_name", "email",
                  "phone", "document_id", "notes", "active", "created_at", "updated_at"]
        read_only_fields = ["id", "display_name", "created_at", "updated_at"]

    def get_display_name(self, obj):
        return str(obj)
