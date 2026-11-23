from django.contrib import admin

from apps.tenancy.admin import TenantScopedAdmin
from .models import Notification


@admin.register(Notification)
class NotificationAdmin(TenantScopedAdmin):
    list_display = ("kind", "recipient_email", "booking", "status", "created_at", "sent_at")
    list_filter = ("kind", "status", "company")
    search_fields = ("recipient_email", "subject", "booking__public_code")
    readonly_fields = [field.name for field in Notification._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
