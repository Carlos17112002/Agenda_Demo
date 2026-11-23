from django.utils import timezone
from apps.identity.authentication import RevocableJWTAuthentication
from .models import TenantContext

def resolve_tenant(request, user):
    request.tenant = None
    request.tenant_context = None
    context_id = request.headers.get("X-Tenant-Context")
    if context_id:
        context = TenantContext.objects.select_related("company").filter(
            pk=context_id, user=user, expires_at__gt=timezone.now(),
            company__status__in=["trial", "active"],
            company__memberships__user=user, company__memberships__active=True,
        ).first()
        if context:
            request.tenant = context.company
            request.tenant_context = context
    return request.tenant

class TenantJWTAuthentication(RevocableJWTAuthentication):
    """Authenticate JWT and resolve the active, user-bound tenant context in DRF."""
    def authenticate(self, request):
        result = super().authenticate(request)
        if result is None:
            return None
        user, token = result
        resolve_tenant(request, user)
        return user, token
