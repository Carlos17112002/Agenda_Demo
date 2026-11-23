from django.contrib import admin

from apps.tenancy.admin import TenantScopedAdmin
from .models import Service


@admin.register(Service)
class ServiceAdmin(TenantScopedAdmin):
    list_display = ("name", "company", "duration_minutes", "price", "active")
    list_filter = ("active", "company")
    search_fields = ("name", "description")
    readonly_fields = ("id", "created_at", "updated_at")
    filter_horizontal = ("branches",)
