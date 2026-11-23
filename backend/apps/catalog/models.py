import uuid

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.tenancy.models import Branch, TenantScopedModel


class Service(TenantScopedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    duration_minutes = models.PositiveSmallIntegerField(default=30, validators=[MinValueValidator(5), MaxValueValidator(480)])
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                validators=[MinValueValidator(0)])
    buffer_before_minutes = models.PositiveSmallIntegerField(default=0, validators=[MaxValueValidator(120)])
    buffer_after_minutes = models.PositiveSmallIntegerField(default=0, validators=[MaxValueValidator(120)])
    # Empty branch list means the service is available at every branch.
    branches = models.ManyToManyField(Branch, blank=True, related_name="services")
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["company", "active"])]
        constraints = [
            models.UniqueConstraint(fields=["company", "name"], name="unique_service_name_per_company"),
        ]

    def __str__(self):
        return self.name
