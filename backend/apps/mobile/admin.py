from django.contrib import admin

from apps.tenancy.admin import TenantScopedAdmin

from .models import DeviceInstallation, MobileOperation, PushMessage


@admin.register(DeviceInstallation)
class DeviceInstallationAdmin(TenantScopedAdmin):
    list_display = ("user", "platform", "installation_id", "active", "last_seen_at", "company")
    list_filter = ("platform", "active", "company")
    search_fields = ("installation_id", "user__email")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(PushMessage)
class PushMessageAdmin(TenantScopedAdmin):
    list_display = ("title", "user", "kind", "status", "provider", "created_at", "company")
    list_filter = ("kind", "status", "company")
    search_fields = ("title", "user__email")
    readonly_fields = [field.name for field in PushMessage._meta.fields]


@admin.register(MobileOperation)
class MobileOperationAdmin(TenantScopedAdmin):
    list_display = ("operation", "client_id", "status", "created_by", "created_at", "company")
    list_filter = ("operation", "status", "company")
    search_fields = ("client_id", "operation")
    readonly_fields = [field.name for field in MobileOperation._meta.fields]
