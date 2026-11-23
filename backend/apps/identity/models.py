import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    is_saas_admin = models.BooleanField(default=False)
    must_change_password = models.BooleanField(default=False)
    jwt_valid_after = models.DateTimeField(null=True, blank=True)
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    def save(self, *args, **kwargs):
        was_active = None
        if self.pk:
            was_active = type(self).objects.filter(pk=self.pk).values_list("is_active", flat=True).first()
        super().save(*args, **kwargs)
        if was_active is True and not self.is_active:
            from .authentication import revoke_user_tokens
            revoke_user_tokens(self)

class Membership(models.Model):
    class Role(models.TextChoices):
        OWNER = "owner", "Propietario"
        ADMIN = "admin", "Administrador"
        MANAGER = "manager", "Supervisor"
        RECEPTION = "reception", "Recepción"
        WORKER = "worker", "Trabajador"
        INVENTORY = "inventory", "Inventario"
        ACCOUNTING = "accounting", "Contabilidad"
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey("tenancy.Company", on_delete=models.PROTECT, related_name="memberships")
    user = models.ForeignKey("identity.User", on_delete=models.PROTECT, related_name="memberships")
    role = models.CharField(max_length=24, choices=Role.choices, default=Role.WORKER)
    default_branch = models.ForeignKey(
        "tenancy.Branch",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="default_for_memberships",
    )
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["company", "user"], name="unique_company_membership")]

    def __str__(self):
        return f"{self.user_id} @ {self.company_id} ({self.role})"

class PermissionGrant(models.Model):
    """Extensible permission catalog and per-membership allow/deny override."""
    class Effect(models.TextChoices):
        ALLOW = "allow", "Permitir"
        DENY = "deny", "Denegar"
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    membership = models.ForeignKey(Membership, on_delete=models.CASCADE, related_name="permission_grants")
    permission = models.CharField(max_length=100)
    effect = models.CharField(max_length=8, choices=Effect.choices, default=Effect.ALLOW)
    branch = models.ForeignKey("tenancy.Branch", null=True, blank=True, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ["created_at"]
        constraints = [models.UniqueConstraint(fields=["membership", "permission", "branch"], name="unique_membership_permission_branch")]
        indexes = [models.Index(fields=["membership", "permission", "effect"])]
