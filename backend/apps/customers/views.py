from apps.tenancy.api import TenantModelViewSet
from .models import Customer
from .serializers import CustomerSerializer


class CustomerViewSet(TenantModelViewSet):
    serializer_class = CustomerSerializer
    audit_name = "customer"
    soft_delete = True
    permission_map = {
        "list": "customers.read", "retrieve": "customers.read",
        "create": "customers.write", "update": "customers.write",
        "partial_update": "customers.write", "destroy": "customers.write",
    }
    search_fields = ["first_name", "last_name", "email", "phone", "document_id"]
    ordering_fields = ["last_name", "first_name", "created_at"]

    def queryset_for_tenant(self, tenant):
        queryset = Customer.objects.filter(company=tenant)
        active = self.request.query_params.get("active")
        if active in {"true", "false"}:
            queryset = queryset.filter(active=active == "true")
        return queryset
