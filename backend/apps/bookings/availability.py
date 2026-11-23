from datetime import datetime, time, timedelta
from datetime import timezone as dt_timezone
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from apps.workforce.models import BlockedSlot, Break, TimeOff, WorkingHours

from .models import Booking

MAX_LOOKAHEAD_DAYS = 90


def branch_timezone(branch):
    return ZoneInfo(branch.timezone or settings.TIME_ZONE)


def local_day_window(branch, day):
    tz = branch_timezone(branch)
    start = datetime.combine(day, time.min, tzinfo=tz)
    end = datetime.combine(day + timedelta(days=1), time.min, tzinfo=tz)
    return start, end


def service_available_at_branch(service, branch):
    if not service.active or not branch.active:
        return False
    branches = service.branches.all()
    return not branches.exists() or branches.filter(pk=branch.pk).exists()


def worker_available_at_branch(worker, branch):
    return worker.active and worker.branches.filter(pk=branch.pk).exists()


def validate_target(company, branch, service, worker):
    """Validate that a branch/service/worker combination belongs to the tenant."""
    from rest_framework.exceptions import ValidationError

    if branch.company_id != company.id or not branch.active:
        raise ValidationError({"branch": "La sucursal no pertenece a la empresa o está inactiva."})
    if service.company_id != company.id or not service.active:
        raise ValidationError({"service": "El servicio no pertenece a la empresa o está inactivo."})
    if worker.company_id != company.id or not worker.active:
        raise ValidationError({"worker": "El trabajador no pertenece a la empresa o está inactivo."})
    if not service_available_at_branch(service, branch):
        raise ValidationError({"service": "El servicio no está disponible en esta sucursal."})
    if not worker_available_at_branch(worker, branch):
        raise ValidationError({"worker": "El trabajador no atiende en esta sucursal."})


def validate_search_date(branch, day):
    from rest_framework.exceptions import ValidationError

    today = timezone.localdate(timezone=branch_timezone(branch))
    if day < today:
        raise ValidationError({"date": "No se puede consultar una fecha pasada."})
    if day > today + timedelta(days=MAX_LOOKAHEAD_DAYS):
        raise ValidationError({"date": f"Consulta como máximo {MAX_LOOKAHEAD_DAYS} días hacia adelante."})


def active_overlaps(company, worker, block_start, block_end, exclude_pk=None):
    queryset = Booking.objects.filter(
        company=company, worker=worker, status__in=Booking.ACTIVE_STATUSES,
        block_start__lt=block_end, block_end__gt=block_start,
    )
    if exclude_pk:
        queryset = queryset.exclude(pk=exclude_pk)
    return queryset.exists()


def worker_slots(*, company, branch, service, worker, day, exclude_pk=None):
    """Return free service slots for one worker on a local calendar day."""
    if not service_available_at_branch(service, branch) or not worker_available_at_branch(worker, branch):
        return []

    tz = branch_timezone(branch)
    day_start, day_end = local_day_window(branch, day)
    shifts = WorkingHours.objects.filter(
        company=company, worker=worker, branch=branch, weekday=day.weekday(),
    ).order_by("start_time")
    bookings_query = Booking.objects.filter(
        company=company, worker=worker, status__in=Booking.ACTIVE_STATUSES,
        block_start__lt=day_end, block_end__gt=day_start,
    )
    if exclude_pk:
        bookings_query = bookings_query.exclude(pk=exclude_pk)
    bookings = list(bookings_query.only("block_start", "block_end"))
    absences = list(TimeOff.objects.filter(
        company=company, worker=worker, starts_at__lt=day_end, ends_at__gt=day_start,
    ).filter(Q(branch=branch) | Q(branch__isnull=True)).only("starts_at", "ends_at"))
    blocked = list(BlockedSlot.objects.filter(
        company=company, worker=worker, starts_at__lt=day_end, ends_at__gt=day_start,
    ).filter(Q(branch=branch) | Q(branch__isnull=True)).only("starts_at", "ends_at"))
    break_windows = [
        (datetime.combine(day, pause.start_time, tzinfo=tz),
         datetime.combine(day, pause.end_time, tzinfo=tz))
        for pause in Break.objects.filter(
            company=company, worker=worker, branch=branch, weekday=day.weekday(),
        ).only("start_time", "end_time")
    ]

    duration = timedelta(minutes=service.duration_minutes)
    before = timedelta(minutes=service.buffer_before_minutes)
    after = timedelta(minutes=service.buffer_after_minutes)
    step = timedelta(minutes=getattr(settings, "BOOKING_SLOT_STEP_MINUTES", 15))
    now = timezone.now()
    slots = {}

    for shift in shifts:
        shift_start = datetime.combine(day, shift.start_time, tzinfo=tz)
        shift_end = datetime.combine(day, shift.end_time, tzinfo=tz)
        cursor = shift_start
        while cursor < shift_end:
            end = cursor + duration
            block_start = cursor - before
            block_end = end + after
            if block_end > shift_end:
                break
            if block_start >= shift_start and cursor > now:
                busy = any(block_start < other.block_end and block_end > other.block_start for other in bookings)
                absent = any(block_start < off.ends_at and block_end > off.starts_at for off in absences)
                parked = any(block_start < item.ends_at and block_end > item.starts_at for item in blocked)
                paused = any(block_start < end_break and block_end > start_break
                             for start_break, end_break in break_windows)
                if not busy and not absent and not parked and not paused:
                    slots[cursor.astimezone(dt_timezone.utc)] = {"start_at": cursor, "end_at": end}
            cursor += step

    return [slots[key] for key in sorted(slots)]
