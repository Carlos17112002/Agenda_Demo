from apps.tenancy.api import TenantModelViewSet
from .models import Service
from .serializers import ServiceSerializer


class ServiceViewSet(TenantModelViewSet):
    serializer_class = ServiceSerializer
    audit_name = "service"
    soft_delete = True
    permission_map = {
        "list": "catalog.read", "retrieve": "catalog.read",
        "create": "catalog.write", "update": "catalog.write",
        "partial_update": "catalog.write", "destroy": "catalog.write",
    }
    search_fields = ["name", "description"]
    ordering_fields = ["name", "price", "duration_minutes", "created_at"]

    def queryset_for_tenant(self, tenant):
        queryset = Service.objects.filter(company=tenant).prefetch_related("branches")
        active = self.request.query_params.get("active")
        if active in {"true", "false"}:
            queryset = queryset.filter(active=active == "true")
        branch = self.request.query_params.get("branch")
        if branch:
            queryset = queryset.filter(branches__id=branch)
        return queryset.distinct()
