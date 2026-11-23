from rest_framework import permissions, status, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from .authentication import resolve_tenant
from .permissions import HasTenantContext, HasTenantPermission


class TenantModelViewSet(viewsets.ModelViewSet):
    """Tenant-scoped CRUD with per-action permissions, audit trail and soft delete."""

    permission_classes = [permissions.IsAuthenticated, HasTenantContext, HasTenantPermission]
    permission_map = {}
    audit_name = None
    soft_delete = False
    plan_limit_feature = None

    def get_required_tenant_permission(self):
        return self.permission_map.get(self.action)

    def get_tenant(self):
        tenant = getattr(self.request, "tenant", None)
        if tenant is None:
            tenant = resolve_tenant(self.request, self.request.user)
        if tenant is None:
            raise PermissionDenied("Selecciona una empresa.")
        return tenant

    def get_queryset(self):
        return self.queryset_for_tenant(self.get_tenant())

    def queryset_for_tenant(self, tenant):
        return self.queryset.filter(company=tenant)

    def perform_create(self, serializer):
        tenant = self.get_tenant()
        if self.plan_limit_feature:
            from apps.billing.gating import enforce_plan_limit
            enforce_plan_limit(tenant, self.plan_limit_feature, self.get_limit_count(tenant))
        instance = serializer.save(company=tenant)
        self._audit("created", instance)

    def get_limit_count(self, tenant):
        return self.queryset_for_tenant(tenant).count()

    def perform_update(self, serializer):
        instance = serializer.save()
        self._audit("updated", instance)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if self.soft_delete:
            instance.active = False
            instance.save(update_fields=["active", "updated_at"])
            self._audit("deactivated", instance)
        else:
            self._audit("deleted", instance)
            instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    def _audit(self, action, instance):
        if not self.audit_name:
            return
        from apps.audit.services import record_event
        record_event(company=self.get_tenant(), actor=self.request.user,
                     action=f"{self.audit_name}.{action}", instance=instance)
