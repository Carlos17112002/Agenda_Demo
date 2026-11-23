from apps.tenancy.api import TenantModelViewSet
from .models import BlockedSlot, Break, TimeOff, WorkerProfile, WorkingHours
from .serializers import (
    BlockedSlotSerializer, BreakSerializer, TimeOffSerializer, WorkerProfileSerializer,
    WorkingHoursSerializer,
)

WORKFORCE_READ = {"list": "workforce.read", "retrieve": "workforce.read"}
WORKFORCE_WRITE = {
    "create": "workforce.write", "update": "workforce.write",
    "partial_update": "workforce.write", "destroy": "workforce.write",
}


def active_filter(view, queryset):
    active = view.request.query_params.get("active")
    if active in {"true", "false"}:
        return queryset.filter(active=active == "true")
    return queryset


class WorkerProfileViewSet(TenantModelViewSet):
    serializer_class = WorkerProfileSerializer
    audit_name = "worker"
    soft_delete = True
    plan_limit_feature = "workers"
    permission_map = {**WORKFORCE_READ, **WORKFORCE_WRITE}
    search_fields = ["first_name", "last_name", "email", "phone", "job_title"]
    ordering_fields = ["last_name", "first_name", "created_at"]

    def queryset_for_tenant(self, tenant):
        queryset = WorkerProfile.objects.filter(company=tenant).prefetch_related("branches")
        branch = self.request.query_params.get("branch")
        if branch:
            queryset = queryset.filter(branches__id=branch)
        return active_filter(self, queryset).distinct()

    def get_limit_count(self, tenant):
        return WorkerProfile.objects.filter(company=tenant, active=True).count()


class WorkingHoursViewSet(TenantModelViewSet):
    serializer_class = WorkingHoursSerializer
    audit_name = "working_hours"
    permission_map = {**WORKFORCE_READ, **WORKFORCE_WRITE}
    ordering_fields = ["weekday", "start_time"]

    def queryset_for_tenant(self, tenant):
        queryset = WorkingHours.objects.filter(company=tenant).select_related("worker", "branch")
        worker = self.request.query_params.get("worker")
        branch = self.request.query_params.get("branch")
        if worker:
            queryset = queryset.filter(worker_id=worker)
        if branch:
            queryset = queryset.filter(branch_id=branch)
        return queryset


class TimeOffViewSet(TenantModelViewSet):
    serializer_class = TimeOffSerializer
    audit_name = "time_off"
    permission_map = {**WORKFORCE_READ, **WORKFORCE_WRITE}
    ordering_fields = ["starts_at"]

    def queryset_for_tenant(self, tenant):
        queryset = TimeOff.objects.filter(company=tenant).select_related("worker", "branch")
        worker = self.request.query_params.get("worker")
        branch = self.request.query_params.get("branch")
        if worker:
            queryset = queryset.filter(worker_id=worker)
        if branch:
            queryset = queryset.filter(branch_id=branch)
        return queryset


class BreakViewSet(TenantModelViewSet):
    serializer_class = BreakSerializer
    audit_name = "break"
    permission_map = {**WORKFORCE_READ, **WORKFORCE_WRITE}
    ordering_fields = ["weekday", "start_time"]

    def queryset_for_tenant(self, tenant):
        queryset = Break.objects.filter(company=tenant).select_related("worker", "branch")
        worker = self.request.query_params.get("worker")
        branch = self.request.query_params.get("branch")
        if worker:
            queryset = queryset.filter(worker_id=worker)
        if branch:
            queryset = queryset.filter(branch_id=branch)
        return queryset


class BlockedSlotViewSet(TenantModelViewSet):
    serializer_class = BlockedSlotSerializer
    audit_name = "blocked_slot"
    permission_map = {**WORKFORCE_READ, **WORKFORCE_WRITE}
    ordering_fields = ["starts_at"]

    def queryset_for_tenant(self, tenant):
        queryset = BlockedSlot.objects.filter(company=tenant).select_related("worker", "branch")
        worker = self.request.query_params.get("worker")
        branch = self.request.query_params.get("branch")
        if worker:
            queryset = queryset.filter(worker_id=worker)
        if branch:
            queryset = queryset.filter(branch_id=branch)
        return queryset
