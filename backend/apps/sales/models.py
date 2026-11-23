import uuid
from decimal import ROUND_HALF_UP, Decimal

from django.db import models
from django.db.models import Q, Sum
from django.utils import timezone

from apps.tenancy.models import Branch, TenantScopedModel


def _reference(prefix):
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"


def default_sale_number():
    return _reference("VTA")


def default_cash_session_number():
    return _reference("CJ")


def default_expense_number():
    return _reference("GTO")


class CashSession(TenantScopedModel):
    """Shift-level cash drawer reconciled on close."""

    class Status(models.TextChoices):
        OPEN = "open", "Abierta"
        CLOSED = "closed", "Cerrada"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    number = models.CharField(max_length=32, default=default_cash_session_number)
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name="cash_sessions")
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.OPEN)
    opening_amount = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0"))
    closing_amount = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    expected_amount = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    difference = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    opened_at = models.DateTimeField(default=timezone.now)
    closed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    closing_notes = models.TextField(blank=True)
    opened_by = models.ForeignKey(
        "identity.User", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="cash_sessions_opened",
    )
    closed_by = models.ForeignKey(
        "identity.User", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="cash_sessions_closed",
    )

    class Meta:
        ordering = ["-opened_at"]
        indexes = [
            models.Index(fields=["company", "branch", "status", "opened_at"]),
            models.Index(fields=["company", "opened_at"]),
        ]
        constraints = [
            models.UniqueConstraint(fields=["company", "number"], name="unique_cash_session_number_per_company"),
            models.UniqueConstraint(
                fields=["company", "branch"], condition=Q(status="open"),
                name="unique_open_cash_session_per_branch",
            ),
            models.CheckConstraint(condition=Q(opening_amount__gte=0), name="cash_opening_not_negative"),
            models.CheckConstraint(
                condition=Q(closing_amount__isnull=True) | Q(closing_amount__gte=0),
                name="cash_closing_not_negative",
            ),
        ]

    def __str__(self):
        return f"{self.number} · {self.branch}"

    @property
    def cash_sales_total(self):
        total = self.payments.filter(
            method=PaymentRecord.Method.CASH, status=PaymentRecord.Status.COMPLETED,
        ).aggregate(total=Sum("amount"))["total"]
        return total or Decimal("0")

    @property
    def cash_expenses_total(self):
        total = self.expenses.filter(
            method=Expense.Method.CASH, status=Expense.Status.ACTIVE,
        ).aggregate(total=Sum("amount"))["total"]
        return total or Decimal("0")

    @property
    def expected_cash(self):
        if self.status == self.Status.CLOSED and self.expected_amount is not None:
            return self.expected_amount
        return self.opening_amount + self.cash_sales_total - self.cash_expenses_total


