from datetime import timezone as dt_timezone

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from apps.catalog.models import Service
from apps.tenancy.branding import branding_payload
from apps.tenancy.models import Branch, Company
from apps.workforce.models import WorkerProfile

from .availability import branch_timezone, worker_slots
from .models import Booking
from .serializers import (
    AvailabilityQuerySerializer, PublicBookingCreateSerializer, PublicBookingSerializer,
    PublicRescheduleSerializer, TransitionSerializer,
)
from .services import (
    InvalidBookingState, create_booking, public_reschedule_allowed, resolve_public_customer,
    reschedule_booking, transition_booking,
)


class PublicRateThrottle(AnonRateThrottle):
    scope = "public"


class PublicBaseView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [PublicRateThrottle]


def public_company(slug):
    company = Company.objects.filter(
        slug__iexact=slug, status__in=[Company.Status.TRIAL, Company.Status.ACTIVE],
    ).first()
    if company is None:
        raise NotFound("Empresa no encontrada.")
    from apps.billing.gating import current_subscription
    from apps.billing.models import Subscription
    subscription = current_subscription(company)
    if subscription is None:
        if Subscription.objects.filter(company=company).exists():
            raise NotFound("Empresa no encontrada.")
    elif not subscription.is_usable() or not subscription.has_feature("bookings"):
        raise NotFound("Empresa no encontrada.")
    return company


def company_payload(company, request=None):
    branches = Branch.objects.filter(company=company, active=True).order_by("name")
    services = (Service.objects.filter(company=company, active=True)
                .prefetch_related("branches").order_by("name"))
    workers = (WorkerProfile.objects.filter(company=company, active=True, branches__isnull=False)
               .prefetch_related("branches").distinct().order_by("last_name", "first_name"))

    services_payload = []
    for service in services:
        branch_ids = [str(branch.id) for branch in service.branches.all()]
        services_payload.append({
            "id": str(service.id), "name": service.name, "description": service.description,
            "duration_minutes": service.duration_minutes, "price": str(service.price),
            "branch_ids": branch_ids, "all_branches": not branch_ids,
        })
    workers_payload = [
        {
            "id": str(worker.id), "display_name": str(worker), "color": worker.color,
            "branch_ids": [str(branch.id) for branch in worker.branches.all()],
        }
        for worker in workers
    ]
    return {
        "name": company.name,
        "slug": company.slug,
        "branding": branding_payload(company, request),
        "branches": [
            {"id": str(branch.id), "name": branch.name, "address": branch.address,
             "timezone": branch.timezone}
            for branch in branches
        ],
        "services": services_payload,
        "workers": workers_payload,
    }


def slots_payload(branch, day, slots):
    tz = branch_timezone(branch)
    return {
        "date": day.isoformat(),
        "timezone": branch.timezone,
        "slots": [
            {
                "start_at": slot["start_at"].astimezone(dt_timezone.utc).isoformat(),
                "end_at": slot["end_at"].astimezone(dt_timezone.utc).isoformat(),
                "label": slot["start_at"].astimezone(tz).strftime("%H:%M"),
            }
            for slot in slots
        ],
    }


class PublicCompanyView(PublicBaseView):
    def get(self, request, slug):
        return Response(company_payload(public_company(slug), request))


class PublicAvailabilityView(PublicBaseView):
    def get(self, request, slug):
        company = public_company(slug)
        serializer = AvailabilityQuerySerializer(data=request.query_params, context={"company": company})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        slots = worker_slots(company=company, branch=data["branch"], service=data["service"],
                             worker=data["worker"], day=data["date"], exclude_pk=data["exclude_pk"])
        return Response(slots_payload(data["branch"], data["date"], slots))


class PublicBookingCreateView(PublicBaseView):
    def post(self, request, slug):
        company = public_company(slug)
        serializer = PublicBookingCreateSerializer(data=request.data, context={"company": company})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        with transaction.atomic():
            customer = resolve_public_customer(
                company=company, first_name=data["first_name"], last_name=data.get("last_name", ""),
                email=data["email"], phone=data.get("phone", ""),
            )
            booking = create_booking(
                company=company, branch=data["branch"], service=data["service"],
                worker=data["worker"], customer=customer, start_at=data["start_at"],
                source=Booking.Source.PUBLIC, actor=None, notes=data.get("notes", ""),
            )
        return Response(PublicBookingSerializer(booking).data, status=status.HTTP_201_CREATED)


def find_public_booking(company, code):
    booking = (Booking.objects.filter(company=company, public_code__iexact=code)
               .select_related("branch", "customer", "service", "worker").first())
    if booking is None:
        raise NotFound("Reserva no encontrada.")
    return booking


class PublicBookingDetailView(PublicBaseView):
    def get(self, request, slug, code):
        company = public_company(slug)
        return Response(PublicBookingSerializer(find_public_booking(company, code)).data)


class PublicBookingCancelView(PublicBaseView):
    def post(self, request, slug, code):
        company = public_company(slug)
        booking = find_public_booking(company, code)
        serializer = TransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if booking.status not in Booking.ACTIVE_STATUSES:
            raise InvalidBookingState("La reserva ya no se puede cancelar.")
        if booking.start_at <= timezone.now():
            raise InvalidBookingState("La reserva ya comenzó y no se puede cancelar en línea.")
        booking = transition_booking(
            booking=booking, action="cancel", actor=None,
            reason=serializer.validated_data.get("reason", ""),
        )
        return Response(PublicBookingSerializer(booking).data)


class PublicBookingRescheduleView(PublicBaseView):
    def post(self, request, slug, code):
        company = public_company(slug)
        booking = find_public_booking(company, code)
        serializer = PublicRescheduleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if booking.status not in Booking.ACTIVE_STATUSES:
            raise InvalidBookingState("La reserva ya no se puede reprogramar.")
        if not public_reschedule_allowed(booking):
            cutoff = getattr(settings, "PUBLIC_RESCHEDULE_CUTOFF_HOURS", 2)
            raise InvalidBookingState(
                f"Faltan menos de {cutoff} horas para tu reserva; contacta a la sucursal para cambiarla."
            )
        booking = reschedule_booking(
            booking=booking, start_at=serializer.validated_data["start_at"],
            actor=None, reason="Reagendado por el cliente",
        )
        return Response(PublicBookingSerializer(booking).data)
