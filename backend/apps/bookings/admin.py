from django.contrib import admin

from apps.tenancy.admin import TenantScopedAdmin
from .models import Booking


@admin.register(Booking)
class BookingAdmin(TenantScopedAdmin):
    list_display = ("public_code", "start_at", "status", "service_name", "worker", "branch", "company")
    list_filter = ("status", "source", "company", "branch")
    search_fields = ("public_code", "service_name", "customer__first_name",
                     "customer__last_name", "customer__email")
    date_hierarchy = "start_at"
    readonly_fields = [field.name for field in Booking._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