class Sale(TenantScopedModel):
    """Commercial document; completing it charges payments and consumes stock."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Borrador"
        COMPLETED = "completed", "Completada"
        CANCELED = "canceled", "Anulada"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    number = models.CharField(max_length=32, default=default_sale_number)
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name="sales")
    customer = models.ForeignKey(
        "customers.Customer", null=True, blank=True,
        on_delete=models.PROTECT, related_name="sales",
    )
    warehouse = models.ForeignKey(
        "inventory.Warehouse", null=True, blank=True,
        on_delete=models.PROTECT, related_name="sales",
    )
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    discount = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0"))
    notes = models.TextField(blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    canceled_at = models.DateTimeField(null=True, blank=True)
    canceled_reason = models.CharField(max_length=240, blank=True)
    created_by = models.ForeignKey(
        "identity.User", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="sales_created",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["company", "status", "created_at"]),
            models.Index(fields=["company", "branch", "completed_at"]),
            models.Index(fields=["company", "customer", "created_at"]),
        ]
        constraints = [
            models.UniqueConstraint(fields=["company", "number"], name="unique_sale_number_per_company"),
            models.CheckConstraint(condition=Q(discount__gte=0), name="sale_discount_not_negative"),
        ]

    def __str__(self):
        return f"{self.number} · {self.branch}"

    @property
    def subtotal(self):
        return sum((line.line_total for line in self.lines.all()), Decimal("0"))

    @property
    def total(self):
        return self.subtotal - self.discount

    @property
    def paid_total(self):
        return sum(
            (payment.amount for payment in self.payments.all()
             if payment.status == PaymentRecord.Status.COMPLETED),
            Decimal("0"),
        )

    @property
    def balance(self):
        return self.total - self.paid_total


class SaleLine(TenantScopedModel):
    class Kind(models.TextChoices):
        PRODUCT = "product", "Producto"
        SERVICE = "service", "Servicio"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name="lines")
    kind = models.CharField(max_length=8, choices=Kind.choices)
    product = models.ForeignKey(
        "inventory.Product", null=True, blank=True,
        on_delete=models.PROTECT, related_name="sale_lines",
    )
    service = models.ForeignKey(
        "catalog.Service", null=True, blank=True,
        on_delete=models.PROTECT, related_name="sale_lines",
    )
    description = models.CharField(max_length=180)
    sku = models.CharField(max_length=64, blank=True)
    quantity = models.DecimalField(max_digits=14, decimal_places=3)
    unit_price = models.DecimalField(max_digits=14, decimal_places=2)
    # Weighted-average cost captured on completion, used by margin reports.
    unit_cost = models.DecimalField(max_digits=14, decimal_places=4, default=Decimal("0"))

    class Meta:
        ordering = ["created_at"]
        indexes = [models.Index(fields=["company", "sale"])]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(kind="product", product__isnull=False, service__isnull=True)
                    | Q(kind="service", product__isnull=True, service__isnull=False)
                ),
                name="sale_line_exactly_one_item",
            ),
            models.CheckConstraint(condition=Q(quantity__gt=0), name="sale_line_quantity_positive"),
            models.CheckConstraint(condition=Q(unit_price__gte=0), name="sale_line_price_not_negative"),
            models.CheckConstraint(condition=Q(unit_cost__gte=0), name="sale_line_cost_not_negative"),
            models.UniqueConstraint(
                fields=["sale", "product"], condition=Q(product__isnull=False),
                name="unique_product_per_sale",
            ),
            models.UniqueConstraint(
                fields=["sale", "service"], condition=Q(service__isnull=False),
                name="unique_service_per_sale",
            ),
        ]

    def __str__(self):
        return f"{self.description} x {self.quantity}"

    @property
    def line_total(self):
        return (self.quantity * self.unit_price).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP,
        )


class PaymentRecord(TenantScopedModel):
    class Method(models.TextChoices):
        CASH = "cash", "Efectivo"
        CARD = "card", "Tarjeta"
        TRANSFER = "transfer", "Transferencia"
        OTHER = "other", "Otro"

    class Status(models.TextChoices):
        COMPLETED = "completed", "Confirmado"
        REFUNDED = "refunded", "Reembolsado"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sale = models.ForeignKey(Sale, on_delete=models.PROTECT, related_name="payments")
    cash_session = models.ForeignKey(
        CashSession, null=True, blank=True,
        on_delete=models.PROTECT, related_name="payments",
    )
    method = models.CharField(max_length=12, choices=Method.choices)
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    reference = models.CharField(max_length=120, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.COMPLETED)
    refunded_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        "identity.User", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="payments_created",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["company", "sale"]),
            models.Index(fields=["company", "cash_session"]),
            models.Index(fields=["company", "method", "created_at"]),
        ]
        constraints = [
            models.CheckConstraint(condition=Q(amount__gt=0), name="payment_amount_positive"),
        ]

    def __str__(self):
        return f"{self.get_method_display()} {self.amount} · {self.sale.number}"


class Expense(TenantScopedModel):
    class Method(models.TextChoices):
        CASH = "cash", "Efectivo"
        CARD = "card", "Tarjeta"
        TRANSFER = "transfer", "Transferencia"
        OTHER = "other", "Otro"

    class Status(models.TextChoices):
        ACTIVE = "active", "Activo"
        CANCELED = "canceled", "Anulado"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    number = models.CharField(max_length=32, default=default_expense_number)
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name="expenses")
    cash_session = models.ForeignKey(
        CashSession, null=True, blank=True,
        on_delete=models.PROTECT, related_name="expenses",
    )
    category = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    method = models.CharField(max_length=12, choices=Method.choices)
    reference = models.CharField(max_length=120, blank=True)
    incurred_at = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    canceled_at = models.DateTimeField(null=True, blank=True)
    canceled_reason = models.CharField(max_length=240, blank=True)
    created_by = models.ForeignKey(
        "identity.User", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="expenses_created",
    )

    class Meta:
        ordering = ["-incurred_at"]
        indexes = [
            models.Index(fields=["company", "branch", "incurred_at"]),
            models.Index(fields=["company", "status", "incurred_at"]),
        ]
        constraints = [
            models.UniqueConstraint(fields=["company", "number"], name="unique_expense_number_per_company"),
            models.CheckConstraint(condition=Q(amount__gt=0), name="expense_amount_positive"),
        ]

    def __str__(self):
        return f"{self.number} · {self.category} {self.amount}"
