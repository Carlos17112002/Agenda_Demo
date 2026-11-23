from django.utils import timezone
from .models import TenantContext

class TenantContextMiddleware:
    """Resolve the active tenant only from a server-issued, user-bound context token."""
    def __init__(self, get_response):
        self.get_response = get_response
    def __call__(self, request):
        request.tenant = None
        request.tenant_context = None
        context_id = request.headers.get("X-Tenant-Context")
        user = getattr(request, "user", None)
        if context_id and user and user.is_authenticated:
            context = TenantContext.objects.select_related("company").filter(
                pk=context_id, user=user, expires_at__gt=timezone.now(), company__status__in=["trial", "active"]
            ).first()
            if context and user.memberships.filter(company=context.company, active=True).exists():
                request.tenant = context.company
                request.tenant_context = context
                request._tenant_authenticated_user = user
        return self.get_response(request)
