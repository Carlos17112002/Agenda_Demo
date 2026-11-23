from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from .admin_access import has_saas_access
from .models import Membership, PermissionGrant, User

@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    ordering = ("email",)
    list_display = ("email", "username", "is_saas_admin", "is_staff", "is_active")
    fieldsets = ((None, {"fields": ("email", "username", "password")}),
        ("Personal", {"fields": ("first_name", "last_name")}),
        ("Access control", {"fields": ("is_active", "is_staff", "is_superuser", "is_saas_admin", "groups", "user_permissions")}),
        ("Important dates", {"fields": ("last_login", "date_joined", "jwt_valid_after")}))
    add_fieldsets = ((None, {"classes": ("wide",), "fields": ("email", "username", "password1", "password2")}),)
    readonly_fields = ("last_login", "date_joined", "jwt_valid_after")
    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if has_saas_access(request.user):
            return queryset
        return queryset.filter(memberships__company__memberships__user=request.user,
            memberships__company__memberships__active=True,
            memberships__company__memberships__role__in=["owner", "admin"]).distinct()
    def has_view_permission(self, request, obj=None):
        if has_saas_access(request.user):
            return True
        qs = request.user.memberships.filter(active=True, role__in=["owner", "admin"])
        return qs.exists() if obj is None else obj.memberships.filter(company__in=qs.values("company_id"), active=True).exists()
    def has_add_permission(self, request):
        return has_saas_access(request.user)
    def has_change_permission(self, request, obj=None):
        return has_saas_access(request.user)
    def has_delete_permission(self, request, obj=None):
        return has_saas_access(request.user)

@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "company", "role", "active")
    list_filter = ("role", "active")
    search_fields = ("user__email", "company__name")
    readonly_fields = ("id", "created_at")
    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if has_saas_access(request.user):
            return queryset
        return queryset.filter(company__memberships__user=request.user, company__memberships__active=True).distinct()
    def has_view_permission(self, request, obj=None):
        if has_saas_access(request.user):
            return True
        qs = request.user.memberships.filter(active=True, role__in=["owner", "admin"])
        return qs.exists() if obj is None else qs.filter(company=obj.company).exists()
    def has_add_permission(self, request):
        return has_saas_access(request.user)
    def has_change_permission(self, request, obj=None):
        return has_saas_access(request.user)
    def has_delete_permission(self, request, obj=None):
        return has_saas_access(request.user)
    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(PermissionGrant)
class PermissionGrantAdmin(admin.ModelAdmin):
    list_display = ("membership", "permission", "effect", "branch")
    list_filter = ("effect", "permission")
    readonly_fields = ("id", "created_at")
    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if has_saas_access(request.user):
            return queryset
        return queryset.filter(membership__company__memberships__user=request.user,
            membership__company__memberships__active=True).distinct()
    def has_view_permission(self, request, obj=None):
        if has_saas_access(request.user):
            return True
        qs = request.user.memberships.filter(active=True, role__in=["owner", "admin"])
        return qs.exists() if obj is None else qs.filter(company=obj.membership.company).exists()
    def has_add_permission(self, request):
        return has_saas_access(request.user)
    def has_change_permission(self, request, obj=None):
        return has_saas_access(request.user)
