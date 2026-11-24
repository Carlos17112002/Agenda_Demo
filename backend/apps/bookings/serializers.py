from rest_framework import serializers

from apps.catalog.models import Service
from apps.customers.models import Customer
from apps.tenancy.models import Branch
from apps.tenancy.serializers import request_tenant
from apps.workforce.models import WorkerProfile

from .availability import (
    service_available_at_branch, validate_search_date, worker_available_at_branch,
)
from .models import Booking
from .services import public_reschedule_allowed


def _tenant(request):
    return request_tenant(request)


def _ensure_company(value, company, field):
    if value is not None and value.company_id != company.id:
        raise serializers.ValidationError({field: "El recurso debe pertenecer a la empresa activa."})
    return value


class BookingSerializer(serializers.ModelSerializer):
    company = serializers.UUIDField(source="company_id", read_only=True)
    branch = serializers.UUIDField(source="branch_id", read_only=True)
    branch_name = serializers.CharField(source="branch.name", read_only=True)
    customer = serializers.UUIDField(source="customer_id", read_only=True)
    customer_name = serializers.SerializerMethodField()
    customer_email = serializers.EmailField(source="customer.email", read_only=True)
    service = serializers.UUIDField(source="service_id", read_only=True)
    worker = serializers.UUIDField(source="worker_id", read_only=True)
    worker_name = serializers.SerializerMethodField()
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    source_display = serializers.CharField(source="get_source_display", read_only=True)

    class Meta:
        model = Booking
        fields = [
            "id", "company", "branch", "branch_name", "customer", "customer_name",
            "customer_email", "service", "service_name", "worker", "worker_name",
            "start_at", "end_at", "duration_minutes", "price", "status", "status_display",
            "source", "source_display", "notes", "public_code", "canceled_at",
            "canceled_reason", "created_at", "updated_at",
        ]
        read_only_fields = fields

    def get_customer_name(self, obj):
        return str(obj.customer)

    def get_worker_name(self, obj):
        return str(obj.worker)


class BookingCreateSerializer(serializers.Serializer):
    branch = serializers.PrimaryKeyRelatedField(queryset=Branch.objects.all())
    customer = serializers.PrimaryKeyRelatedField(queryset=Customer.objects.all())
    service = serializers.PrimaryKeyRelatedField(queryset=Service.objects.all())
    worker = serializers.PrimaryKeyRelatedField(queryset=WorkerProfile.objects.all())
    start_at = serializers.DateTimeField()
    notes = serializers.CharField(required=False, allow_blank=True, max_length=2000)

    def validate(self, attrs):
        company = _tenant(self.context["request"])
        for field in ["branch", "customer", "service", "worker"]:
            _ensure_company(attrs[field], company, field)
        return attrs


class BookingNotesSerializer(serializers.ModelSerializer):
    notes = serializers.CharField(required=False, allow_blank=True, max_length=2000)

    class Meta:
        model = Booking
        fields = ["notes"]


class RescheduleSerializer(serializers.Serializer):
    start_at = serializers.DateTimeField()
    worker = serializers.PrimaryKeyRelatedField(
        queryset=WorkerProfile.objects.all(), required=False, allow_null=True,
    )
    reason = serializers.CharField(required=False, allow_blank=True, max_length=240)

    def validate_worker(self, worker):
        company = _tenant(self.context["request"])
        return _ensure_company(worker, company, "worker") if worker else worker


class TransitionSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, max_length=240)


class PublicRescheduleSerializer(serializers.Serializer):
    start_at = serializers.DateTimeField()


class AvailabilityQuerySerializer(serializers.Serializer):
    branch = serializers.PrimaryKeyRelatedField(queryset=Branch.objects.all())
    service = serializers.PrimaryKeyRelatedField(queryset=Service.objects.all())
    worker = serializers.PrimaryKeyRelatedField(queryset=WorkerProfile.objects.all())
    date = serializers.DateField()
    exclude_booking = serializers.CharField(required=False, allow_blank=False, max_length=16)

    def validate(self, attrs):
        company = self.context.get("company") or _tenant(self.context["request"])
        branch = attrs["branch"]
        service = attrs["service"]
        worker = attrs["worker"]
        for field in ["branch", "service", "worker"]:
            _ensure_company(attrs[field], company, field)
        if not branch.active:
            raise serializers.ValidationError({"branch": "La sucursal está inactiva."})
        if not service_available_at_branch(service, branch):
            raise serializers.ValidationError({"service": "El servicio no está disponible en esta sucursal."})
        if not worker_available_at_branch(worker, branch):
            raise serializers.ValidationError({"worker": "El trabajador no atiende en esta sucursal."})
        validate_search_date(branch, attrs["date"])
        attrs["exclude_pk"] = None
        code = attrs.pop("exclude_booking", "")
        if code:
            booking = Booking.objects.filter(company=company, public_code__iexact=code).first()
            if booking is None or booking.worker_id != worker.id:
                raise serializers.ValidationError({"exclude_booking": "Reserva no encontrada."})
            attrs["exclude_pk"] = booking.pk
        return attrs


class PublicBookingCreateSerializer(serializers.Serializer):
    branch = serializers.PrimaryKeyRelatedField(queryset=Branch.objects.all())
    service = serializers.PrimaryKeyRelatedField(queryset=Service.objects.all())
    worker = serializers.PrimaryKeyRelatedField(queryset=WorkerProfile.objects.all())
    start_at = serializers.DateTimeField()
    first_name = serializers.CharField(max_length=120)
    last_name = serializers.CharField(max_length=120, required=False, allow_blank=True)
    email = serializers.EmailField()
    phone = serializers.CharField(max_length=32, required=False, allow_blank=True)
    notes = serializers.CharField(max_length=500, required=False, allow_blank=True)

    def validate(self, attrs):
        company = self.context["company"]
        for field in ["branch", "service", "worker"]:
            _ensure_company(attrs[field], company, field)
        return attrs


class PublicBookingSerializer(serializers.ModelSerializer):
    branch = serializers.UUIDField(source="branch_id", read_only=True)
    branch_name = serializers.CharField(source="branch.name", read_only=True)
    branch_timezone = serializers.CharField(source="branch.timezone", read_only=True)
    service = serializers.UUIDField(source="service_id", read_only=True)
    worker = serializers.UUIDField(source="worker_id", read_only=True)
    worker_name = serializers.SerializerMethodField()
    customer_first_name = serializers.CharField(source="customer.first_name", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    can_reschedule = serializers.SerializerMethodField()

    class Meta:
        model = Booking
        fields = [
            "public_code", "status", "status_display", "service_name", "worker_name",
            "branch", "branch_name", "branch_timezone", "service", "worker", "start_at",
            "end_at", "duration_minutes", "price", "customer_first_name", "can_reschedule",
            "created_at",
        ]
        read_only_fields = fields

    def get_worker_name(self, obj):
        return str(obj.worker)

    def get_can_reschedule(self, obj):
        return public_reschedule_allowed(obj)
