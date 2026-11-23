import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.tenancy.models import Branch, TenantScopedModel

from .storage import asset_photo_upload_path, document_upload_path, private_storage


def _reference(prefix):
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"


def default_purchase_number():
    return _reference("OC")


def default_transfer_number():
    return _reference("TR")


def default_stocktake_number():
    return _reference("CT")


class Category(TenantScopedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["company", "active"])]
        constraints = [
            models.UniqueConstraint(fields=["company", "name"], name="unique_category_name_per_company"),
        ]

    def __str__(self):
        return self.name


class Product(TenantScopedModel):
    class Unit(models.TextChoices):
        UNIT = "unit", "Unidad"
        KG = "kg", "Kilogramo"
        G = "g", "Gramo"
        L = "l", "Litro"
        ML = "ml", "Mililitro"
        BOX = "box", "Caja"
        PACK = "pack", "Paquete"

    class Kind(models.TextChoices):
        STOCK = "stock", "Insumo con stock"
        ASSET = "asset", "Objeto"

    class AssetStatus(models.TextChoices):
        AVAILABLE = "available", "Disponible"
        ASSIGNED = "assigned", "Asignado"
        MAINTENANCE = "maintenance", "En mantenimiento"
        RETIRED = "retired", "Dado de baja"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sku = models.CharField(max_length=64)
    name = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    category = models.ForeignKey(
        Category, null=True, blank=True, on_delete=models.PROTECT, related_name="products",
    )
    unit = models.CharField(max_length=8, choices=Unit.choices, default=Unit.UNIT)
    cost = models.DecimalField(max_digits=14, decimal_places=4, default=Decimal("0"))
    price = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    reorder_point = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal("0"))
    barcode = models.CharField(max_length=64, blank=True)
    active = models.BooleanField(default=True)
    kind = models.CharField(max_length=8, choices=Kind.choices, default=Kind.STOCK)
    status = models.CharField(
        max_length=12, choices=AssetStatus.choices, default=AssetStatus.AVAILABLE,
    )
    branch = models.ForeignKey(
        Branch, null=True, blank=True, on_delete=models.PROTECT,
        related_name="asset_products",
    )
    assigned_worker = models.ForeignKey(
        "workforce.WorkerProfile", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="assigned_assets",
    )
    serial_number = models.CharField(max_length=120, blank=True)
    internal_code = models.CharField(max_length=64, blank=True)
    quantity = models.PositiveIntegerField(default=1)
    purchase_date = models.DateField(null=True, blank=True)
    supplier = models.ForeignKey(
        "inventory.Supplier", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="assets",
    )
    warranty_until = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    photo = models.FileField(
        upload_to=asset_photo_upload_path, storage=private_storage, blank=True,
        max_length=255,
    )
    photo_content_type = models.CharField(max_length=120, blank=True)
    photo_size = models.PositiveBigIntegerField(default=0)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["company", "active"]),
            models.Index(fields=["company", "name"]),
            models.Index(fields=["company", "kind", "active"]),
            models.Index(fields=["company", "branch", "kind"]),
        ]
        constraints = [
            models.UniqueConstraint(fields=["company", "sku"], name="unique_product_sku_per_company"),
        ]

    def __str__(self):
        return f"{self.sku} · {self.name}"


class Document(TenantScopedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    client_id = models.UUIDField(null=True, blank=True)
    name = models.CharField(max_length=180)
    original_name = models.CharField(max_length=255)
    content_type = models.CharField(max_length=120, blank=True)
    size = models.PositiveBigIntegerField(default=0)
    file = models.FileField(
        upload_to=document_upload_path, storage=private_storage, max_length=255,
    )
    product = models.ForeignKey(
        Product, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="documents",
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="uploaded_documents",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["company", "created_at"]),
            models.Index(fields=["company", "product"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "client_id"],
                condition=models.Q(client_id__isnull=False),
                name="unique_document_client_id_per_company",
            ),
        ]

    def __str__(self):
        return self.name


