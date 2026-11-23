from rest_framework.exceptions import PermissionDenied

class TenantQuerysetMixin:
    """Fail closed: tenant-scoped viewsets must have an authorized tenant context."""
    def get_queryset(self):
        tenant = getattr(self.request, "tenant", None)
        if tenant is None:
            raise PermissionDenied("No hay una empresa autorizada en el contexto.")
        return super().get_queryset().filter(company=tenant)

    def perform_create(self, serializer):
        tenant = getattr(self.request, "tenant", None)
        if tenant is None:
            raise PermissionDenied("No hay una empresa autorizada en el contexto.")
        serializer.save(company=tenant)
