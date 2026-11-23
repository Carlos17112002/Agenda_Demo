from datetime import timedelta
from datetime import timezone as dt_timezone

from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import APIException, ValidationError

from apps.audit.services import record_event
from apps.customers.models import Customer
from apps.mobile.push import push_booking_event
from apps.notifications.models import Notification
from apps.notifications.services import queue_booking_notification
from apps.workforce.models import WorkerProfile

from .availability import (
    active_overlaps, branch_timezone, validate_search_date, validate_target, worker_slots,
)
from .models import Booking


class BookingConflict(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "El horario seleccionado ya no está disponible."
    default_code = "booking_conflict"


class InvalidBookingState(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "La reserva no permite esta acción en su estado actual."
    default_code = "invalid_booking_state"


def _aware(branch, value):
    if timezone.is_naive(value):
        return timezone.make_aware(value, branch_timezone(branch))
    return value


def _local_day(branch, value):
    return value.astimezone(branch_timezone(branch)).date()


def _matches_slot(company, branch, service, worker, start_at, exclude_pk=None):
    day = _local_day(branch, start_at)
    target = start_at.astimezone(dt_timezone.utc)
    slots = worker_slots(company=company, branch=branch, service=service, worker=worker,
                         day=day, exclude_pk=exclude_pk)
    return any(slot["start_at"].astimezone(dt_timezone.utc) == target for slot in slots)


def _require_future_start(branch, start_at):
    if start_at <= timezone.now():
        raise ValidationError({"start_at": "La reserva debe ser futura."})
    validate_search_date(branch, _local_day(branch, start_at))


def create_booking(*, company, branch, service, worker, customer, start_at,
                   source=Booking.Source.STAFF, actor=None, notes=""):
    validate_target(company, branch, service, worker)
    if customer.company_id != company.id or not customer.active:
        raise ValidationError({"customer": "El cliente no pertenece a la empresa o está inactivo."})
    start_at = _aware(branch, start_at)
    _require_future_start(branch, start_at)

    duration = service.duration_minutes
    end_at = start_at + timedelta(minutes=duration)
    block_start = start_at - timedelta(minutes=service.buffer_before_minutes)
    block_end = end_at + timedelta(minutes=service.buffer_after_minutes)

    with transaction.atomic():
        # Serializes bookings per worker; PostgreSQL enforces the lock, SQLite is single-writer.
        worker = WorkerProfile.objects.select_for_update().get(pk=worker.pk)
        if not _matches_slot(company, branch, service, worker, start_at):
            raise BookingConflict()
        if active_overlaps(company, worker, block_start, block_end):
            raise BookingConflict()
        booking = Booking.objects.create(
            company=company, branch=branch, customer=customer, service=service, worker=worker,
            start_at=start_at, end_at=end_at, block_start=block_start, block_end=block_end,
            status=Booking.Status.SCHEDULED, source=source, notes=notes or "",
            service_name=service.name, duration_minutes=duration, price=service.price,
            buffer_before_minutes=service.buffer_before_minutes,
            buffer_after_minutes=service.buffer_after_minutes,
            created_by=actor if getattr(actor, "is_authenticated", False) else None,
        )
        record_event(company=company, actor=actor, action="booking.created", instance=booking,
                     metadata={"source": source, "start_at": start_at.isoformat(),
                               "worker_id": str(worker.id)})
        queue_booking_notification(booking, Notification.Kind.BOOKING_CREATED)
        push_booking_event(booking, Notification.Kind.BOOKING_CREATED)
    return booking


def reschedule_booking(*, booking, start_at, worker=None, actor=None, reason=""):
    if booking.status not in Booking.ACTIVE_STATUSES:
        raise InvalidBookingState("Solo se pueden reprogramar reservas agendadas o confirmadas.")
    worker = worker or booking.worker
    validate_target(booking.company, booking.branch, booking.service, worker)
    start_at = _aware(booking.branch, start_at)
    _require_future_start(booking.branch, start_at)

    with transaction.atomic():
        current = (Booking.objects.select_for_update()
                   .select_related("company", "branch", "service", "customer", "worker")
                   .get(pk=booking.pk))
        if current.status not in Booking.ACTIVE_STATUSES:
            raise InvalidBookingState("Solo se pueden reprogramar reservas agendadas o confirmadas.")
        if current.start_at == start_at and current.worker_id == worker.id:
            return current
        worker = WorkerProfile.objects.select_for_update().get(pk=worker.pk)
        if not _matches_slot(current.company, current.branch, current.service, worker,
                             start_at, exclude_pk=current.pk):
            raise BookingConflict()

        end_at = start_at + timedelta(minutes=current.duration_minutes)
        block_start = start_at - timedelta(minutes=current.buffer_before_minutes)
        block_end = end_at + timedelta(minutes=current.buffer_after_minutes)
        if active_overlaps(current.company, worker, block_start, block_end, exclude_pk=current.pk):
            raise BookingConflict()

        previous = {"start_at": current.start_at.isoformat(), "worker_id": str(current.worker_id)}
        current.worker = worker
        current.start_at = start_at
        current.end_at = end_at
        current.block_start = block_start
        current.block_end = block_end
        current.save(update_fields=["worker", "start_at", "end_at", "block_start", "block_end", "updated_at"])
        record_event(company=current.company, actor=actor, action="booking.rescheduled", instance=current,
                     metadata={"previous": previous, "start_at": start_at.isoformat(),
                               "worker_id": str(worker.id), "reason": reason})
        queue_booking_notification(current, Notification.Kind.BOOKING_RESCHEDULED)
        push_booking_event(current, Notification.Kind.BOOKING_RESCHEDULED)
    return current


TRANSITIONS = {
    "confirm": (Booking.Status.CONFIRMED, {Booking.Status.SCHEDULED},
                Notification.Kind.BOOKING_CONFIRMED),
    "cancel": (Booking.Status.CANCELED, {Booking.Status.SCHEDULED, Booking.Status.CONFIRMED},
               Notification.Kind.BOOKING_CANCELED),
    "complete": (Booking.Status.COMPLETED, {Booking.Status.SCHEDULED, Booking.Status.CONFIRMED}, None),
    "no_show": (Booking.Status.NO_SHOW, {Booking.Status.SCHEDULED, Booking.Status.CONFIRMED}, None),
}


def transition_booking(*, booking, action, actor=None, reason=""):
    target, allowed, notification_kind = TRANSITIONS[action]
    with transaction.atomic():
        current = (Booking.objects.select_for_update()
                   .select_related("company", "branch", "service", "customer", "worker")
                   .get(pk=booking.pk))
        if current.status == target:
            return current
        if current.status not in allowed:
            raise InvalidBookingState(
                f"No se puede ejecutar '{action}' sobre una reserva en estado {current.get_status_display().lower()}."
            )
        current.status = target
        fields = ["status", "updated_at"]
        if target == Booking.Status.CANCELED:
            current.canceled_at = timezone.now()
            current.canceled_reason = (reason or "").strip()[:240]
            fields += ["canceled_at", "canceled_reason"]
        current.save(update_fields=fields)
        record_event(company=current.company, actor=actor, action=f"booking.{action}", instance=current,
                     metadata={"reason": reason})
        if notification_kind:
            queue_booking_notification(current, notification_kind)
            push_booking_event(current, notification_kind)
    return current


def resolve_public_customer(*, company, first_name, last_name="", email="", phone=""):
    normalized = email.strip()
    customer = (Customer.objects.filter(company=company, email__iexact=normalized)
                .order_by("created_at").first())
    if customer:
        if not customer.active:
            raise ValidationError({"email": "El cliente está inactivo; contacta a la empresa."})
        return customer
    return Customer.objects.create(
        company=company, first_name=first_name.strip(), last_name=last_name.strip(),
        email=normalized, phone=phone.strip(),
    )
