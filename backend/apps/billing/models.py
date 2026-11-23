import calendar
import math
import uuid
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.tenancy.models import Company


class Plan(models.Model):
    class BillingPeriod(models.TextChoices):
        MONTHLY = "monthly", "Mensual"
        YEARLY = "yearly", "Anual"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.SlugField(max_length=64, unique=True)
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    price = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0"))],
    )
    currency = models.CharField(max_length=3, default="CLP")
    billing_period = models.CharField(
        max_length=8, choices=BillingPeriod.choices, default=BillingPeriod.MONTHLY,
    )
    trial_days = models.PositiveIntegerField(default=0)
    active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "price", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["is_default"], condition=Q(is_default=True),
                name="unique_default_plan",
            ),
        ]

    def __str__(self):
        return self.name


def add_billing_period(start, billing_period):
    months = 12 if billing_period == Plan.BillingPeriod.YEARLY else 1
    year = start.year + (start.month - 1 + months) // 12
    month = (start.month - 1 + months) % 12 + 1
    day = min(start.day, calendar.monthrange(year, month)[1])
    return start.replace(year=year, month=month, day=day)


class PlanFeature(models.Model):
    class Code(models.TextChoices):
        BOOKINGS = "bookings", "Agenda y reservas"
        CUSTOMERS = "customers", "Clientes"
        CATALOG = "catalog", "Catálogo de servicios"
        WORKFORCE = "workforce", "Trabajadores y horarios"
        INVENTORY = "inventory", "Inventario y compras"
        SALES = "sales", "Ventas, caja y gastos"
        REPORTS = "reports", "Informes"
        BRANCHES = "branches", "Límite de sucursales"
        WORKERS = "workers", "Límite de trabajadores"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    plan = models.ForeignKey(Plan, on_delete=models.CASCADE, related_name="features")
    code = models.CharField(max_length=32, choices=Code.choices)
    enabled = models.BooleanField(default=True)
    limit_value = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Máximo permitido cuando el código representa un límite (branches/workers).",
    )

    class Meta:
        ordering = ["code"]
        constraints = [
            models.UniqueConstraint(fields=["plan", "code"], name="unique_plan_feature"),
        ]

    def __str__(self):
        return f"{self.plan_id} {self.code}"


class Subscription(models.Model):
    class Status(models.TextChoices):
        TRIALING = "trialing", "En prueba"
        ACTIVE = "active", "Activa"
        PAST_DUE = "past_due", "Pago pendiente"
        EXPIRED = "expired", "Vencida"
        CANCELED = "canceled", "Cancelada"

    GRACE_DAYS = 7

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="subscriptions")
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name="subscriptions")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.TRIALING)
    started_at = models.DateTimeField(default=timezone.now)
    trial_ends_at = models.DateTimeField(null=True, blank=True)
    current_period_start = models.DateTimeField(null=True, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True)
    cancel_at_period_end = models.BooleanField(default=False)
    canceled_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-started_at"]
        indexes = [models.Index(fields=["company", "ended_at"])]
        constraints = [
            models.UniqueConstraint(
                fields=["company"], condition=Q(ended_at__isnull=True),
                name="unique_open_subscription_per_company",
            ),
        ]

    def __str__(self):
        return f"{self.company_id} {self.plan_id} ({self.status})"

    def effective_status(self, now=None):
        now = now or timezone.now()
        if self.ended_at:
            return self.Status.EXPIRED if self.status == self.Status.EXPIRED else self.Status.CANCELED
        if self.status == self.Status.TRIALING:
            if self.trial_ends_at and self.trial_ends_at <= now:
                return self.Status.CANCELED if self.cancel_at_period_end else self.Status.EXPIRED
            return self.Status.TRIALING
        if self.status in {self.Status.ACTIVE, self.Status.PAST_DUE}:
            if self.current_period_end and self.current_period_end <= now:
                if self.cancel_at_period_end:
                    return self.Status.CANCELED
                if now <= self.current_period_end + timedelta(days=self.GRACE_DAYS):
                    return self.Status.PAST_DUE
                return self.Status.EXPIRED
            if self.status == self.Status.PAST_DUE:
                return self.Status.PAST_DUE
            return self.Status.ACTIVE
        return self.status

    def is_usable(self, now=None):
        return self.effective_status(now) in {
            self.Status.TRIALING, self.Status.ACTIVE, self.Status.PAST_DUE,
        }

    def days_remaining(self, now=None):
        now = now or timezone.now()
        end = self.trial_ends_at if self.effective_status(now) == self.Status.TRIALING else self.current_period_end
        if end is None:
            return None
        return max(0, math.ceil((end - now).total_seconds() / 86400))

    def feature_row(self, code):
        return next((row for row in self.plan.features.all() if row.code == code), None)

    def has_feature(self, code):
        row = self.feature_row(code)
        return bool(row and row.enabled)

    def feature_limit(self, code):
        row = self.feature_row(code)
        if row and row.enabled and row.limit_value is not None:
            return row.limit_value
        return None


class Payment(models.Model):
    class Method(models.TextChoices):
        CASH = "cash", "Efectivo"
        TRANSFER = "transfer", "Transferencia"
        CARD = "card", "Tarjeta"
        OTHER = "other", "Otro"

    class Status(models.TextChoices):
        COMPLETED = "completed", "Completado"
        REFUNDED = "refunded", "Reembolsado"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="billing_payments")
    subscription = models.ForeignKey(Subscription, on_delete=models.PROTECT, related_name="payments")
    amount = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))],
    )
    currency = models.CharField(max_length=3, default="CLP")
    method = models.CharField(max_length=12, choices=Method.choices, default=Method.TRANSFER)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.COMPLETED)
    reference = models.CharField(max_length=120, blank=True)
    paid_at = models.DateTimeField(default=timezone.now)
    period_start = models.DateTimeField(null=True, blank=True)
    period_end = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="billing_payments",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-paid_at"]
        indexes = [models.Index(fields=["company", "paid_at"])]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "reference"], condition=~Q(reference=""),
                name="unique_billing_payment_reference_per_company",
            ),
        ]

    def __str__(self):
        return f"{self.company_id} {self.amount} {self.currency}"


class Invoice(models.Model):
    class Status(models.TextChoices):
        ISSUED = "issued", "Emitida"
        PAID = "paid", "Pagada"
        VOID = "void", "Anulada"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="billing_invoices")
    subscription = models.ForeignKey(Subscription, on_delete=models.PROTECT, related_name="invoices")
    payment = models.ForeignKey(
        Payment, null=True, blank=True, on_delete=models.SET_NULL, related_name="invoices",
    )
    sequence = models.PositiveIntegerField()
    number = models.CharField(max_length=32)
    description = models.CharField(max_length=240)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    tax = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    total = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default="CLP")
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.ISSUED)
    period_start = models.DateTimeField(null=True, blank=True)
    period_end = models.DateTimeField(null=True, blank=True)
    issued_at = models.DateTimeField(default=timezone.now)
    due_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-issued_at"]
        indexes = [models.Index(fields=["company", "issued_at"])]
        constraints = [
            models.UniqueConstraint(fields=["company", "sequence"], name="unique_invoice_sequence_per_company"),
            models.UniqueConstraint(fields=["company", "number"], name="unique_invoice_number_per_company"),
        ]

    def __str__(self):
        return f"{self.number} ({self.company_id})"
