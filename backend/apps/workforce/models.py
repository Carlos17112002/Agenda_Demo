import uuid

from django.core.validators import RegexValidator
from django.db import models

from apps.tenancy.models import Branch, TenantScopedModel

COLOR_VALIDATOR = RegexValidator(r"^#[0-9A-Fa-f]{6}$", "Usa un color hexadecimal como #E50914.")


class WorkerProfile(TenantScopedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    membership = models.OneToOneField(
        "identity.Membership", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="worker_profile",
    )
    first_name = models.CharField(max_length=120)
    last_name = models.CharField(max_length=120, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=32, blank=True)
    job_title = models.CharField(max_length=120, blank=True)
    color = models.CharField(max_length=7, default="#E50914", validators=[COLOR_VALIDATOR])
    branches = models.ManyToManyField(Branch, blank=True, related_name="workers")
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["last_name", "first_name"]
        indexes = [models.Index(fields=["company", "active"])]

    def __str__(self):
        return f"{self.first_name} {self.last_name}".strip()


class WorkingHours(TenantScopedModel):
    class Weekday(models.IntegerChoices):
        MONDAY = 0, "Lunes"
        TUESDAY = 1, "Martes"
        WEDNESDAY = 2, "Miércoles"
        THURSDAY = 3, "Jueves"
        FRIDAY = 4, "Viernes"
        SATURDAY = 5, "Sábado"
        SUNDAY = 6, "Domingo"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    worker = models.ForeignKey(WorkerProfile, on_delete=models.CASCADE, related_name="working_hours")
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name="working_hours")
    weekday = models.PositiveSmallIntegerField(choices=Weekday.choices)
    start_time = models.TimeField()
    end_time = models.TimeField()

    class Meta:
        ordering = ["worker", "weekday", "start_time"]
        indexes = [models.Index(fields=["company", "worker", "branch", "weekday"])]
        constraints = [
            models.UniqueConstraint(fields=["worker", "branch", "weekday", "start_time"],
                                    name="unique_shift_start_per_worker_branch"),
        ]

    def __str__(self):
        return f"{self.worker} {self.get_weekday_display()} {self.start_time}-{self.end_time}"


class TimeOff(TenantScopedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    worker = models.ForeignKey(WorkerProfile, on_delete=models.CASCADE, related_name="time_off")
    branch = models.ForeignKey(Branch, null=True, blank=True, on_delete=models.CASCADE, related_name="time_off")
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    reason = models.CharField(max_length=240, blank=True)

    class Meta:
        ordering = ["-starts_at"]
        indexes = [models.Index(fields=["company", "worker", "starts_at"])]

    def __str__(self):
        return f"{self.worker} {self.starts_at:%Y-%m-%d %H:%M}"


class Break(TenantScopedModel):
    """Recurring daily pause excluded from booking availability."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    worker = models.ForeignKey(WorkerProfile, on_delete=models.CASCADE, related_name="breaks")
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name="breaks")
    weekday = models.PositiveSmallIntegerField(choices=WorkingHours.Weekday.choices)
    start_time = models.TimeField()
    end_time = models.TimeField()
    label = models.CharField(max_length=120, blank=True)

    class Meta:
        ordering = ["worker", "weekday", "start_time"]
        indexes = [models.Index(fields=["company", "worker", "branch", "weekday"])]
        constraints = [
            models.UniqueConstraint(fields=["worker", "branch", "weekday", "start_time"],
                                    name="unique_break_start_per_worker_branch"),
        ]

    def __str__(self):
        return f"{self.worker} pausa {self.get_weekday_display()} {self.start_time}-{self.end_time}"


class BlockedSlot(TenantScopedModel):
    """One-off block of a worker's agenda (meeting, personal errand, maintenance)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    worker = models.ForeignKey(WorkerProfile, on_delete=models.CASCADE, related_name="blocked_slots")
    branch = models.ForeignKey(Branch, null=True, blank=True, on_delete=models.CASCADE, related_name="blocked_slots")
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    reason = models.CharField(max_length=240, blank=True)

    class Meta:
        ordering = ["-starts_at"]
        indexes = [models.Index(fields=["company", "worker", "starts_at"])]

    def __str__(self):
        return f"{self.worker} bloqueo {self.starts_at:%Y-%m-%d %H:%M}"