class Warehouse(TenantScopedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    branch = models.ForeignKey(
        Branch, null=True, blank=True, on_delete=models.PROTECT, related_name="warehouses",
    )
    name = models.CharField(max_length=160)
    code = models.CharField(max_length=32)
    address = models.CharField(max_length=240, blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["company", "active"])]
        constraints = [
            models.UniqueConstraint(fields=["company", "code"], name="unique_warehouse_code_per_company"),
        ]

    def __str__(self):
        return f"{self.code} · {self.name}"


class Supplier(TenantScopedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=180)
    tax_identifier = models.CharField(max_length=32, blank=True)
    contact_name = models.CharField(max_length=160, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=32, blank=True)
    address = models.CharField(max_length=240, blank=True)
    notes = models.TextField(blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["company", "active"])]

    def __str__(self):
        return self.name


class StockBalance(TenantScopedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="balances")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="balances")
    quantity = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal("0"))
    average_cost = models.DecimalField(max_digits=14, decimal_places=4, default=Decimal("0"))

    class Meta:
        ordering = ["warehouse__name", "product__name"]
        indexes = [
            models.Index(fields=["company", "warehouse"]),
            models.Index(fields=["company", "product"]),
        ]
        constraints = [
            models.UniqueConstraint(fields=["warehouse", "product"], name="unique_stock_per_warehouse_product"),
            models.CheckConstraint(condition=models.Q(quantity__gte=0), name="stock_quantity_not_negative"),
            models.CheckConstraint(condition=models.Q(average_cost__gte=0), name="stock_cost_not_negative"),
        ]

    def __str__(self):
        return f"{self.warehouse} / {self.product} = {self.quantity}"

    @property
    def value(self):
        return self.quantity * self.average_cost


class InventoryMovement(TenantScopedModel):
    """Append-only stock ledger; corrections are new compensating movements."""

    class Kind(models.TextChoices):
        ENTRY = "entry", "Ingreso manual"
        EXIT = "exit", "Salida manual"
        PURCHASE_RECEIPT = "purchase_receipt", "Recepción de compra"
        TRANSFER_OUT = "transfer_out", "Salida por transferencia"
        TRANSFER_IN = "transfer_in", "Ingreso por transferencia"
        STOCKTAKE = "stocktake", "Ajuste por conteo"
        SALE = "sale", "Salida por venta"
        SALE_CANCEL = "sale_cancel", "Ingreso por anulación de venta"

    class Direction(models.TextChoices):
        IN = "in", "Entrada"
        OUT = "out", "Salida"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="movements")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="movements")
    kind = models.CharField(max_length=24, choices=Kind.choices)
    direction = models.CharField(max_length=4, choices=Direction.choices)
    quantity = models.DecimalField(max_digits=14, decimal_places=3)
    unit_cost = models.DecimalField(max_digits=14, decimal_places=4, default=Decimal("0"))
    balance_after = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal("0"))
    reference_type = models.CharField(max_length=32, blank=True)
    reference_id = models.CharField(max_length=64, blank=True)
    note = models.CharField(max_length=240, blank=True)
    actor = models.ForeignKey(
        "identity.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="inventory_movements",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["company", "warehouse", "product", "created_at"]),
            models.Index(fields=["company", "created_at"]),
        ]
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="movement_quantity_positive"),
        ]

    def __str__(self):
        return f"{self.get_kind_display()} {self.quantity} {self.product}"

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError(
                "Los movimientos de inventario son inmutables; registra un movimiento de compensación."
            )
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError(
            "Los movimientos de inventario no se eliminan; registra un movimiento de compensación."
        )


class PurchaseOrder(TenantScopedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Borrador"
        ORDERED = "ordered", "Pedida"
        RECEIVED = "received", "Recibida"
        CANCELED = "canceled", "Cancelada"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    number = models.CharField(max_length=32, default=default_purchase_number)
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name="purchase_orders")
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="purchase_orders")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    expected_at = models.DateTimeField(null=True, blank=True)
    ordered_at = models.DateTimeField(null=True, blank=True)
    received_at = models.DateTimeField(null=True, blank=True)
    canceled_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        "identity.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="purchase_orders",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["company", "status", "created_at"])]
        constraints = [
            models.UniqueConstraint(fields=["company", "number"], name="unique_purchase_number_per_company"),
        ]

    def __str__(self):
        return f"{self.number} · {self.supplier}"

    @property
    def total(self):
        return sum((line.subtotal for line in self.lines.all()), Decimal("0"))


