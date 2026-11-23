from django.contrib import admin

from apps.tenancy.admin import TenantScopedAdmin
from .models import Customer


@admin.register(Customer)
class CustomerAdmin(TenantScopedAdmin):
    list_display = ("first_name", "last_name", "company", "email", "phone", "active")
    list_filter = ("active", "company")
    search_fields = ("first_name", "last_name", "email", "phone", "document_id")
    readonly_fields = ("id", "created_at", "updated_at")
