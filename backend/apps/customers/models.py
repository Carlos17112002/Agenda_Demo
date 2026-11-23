import uuid

from django.db import models

from apps.tenancy.models import TenantScopedModel


class Customer(TenantScopedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    first_name = models.CharField(max_length=120)
    last_name = models.CharField(max_length=120, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=32, blank=True)
    document_id = models.CharField(max_length=32, blank=True)
    notes = models.TextField(blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["last_name", "first_name"]
        indexes = [
            models.Index(fields=["company", "active"]),
            models.Index(fields=["company", "last_name"]),
        ]

    def __str__(self):
        return f"{self.first_name} {self.last_name}".strip()