class PurchaseLine(TenantScopedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    purchase = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name="lines")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="purchase_lines")
    quantity = models.DecimalField(max_digits=14, decimal_places=3)
    unit_cost = models.DecimalField(max_digits=14, decimal_places=4)

    class Meta:
        ordering = ["created_at"]
        constraints = [
            models.UniqueConstraint(fields=["purchase", "product"], name="unique_product_per_purchase"),
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="purchase_quantity_positive"),
            models.CheckConstraint(condition=models.Q(unit_cost__gte=0), name="purchase_cost_not_negative"),
        ]

    def __str__(self):
        return f"{self.product} x {self.quantity}"

    @property
    def subtotal(self):
        return self.quantity * self.unit_cost


class Transfer(TenantScopedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Borrador"
        IN_TRANSIT = "in_transit", "En tránsito"
        COMPLETED = "completed", "Completada"
        CANCELED = "canceled", "Cancelada"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    number = models.CharField(max_length=32, default=default_transfer_number)
    from_warehouse = models.ForeignKey(
        Warehouse, on_delete=models.PROTECT, related_name="transfers_out",
    )
    to_warehouse = models.ForeignKey(
        Warehouse, on_delete=models.PROTECT, related_name="transfers_in",
    )
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    dispatched_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    canceled_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        "identity.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="transfers",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["company", "status", "created_at"])]
        constraints = [
            models.UniqueConstraint(fields=["company", "number"], name="unique_transfer_number_per_company"),
            models.CheckConstraint(
                condition=~models.Q(from_warehouse=models.F("to_warehouse")),
                name="transfer_warehouses_differ",
            ),
        ]

    def __str__(self):
        return f"{self.number} · {self.from_warehouse} → {self.to_warehouse}"


class TransferLine(TenantScopedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transfer = models.ForeignKey(Transfer, on_delete=models.CASCADE, related_name="lines")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="transfer_lines")
    quantity = models.DecimalField(max_digits=14, decimal_places=3)
    unit_cost = models.DecimalField(max_digits=14, decimal_places=4, default=Decimal("0"))

    class Meta:
        ordering = ["created_at"]
        constraints = [
            models.UniqueConstraint(fields=["transfer", "product"], name="unique_product_per_transfer"),
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="transfer_quantity_positive"),
        ]

    def __str__(self):
        return f"{self.product} x {self.quantity}"


class Stocktake(TenantScopedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Borrador"
        COMPLETED = "completed", "Conciliado"
        CANCELED = "canceled", "Cancelado"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    number = models.CharField(max_length=32, default=default_stocktake_number)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="stocktakes")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    completed_at = models.DateTimeField(null=True, blank=True)
    canceled_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        "identity.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="stocktakes",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["company", "status", "created_at"])]
        constraints = [
            models.UniqueConstraint(fields=["company", "number"], name="unique_stocktake_number_per_company"),
        ]

    def __str__(self):
        return f"{self.number} · {self.warehouse}"


class StocktakeLine(TenantScopedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    stocktake = models.ForeignKey(Stocktake, on_delete=models.CASCADE, related_name="lines")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="stocktake_lines")
    counted_quantity = models.DecimalField(max_digits=14, decimal_places=3)
    expected_quantity = models.DecimalField(max_digits=14, decimal_places=3, null=True, blank=True)
    difference = models.DecimalField(max_digits=14, decimal_places=3, null=True, blank=True)

    class Meta:
        ordering = ["created_at"]
        constraints = [
            models.UniqueConstraint(fields=["stocktake", "product"], name="unique_product_per_stocktake"),
            models.CheckConstraint(condition=models.Q(counted_quantity__gte=0), name="stocktake_count_not_negative"),
        ]

    def __str__(self):
        return f"{self.product} contado {self.counted_quantity}"
