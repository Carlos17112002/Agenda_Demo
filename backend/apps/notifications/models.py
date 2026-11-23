import uuid

from django.db import models

from apps.tenancy.models import TenantScopedModel


class Notification(TenantScopedModel):
    """Delivery record for transactional messages; sending happens after commit."""

    class Kind(models.TextChoices):
        BOOKING_CREATED = "booking_created", "Reserva recibida"
        BOOKING_CONFIRMED = "booking_confirmed", "Reserva confirmada"
        BOOKING_RESCHEDULED = "booking_rescheduled", "Reserva reprogramada"
        BOOKING_CANCELED = "booking_canceled", "Reserva cancelada"

    class Status(models.TextChoices):
        PENDING = "pending", "Pendiente"
        SENT = "sent", "Enviada"
        FAILED = "failed", "Fallida"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    booking = models.ForeignKey(
        "bookings.Booking", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="notifications",
    )
    kind = models.CharField(max_length=32, choices=Kind.choices)
    recipient_email = models.EmailField()
    subject = models.CharField(max_length=200)
    body = models.TextField()
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    error = models.TextField(blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["company", "status"]),
            models.Index(fields=["company", "kind"]),
        ]

    def __str__(self):
        return f"{self.kind} -> {self.recipient_email} ({self.status})"
