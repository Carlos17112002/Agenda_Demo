from django.contrib import admin
from apps.identity.admin_access import has_saas_access
from .models import Branch, Company, TenantContext


class TenantScopedAdmin(admin.ModelAdmin):
    """Show only records of companies where the user has an active membership."""

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if has_saas_access(request.user):
            return queryset
        return queryset.filter(company__memberships__user=request.user,
                               company__memberships__active=True).distinct()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("name", "slug", "tax_identifier")
    readonly_fields = ("id", "created_at", "updated_at")
    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if has_saas_access(request.user):
            return queryset
        return queryset.filter(memberships__user=request.user, memberships__active=True).distinct()
    def has_view_permission(self, request, obj=None):
        if has_saas_access(request.user):
            return True
        if obj is None:
            return request.user.memberships.filter(active=True, role__in=["owner", "admin"]).exists()
        return request.user.memberships.filter(company=obj, active=True, role__in=["owner", "admin"]).exists()
    def has_add_permission(self, request):
        return has_saas_access(request.user)
    def has_change_permission(self, request, obj=None):
        return has_saas_access(request.user)
    def has_delete_permission(self, request, obj=None):
        return has_saas_access(request.user)

@admin.register(Branch)
class BranchAdmin(TenantScopedAdmin):
    list_display = ("name", "code", "company", "timezone", "active")
    list_filter = ("active", "company")
    readonly_fields = ("id", "created_at", "updated_at")

@admin.register(TenantContext)
class TenantContextAdmin(admin.ModelAdmin):
    list_display = ("user", "company", "created_at", "expires_at")
    readonly_fields = [field.name for field in TenantContext._meta.fields]
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False
