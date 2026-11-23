from rest_framework import serializers

from apps.identity.models import Membership
from apps.tenancy.models import Branch
from apps.tenancy.serializers import TenantOwnedSerializer, request_tenant
from .models import BlockedSlot, Break, TimeOff, WorkerProfile, WorkingHours


class WorkerProfileSerializer(TenantOwnedSerializer):
    membership = serializers.PrimaryKeyRelatedField(queryset=Membership.objects.all(), required=False, allow_null=True)
    branches = serializers.PrimaryKeyRelatedField(queryset=Branch.objects.all(), many=True, required=False)
    display_name = serializers.SerializerMethodField()

    class Meta:
        model = WorkerProfile
        fields = ["id", "company", "membership", "first_name", "last_name", "display_name",
                  "email", "phone", "job_title", "color", "branches", "active",
                  "created_at", "updated_at"]
        read_only_fields = ["id", "display_name", "created_at", "updated_at"]

    def get_display_name(self, obj):
        return str(obj)

    def validate_membership(self, membership):
        tenant = request_tenant(self.context["request"])
        if membership and membership.company_id != tenant.id:
            raise serializers.ValidationError("La membresía debe pertenecer a la empresa activa.")
        return membership

    def validate_branches(self, branches):
        tenant = request_tenant(self.context["request"])
        if any(branch.company_id != tenant.id for branch in branches):
            raise serializers.ValidationError("Todas las sucursales deben pertenecer a la empresa activa.")
        return branches


class WorkingHoursSerializer(TenantOwnedSerializer):
    worker = serializers.PrimaryKeyRelatedField(queryset=WorkerProfile.objects.all())
    branch = serializers.PrimaryKeyRelatedField(queryset=Branch.objects.all())

    class Meta:
        model = WorkingHours
        fields = ["id", "company", "worker", "branch", "weekday", "start_time", "end_time",
                  "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate(self, attrs):
        tenant = request_tenant(self.context["request"])
        worker = attrs.get("worker", getattr(self.instance, "worker", None))
        branch = attrs.get("branch", getattr(self.instance, "branch", None))
        start = attrs.get("start_time", getattr(self.instance, "start_time", None))
        end = attrs.get("end_time", getattr(self.instance, "end_time", None))
        weekday = attrs.get("weekday", getattr(self.instance, "weekday", None))
        if worker and worker.company_id != tenant.id:
            raise serializers.ValidationError({"worker": "El trabajador debe pertenecer a la empresa activa."})
        if branch and branch.company_id != tenant.id:
            raise serializers.ValidationError({"branch": "La sucursal debe pertenecer a la empresa activa."})
        if start and end and end <= start:
            raise serializers.ValidationError({"end_time": "La hora de término debe ser posterior al inicio."})
        if worker and branch and weekday is not None and start and end:
            overlaps = WorkingHours.objects.filter(
                company=tenant, worker=worker, branch=branch, weekday=weekday,
                start_time__lt=end, end_time__gt=start,
            )
            if self.instance:
                overlaps = overlaps.exclude(pk=self.instance.pk)
            if overlaps.exists():
                raise serializers.ValidationError("El horario se superpone con otro turno del trabajador.")
        return attrs


class TimeOffSerializer(TenantOwnedSerializer):
    worker = serializers.PrimaryKeyRelatedField(queryset=WorkerProfile.objects.all())
    branch = serializers.PrimaryKeyRelatedField(queryset=Branch.objects.all(), required=False, allow_null=True)

    class Meta:
        model = TimeOff
        fields = ["id", "company", "worker", "branch", "starts_at", "ends_at", "reason",
                  "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate(self, attrs):
        tenant = request_tenant(self.context["request"])
        worker = attrs.get("worker", getattr(self.instance, "worker", None))
        branch = attrs.get("branch", getattr(self.instance, "branch", None))
        starts_at = attrs.get("starts_at", getattr(self.instance, "starts_at", None))
        ends_at = attrs.get("ends_at", getattr(self.instance, "ends_at", None))
        if worker and worker.company_id != tenant.id:
            raise serializers.ValidationError({"worker": "El trabajador debe pertenecer a la empresa activa."})
        if branch and branch.company_id != tenant.id:
            raise serializers.ValidationError({"branch": "La sucursal debe pertenecer a la empresa activa."})
        if starts_at and ends_at and ends_at <= starts_at:
            raise serializers.ValidationError({"ends_at": "El término debe ser posterior al inicio."})
        return attrs


class BreakSerializer(TenantOwnedSerializer):
    worker = serializers.PrimaryKeyRelatedField(queryset=WorkerProfile.objects.all())
    branch = serializers.PrimaryKeyRelatedField(queryset=Branch.objects.all())

    class Meta:
        model = Break
        fields = ["id", "company", "worker", "branch", "weekday", "start_time", "end_time",
                  "label", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate(self, attrs):
        tenant = request_tenant(self.context["request"])
        worker = attrs.get("worker", getattr(self.instance, "worker", None))
        branch = attrs.get("branch", getattr(self.instance, "branch", None))
        start = attrs.get("start_time", getattr(self.instance, "start_time", None))
        end = attrs.get("end_time", getattr(self.instance, "end_time", None))
        weekday = attrs.get("weekday", getattr(self.instance, "weekday", None))
        if worker and worker.company_id != tenant.id:
            raise serializers.ValidationError({"worker": "El trabajador debe pertenecer a la empresa activa."})
        if branch and branch.company_id != tenant.id:
            raise serializers.ValidationError({"branch": "La sucursal debe pertenecer a la empresa activa."})
        if start and end and end <= start:
            raise serializers.ValidationError({"end_time": "La hora de término debe ser posterior al inicio."})
        if worker and branch and weekday is not None and start and end:
            overlaps = Break.objects.filter(
                company=tenant, worker=worker, branch=branch, weekday=weekday,
                start_time__lt=end, end_time__gt=start,
            )
            if self.instance:
                overlaps = overlaps.exclude(pk=self.instance.pk)
            if overlaps.exists():
                raise serializers.ValidationError("La pausa se superpone con otra pausa del trabajador.")
        return attrs


class BlockedSlotSerializer(TenantOwnedSerializer):
    worker = serializers.PrimaryKeyRelatedField(queryset=WorkerProfile.objects.all())
    branch = serializers.PrimaryKeyRelatedField(queryset=Branch.objects.all(), required=False, allow_null=True)

    class Meta:
        model = BlockedSlot
        fields = ["id", "company", "worker", "branch", "starts_at", "ends_at", "reason",
                  "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate(self, attrs):
        tenant = request_tenant(self.context["request"])
        worker = attrs.get("worker", getattr(self.instance, "worker", None))
        branch = attrs.get("branch", getattr(self.instance, "branch", None))
        starts_at = attrs.get("starts_at", getattr(self.instance, "starts_at", None))
        ends_at = attrs.get("ends_at", getattr(self.instance, "ends_at", None))
        if worker and worker.company_id != tenant.id:
            raise serializers.ValidationError({"worker": "El trabajador debe pertenecer a la empresa activa."})
        if branch and branch.company_id != tenant.id:
            raise serializers.ValidationError({"branch": "La sucursal debe pertenecer a la empresa activa."})
        if starts_at and ends_at and ends_at <= starts_at:
            raise serializers.ValidationError({"ends_at": "El término debe ser posterior al inicio."})
        return attrs
