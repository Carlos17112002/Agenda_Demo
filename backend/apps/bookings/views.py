from datetime import datetime, time, timedelta
from datetime import timezone as dt_timezone
from zoneinfo import ZoneInfo

from django.conf import settings
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from apps.identity.models import Membership
from apps.tenancy.api import TenantModelViewSet
from apps.tenancy.models import Branch

from .availability import branch_timezone, worker_slots
from .models import Booking
from .serializers import (
    AvailabilityQuerySerializer, BookingCreateSerializer, BookingNotesSerializer,
    BookingSerializer, RescheduleSerializer, TransitionSerializer,
)
from .services import create_booking, reschedule_booking, transition_booking


def _parse_day(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def _day_bounds(day, tz):
    return (datetime.combine(day, time.min, tzinfo=tz),
            datetime.combine(day + timedelta(days=1), time.min, tzinfo=tz))


class BookingViewSet(TenantModelViewSet):
    """Staff calendar, conflict-safe booking commands and per-worker availability."""

    serializer_class = BookingSerializer
    audit_name = "booking"
    http_method_names = ["get", "post", "patch", "head", "options"]
    permission_map = {
        "list": "bookings.read", "retrieve": "bookings.read", "availability": "bookings.read",
        "create": "bookings.write", "partial_update": "bookings.write",
        "update": "bookings.write", "destroy": "bookings.write",
        "reschedule": "bookings.write", "confirm": "bookings.write",
        "cancel": "bookings.write", "complete": "bookings.write", "no_show": "bookings.write",
    }
    search_fields = ["customer__first_name", "customer__last_name", "customer__email",
                     "service_name", "public_code"]
    ordering_fields = ["start_at", "created_at", "status", "worker__last_name"]

    def _membership(self):
        tenant = getattr(self.request, "tenant", None)
        if tenant is None:
            from apps.tenancy.authentication import resolve_tenant
            tenant = resolve_tenant(self.request, self.request.user)
        if tenant is None:
            return None
        return self.request.user.memberships.filter(company=tenant, active=True).first()

    def _is_worker(self):
        membership = self._membership()
        return membership is not None and membership.role == Membership.Role.WORKER

    def get_required_tenant_permission(self):
        required = super().get_required_tenant_permission()
        if required and required.startswith("bookings.") and self._is_worker():
            return "bookings.own." + required.split(".", 1)[1]
        return required

    def get_serializer_class(self):
        if self.action == "create":
            return BookingCreateSerializer
        if self.action == "partial_update":
            return BookingNotesSerializer
        return BookingSerializer

    def queryset_for_tenant(self, tenant):
        queryset = (Booking.objects.filter(company=tenant)
                    .select_related("branch", "customer", "service", "worker"))
        membership = self._membership()
        if membership and membership.role == Membership.Role.WORKER:
            queryset = queryset.filter(worker__membership=membership)

        params = self.request.query_params
        branch_id = params.get("branch")
        if branch_id:
            queryset = queryset.filter(branch_id=branch_id)
        if params.get("worker"):
            queryset = queryset.filter(worker_id=params["worker"])
        if params.get("service"):
            queryset = queryset.filter(service_id=params["service"])
        if params.get("customer"):
            queryset = queryset.filter(customer_id=params["customer"])
        if params.get("status") in Booking.Status.values:
            queryset = queryset.filter(status=params["status"])

        branch = None
        if branch_id:
            branch = Branch.objects.filter(pk=branch_id, company=tenant).first()
        tz = branch_timezone(branch) if branch else ZoneInfo(settings.TIME_ZONE)
        exact_day = _parse_day(params.get("date"))
        if exact_day:
            start, end = _day_bounds(exact_day, tz)
            queryset = queryset.filter(start_at__gte=start, start_at__lt=end)
        date_from = _parse_day(params.get("date_from"))
        if date_from:
            queryset = queryset.filter(start_at__gte=_day_bounds(date_from, tz)[0])
        date_to = _parse_day(params.get("date_to"))
        if date_to:
            queryset = queryset.filter(start_at__lt=_day_bounds(date_to, tz)[1])
        return queryset

    def create(self, request, *args, **kwargs):
        serializer = BookingCreateSerializer(data=request.data, context=self.get_serializer_context())
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        membership = self._membership()
        if self._is_worker():
            if not data["worker"].membership_id or data["worker"].membership_id != membership.id:
                raise PermissionDenied("Solo puedes agendar reservas para tu propio perfil.")
        booking = create_booking(
            company=self.get_tenant(), branch=data["branch"], service=data["service"],
            worker=data["worker"], customer=data["customer"], start_at=data["start_at"],
            source=Booking.Source.STAFF, actor=request.user, notes=data.get("notes", ""),
        )
        return Response(BookingSerializer(booking).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = BookingNotesSerializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        self._audit("updated", instance)
        return Response(BookingSerializer(instance).data)

    @action(detail=False, methods=["get"])
    def availability(self, request):
        serializer = AvailabilityQuerySerializer(
            data=request.query_params, context={"request": request, "company": self.get_tenant()},
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        membership = self._membership()
        if membership and membership.role == Membership.Role.WORKER:
            if data["worker"].membership_id != membership.id:
                raise PermissionDenied("Solo puedes consultar tu propia disponibilidad.")
        slots = worker_slots(company=self.get_tenant(), branch=data["branch"],
                             service=data["service"], worker=data["worker"], day=data["date"])
        tz = branch_timezone(data["branch"])
        return Response({
            "date": data["date"].isoformat(),
            "timezone": data["branch"].timezone,
            "slots": [
                {
                    "start_at": slot["start_at"].astimezone(dt_timezone.utc).isoformat(),
                    "end_at": slot["end_at"].astimezone(dt_timezone.utc).isoformat(),
                    "label": slot["start_at"].astimezone(tz).strftime("%H:%M"),
                }
                for slot in slots
            ],
        })

    def _transition(self, request, action_name):
        booking = self.get_object()
        serializer = TransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        booking = transition_booking(booking=booking, action=action_name, actor=request.user,
                                     reason=serializer.validated_data.get("reason", ""))
        return Response(BookingSerializer(booking).data)

    @action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        return self._transition(request, "confirm")

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        return self._transition(request, "cancel")

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        return self._transition(request, "complete")

    @action(detail=True, methods=["post"], url_path="no-show")
    def no_show(self, request, pk=None):
        return self._transition(request, "no_show")

    @action(detail=True, methods=["post"])
    def reschedule(self, request, pk=None):
        booking = self.get_object()
        serializer = RescheduleSerializer(data=request.data, context=self.get_serializer_context())
        serializer.is_valid(raise_exception=True)
        worker = serializer.validated_data.get("worker")
        membership = self._membership()
        if membership and membership.role == Membership.Role.WORKER:
            target = worker or booking.worker
            if target.membership_id != membership.id:
                raise PermissionDenied("Solo puedes reprogramar reservas de tu propio perfil.")
        booking = reschedule_booking(
            booking=booking, start_at=serializer.validated_data["start_at"], worker=worker,
            actor=request.user, reason=serializer.validated_data.get("reason", ""),
        )
        return Response(BookingSerializer(booking).data)
