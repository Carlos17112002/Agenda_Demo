import secrets
import uuid

from django.db import models
from django.db.models import F, Q

from apps.tenancy.models import Branch, TenantScopedModel

PUBLIC_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def generate_public_code():
    return "".join(secrets.choice(PUBLIC_CODE_ALPHABET) for _ in range(10))


class Booking(TenantScopedModel):
    """Appointment with immutable service snapshots and reserved buffer blocks."""

    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "Agendada"
        CONFIRMED = "confirmed", "Confirmada"
        COMPLETED = "completed", "Completada"
        CANCELED = "canceled", "Cancelada"
        NO_SHOW = "no_show", "No asistió"

    class Source(models.TextChoices):
        STAFF = "staff", "Equipo"
        PUBLIC = "public", "Portal público"

    ACTIVE_STATUSES = (Status.SCHEDULED, Status.CONFIRMED)

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name="bookings")
    customer = models.ForeignKey("customers.Customer", on_delete=models.PROTECT, related_name="bookings")
    service = models.ForeignKey("catalog.Service", on_delete=models.PROTECT, related_name="bookings")
    worker = models.ForeignKey("workforce.WorkerProfile", on_delete=models.PROTECT, related_name="bookings")
    start_at = models.DateTimeField()
    end_at = models.DateTimeField()
    # Buffers reserve the worker's time without changing the customer-facing range.
    block_start = models.DateTimeField()
    block_end = models.DateTimeField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.SCHEDULED)
    source = models.CharField(max_length=12, choices=Source.choices, default=Source.STAFF)
    notes = models.TextField(blank=True)
    public_code = models.CharField(max_length=16, unique=True, default=generate_public_code, editable=False)
    canceled_at = models.DateTimeField(null=True, blank=True)
    canceled_reason = models.CharField(max_length=240, blank=True)
    created_by = models.ForeignKey(
        "identity.User", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="bookings_created",
    )

    service_name = models.CharField(max_length=160)
    duration_minutes = models.PositiveSmallIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    buffer_before_minutes = models.PositiveSmallIntegerField(default=0)
    buffer_after_minutes = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["start_at"]
        indexes = [
            models.Index(fields=["company", "branch", "start_at"]),
            models.Index(fields=["company", "worker", "start_at"]),
            models.Index(fields=["company", "customer", "start_at"]),
            models.Index(fields=["company", "status"]),
        ]
        constraints = [
            models.CheckConstraint(condition=Q(end_at__gt=F("start_at")), name="booking_end_after_start"),
            models.CheckConstraint(condition=Q(block_start__lte=F("start_at")), name="booking_block_starts_before_service"),
            models.CheckConstraint(condition=Q(block_end__gte=F("end_at")), name="booking_block_ends_after_service"),
        ]

    def __str__(self):
        return f"{self.public_code} {self.service_name} {self.start_at:%Y-%m-%d %H:%M}"
