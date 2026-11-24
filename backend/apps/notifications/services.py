from datetime import timedelta
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from .models import Notification


SUBJECTS = {
    Notification.Kind.BOOKING_CREATED: "Reserva recibida",
    Notification.Kind.BOOKING_CONFIRMED: "Reserva confirmada",
    Notification.Kind.BOOKING_RESCHEDULED: "Reserva reprogramada",
    Notification.Kind.BOOKING_CANCELED: "Reserva cancelada",
    Notification.Kind.BOOKING_REMINDER: "Recordatorio de tu reserva",
}

REMINDER_LEAD = timedelta(hours=24)
REMINDER_WINDOW = timedelta(hours=1)


def booking_public_links(booking):
    """Cancel and reschedule links served by the public booking page."""
    page = reverse("public-booking-page-reservation", args=[booking.company.slug, booking.public_code])
    base = settings.PUBLIC_BASE_URL.rstrip("/")
    return f"{base}{page}", f"{base}{page}?reagendar=1"


def _local_range(booking):
    tz = ZoneInfo(booking.branch.timezone or settings.TIME_ZONE)
    start = booking.start_at.astimezone(tz)
    end = booking.end_at.astimezone(tz)
    day = start.strftime("%d-%m-%Y")
    return f"{day} de {start:%H:%M} a {end:%H:%M} ({booking.branch.timezone})"


def _compose(booking, kind):
    subject = f"{SUBJECTS[kind]} · {booking.service_name} · {booking.company.name}"[:200]
    if kind == Notification.Kind.BOOKING_REMINDER:
        intro = f"Te recordamos tu reserva {booking.public_code} en {booking.company.name}."
    else:
        intro = f"Tu reserva {booking.public_code} en {booking.company.name} está {SUBJECTS[kind].lower()}."
    lines = [
        f"Hola {booking.customer.first_name},",
        "",
        intro,
        "",
        f"Servicio: {booking.service_name}",
        f"Profesional: {booking.worker}",
        f"Sucursal: {booking.branch.name}" + (f" — {booking.branch.address}" if booking.branch.address else ""),
        f"Fecha: {_local_range(booking)}",
        f"Duración: {booking.duration_minutes} minutos",
    ]
    if kind == Notification.Kind.BOOKING_CANCELED and booking.canceled_reason:
        lines.append(f"Motivo: {booking.canceled_reason}")
    lines.append("")
    if kind == Notification.Kind.BOOKING_REMINDER:
        cancel_url, reschedule_url = booking_public_links(booking)
        lines += ["¿No puedes asistir? Cancela o reagenda aquí:",
                  f"Cancelar: {cancel_url}", f"Reagendar: {reschedule_url}"]
    else:
        lines.append("Si necesitas cambiar tu reserva, contacta a la sucursal.")
    lines += ["", f"Código de reserva: {booking.public_code}"]
    return subject, "\n".join(lines)


def deliver_notification(notification_id):
    notification = Notification.objects.filter(pk=notification_id).first()
    if notification is None or notification.status != Notification.Status.PENDING:
        return
    try:
        send_mail(notification.subject, notification.body, settings.DEFAULT_FROM_EMAIL,
                  [notification.recipient_email], fail_silently=False)
    except Exception as exc:  # delivered later by console/file backend in development
        notification.status = Notification.Status.FAILED
        notification.error = str(exc)[:500]
        notification.save(update_fields=["status", "error", "updated_at"])
        return
    notification.status = Notification.Status.SENT
    notification.sent_at = timezone.now()
    notification.save(update_fields=["status", "sent_at", "updated_at"])


def queue_booking_notification(booking, kind):
    """Persist an email record and send it only after the surrounding transaction commits."""
    recipient = (booking.customer.email or "").strip()
    if not recipient:
        return None
    subject, body = _compose(booking, kind)
    notification = Notification.objects.create(
        company=booking.company, booking=booking, kind=kind,
        recipient_email=recipient, subject=subject, body=body,
    )
    transaction.on_commit(lambda: deliver_notification(notification.pk))
    return notification


def send_due_reminders(now=None):
    """Queue 24h reminders for active bookings starting within the next hour-ish window.

    Meant to run hourly: bookings are selected when they enter the 24-25 hour
    window, pending/sent reminders are skipped so each booking is reminded once,
    and failed deliveries are retried by the following run.
    """
    from apps.bookings.models import Booking

    now = now or timezone.now()
    window_start = now + REMINDER_LEAD
    window_end = window_start + REMINDER_WINDOW
    candidates = (Booking.objects.filter(
        status__in=Booking.ACTIVE_STATUSES, start_at__gte=window_start, start_at__lt=window_end,
    ).exclude(customer__email="").values_list("pk", flat=True))

    queued = skipped = 0
    for pk in list(candidates):
        with transaction.atomic():
            booking = (Booking.objects.select_for_update()
                       .select_related("company", "branch", "customer", "worker", "service")
                       .get(pk=pk))
            already = Notification.objects.filter(
                booking=booking, kind=Notification.Kind.BOOKING_REMINDER,
                status__in=[Notification.Status.PENDING, Notification.Status.SENT],
            ).exists()
            if already or queue_booking_notification(booking, Notification.Kind.BOOKING_REMINDER) is None:
                skipped += 1
            else:
                queued += 1
    return {"queued": queued, "skipped": skipped}
