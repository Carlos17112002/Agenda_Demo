from django.contrib import admin
from apps.identity.admin_access import has_saas_access
from .models import AuditEvent

@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ("occurred_at", "company", "actor", "action", "entity_type", "entity_id")
    readonly_fields = [field.name for field in AuditEvent._meta.fields]
    list_per_page = 50
    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if has_saas_access(request.user):
            return queryset
        return queryset.filter(company__memberships__user=request.user, company__memberships__active=True,
            company__memberships__role__in=["owner", "admin"]).distinct()
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False
