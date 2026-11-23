from django.contrib import admin

from apps.tenancy.admin import TenantScopedAdmin
from .models import BlockedSlot, Break, TimeOff, WorkerProfile, WorkingHours


@admin.register(WorkerProfile)
class WorkerProfileAdmin(TenantScopedAdmin):
    list_display = ("first_name", "last_name", "company", "job_title", "active")
    list_filter = ("active", "company")
    search_fields = ("first_name", "last_name", "email", "phone", "job_title")
    readonly_fields = ("id", "created_at", "updated_at")
    filter_horizontal = ("branches",)


@admin.register(WorkingHours)
class WorkingHoursAdmin(TenantScopedAdmin):
    list_display = ("worker", "branch", "weekday", "start_time", "end_time")
    list_filter = ("company", "branch", "weekday")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(TimeOff)
class TimeOffAdmin(TenantScopedAdmin):
    list_display = ("worker", "branch", "starts_at", "ends_at", "reason")
    list_filter = ("company", "branch")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(Break)
class BreakAdmin(TenantScopedAdmin):
    list_display = ("worker", "branch", "weekday", "start_time", "end_time", "label")
    list_filter = ("company", "branch", "weekday")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(BlockedSlot)
class BlockedSlotAdmin(TenantScopedAdmin):
    list_display = ("worker", "branch", "starts_at", "ends_at", "reason")
    list_filter = ("company", "branch")
    readonly_fields = ("id", "created_at", "updated_at")
