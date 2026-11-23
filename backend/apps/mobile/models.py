import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.tenancy.models import Company


class DeviceInstallation(models.Model):
    class Platform(models.TextChoices):
        ANDROID = "android", "Android"
        IOS = "ios", "iOS"
        WEB = "web", "Web"
        OTHER = "other", "Otro"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name="device_installations",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="device_installations",
    )
    installation_id = models.CharField(max_length=128)
    platform = models.CharField(
        max_length=12, choices=Platform.choices, default=Platform.OTHER,
    )
    push_token = models.CharField(max_length=512, blank=True)
    app_version = models.CharField(max_length=32, blank=True)
    locale = models.CharField(max_length=16, blank=True)
    active = models.BooleanField(default=True)
    last_seen_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-last_seen_at"]
        indexes = [
            models.Index(fields=["company", "user", "active"]),
            models.Index(fields=["company", "push_token"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "user", "installation_id"],
                name="unique_installation_per_company_user",
            ),
        ]

    def __str__(self):
        return f"{self.user_id} {self.platform} {self.installation_id}"


class PushMessage(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pendiente"
        SENT = "sent", "Enviada"
        FAILED = "failed", "Fallida"
        SKIPPED = "skipped", "Omitida"

    class Kind(models.TextChoices):
        BOOKING_CREATED = "booking_created", "Reserva creada"
        BOOKING_CONFIRMED = "booking_confirmed", "Reserva confirmada"
        BOOKING_RESCHEDULED = "booking_rescheduled", "Reserva reprogramada"
        BOOKING_CANCELED = "booking_canceled", "Reserva cancelada"
        LOW_STOCK = "low_stock", "Stock bajo"
        SYSTEM = "system", "Sistema"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name="push_messages",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="push_messages",
    )
    kind = models.CharField(max_length=32, choices=Kind.choices, default=Kind.SYSTEM)
    title = models.CharField(max_length=160)
    body = models.TextField(blank=True)
    data = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.PENDING,
    )
    provider = models.CharField(max_length=24, blank=True)
    error = models.CharField(max_length=500, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["company", "user", "read_at"]),
            models.Index(fields=["company", "status"]),
        ]

    def __str__(self):
        return f"{self.title} → {self.user_id}"


class MobileOperation(models.Model):
    class Status(models.TextChoices):
        APPLIED = "applied", "Aplicada"
        CONFLICT = "conflict", "Conflicto"
        REJECTED = "rejected", "Rechazada"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name="mobile_operations",
    )
    client_id = models.UUIDField()
    operation = models.CharField(max_length=48)
    status = models.CharField(max_length=12, choices=Status.choices)
    request = models.JSONField(default=dict, blank=True)
    response = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="mobile_operations",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["company", "created_at"])]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "client_id"],
                name="unique_mobile_operation_per_company",
            ),
        ]

    def __str__(self):
        return f"{self.operation} {self.client_id} ({self.status})"
