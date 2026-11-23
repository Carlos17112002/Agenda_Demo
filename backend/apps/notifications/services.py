from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from .models import Notification


SUBJECTS = {
    Notification.Kind.BOOKING_CREATED: "Reserva recibida",
    Notification.Kind.BOOKING_CONFIRMED: "Reserva confirmada",
    Notification.Kind.BOOKING_RESCHEDULED: "Reserva reprogramada",
    Notification.Kind.BOOKING_CANCELED: "Reserva cancelada",
}


def _local_range(booking):
    tz = ZoneInfo(booking.branch.timezone or settings.TIME_ZONE)
    start = booking.start_at.astimezone(tz)
    end = booking.end_at.astimezone(tz)
    day = start.strftime("%d-%m-%Y")
    return f"{day} de {start:%H:%M} a {end:%H:%M} ({booking.branch.timezone})"


def _compose(booking, kind):
    subject = f"{SUBJECTS[kind]} · {booking.service_name} · {booking.company.name}"[:200]
    lines = [
        f"Hola {booking.customer.first_name},",
        "",
        f"Tu reserva {booking.public_code} en {booking.company.name} está {SUBJECTS[kind].lower()}.",
        "",
        f"Servicio: {booking.service_name}",
        f"Profesional: {booking.worker}",
        f"Sucursal: {booking.branch.name}" + (f" — {booking.branch.address}" if booking.branch.address else ""),
        f"Fecha: {_local_range(booking)}",
        f"Duración: {booking.duration_minutes} minutos",
    ]
    if kind == Notification.Kind.BOOKING_CANCELED and booking.canceled_reason:
        lines.append(f"Motivo: {booking.canceled_reason}")
    lines += ["", "Si necesitas cambiar tu reserva, contacta a la sucursal.", "",
              f"Código de reserva: {booking.public_code}"]
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
