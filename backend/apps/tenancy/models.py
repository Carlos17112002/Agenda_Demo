import uuid
from django.conf import settings
from django.db import models

from .validators import validate_company_slug, validate_hex_color, validate_timezone

class Company(models.Model):
    class Status(models.TextChoices):
        TRIAL = "trial", "Prueba"
        ACTIVE = "active", "Activa"
        SUSPENDED = "suspended", "Suspendida"
        CLOSED = "closed", "Cerrada"
    class ThemeMode(models.TextChoices):
        LIGHT = "light", "Claro"
        DARK = "dark", "Oscuro"
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=180)
    slug = models.SlugField(max_length=100, unique=True, validators=[validate_company_slug])
    display_name = models.CharField(
        max_length=180, blank=True,
        help_text="Nombre comercial visible en la página de reservas y la app; si queda vacío se usa el nombre legal.",
    )
    logo = models.ImageField(upload_to="company-logos/", blank=True, null=True)
    primary_color = models.CharField(
        max_length=7, default="#E50914", validators=[validate_hex_color],
    )
    secondary_color = models.CharField(
        max_length=7, default="#8B0000", validators=[validate_hex_color],
    )
    theme_mode = models.CharField(
        max_length=8, choices=ThemeMode.choices, default=ThemeMode.LIGHT,
        help_text="Fondo claro u oscuro de la app y la página pública de reservas.",
    )
    legal_name = models.CharField(max_length=200, blank=True)
    tax_identifier = models.CharField(max_length=32, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.TRIAL)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

class TenantScopedModel(models.Model):
    """Base for business records; tenant ownership cannot be changed by API clients."""
    company = models.ForeignKey(Company, on_delete=models.PROTECT, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        abstract = True

class Branch(TenantScopedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=160)
    code = models.CharField(max_length=32)
    address = models.CharField(max_length=240, blank=True)
    timezone = models.CharField(
        max_length=64, default="America/Santiago", validators=[validate_timezone],
        help_text="Zona horaria IANA usada para calcular la agenda de esta sucursal.",
    )
    active = models.BooleanField(default=True)
    class Meta:
        ordering = ["name"]
        constraints = [models.UniqueConstraint(fields=["company", "code"], name="unique_branch_code_per_company")]

class TenantContext(models.Model):
    """Explicit, expiring user selection of an authorized tenant."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    class Meta:
        indexes = [models.Index(fields=["user", "expires_at"])]
