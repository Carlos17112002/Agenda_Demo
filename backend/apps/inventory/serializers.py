import uuid
from decimal import Decimal
from pathlib import Path

from django.db import transaction
from rest_framework import serializers

from apps.audit.services import record_event
from apps.tenancy.models import Branch, Company
from apps.tenancy.serializers import TenantOwnedSerializer, request_tenant
from apps.workforce.models import WorkerProfile

from .files import (
    COMPANY_STORAGE_LIMIT_BYTES, sanitize_filename, storage_usage, validate_asset_photo,
    validate_document,
)
from .models import (
    Category, Document, InventoryMovement, Product, PurchaseLine, PurchaseOrder, StockBalance,
    Stocktake, StocktakeLine, Supplier, Transfer, TransferLine, Warehouse,
)


def _ensure_company(value, company, field):
    if value is not None and value.company_id != company.id:
        raise serializers.ValidationError({field: "El recurso debe pertenecer a la empresa activa."})
    return value


class RejectCompanyMixin:
    def to_internal_value(self, data):
        if "company" in data:
            raise serializers.ValidationError({"company": "La empresa se asigna desde el contexto autenticado."})
        return super().to_internal_value(data)


class CategorySerializer(TenantOwnedSerializer):
    class Meta:
        model = Category
        fields = ["id", "company", "name", "description", "active", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate(self, attrs):
        tenant = request_tenant(self.context["request"])
        name = attrs.get("name", getattr(self.instance, "name", None))
        if name:
            existing = Category.objects.filter(company=tenant, name=name)
            if self.instance is not None:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise serializers.ValidationError({"name": "Ya existe una categoría con este nombre."})
        return attrs


def _generate_asset_sku(company):
    for _ in range(20):
        sku = f"ACT-{uuid.uuid4().hex[:8].upper()}"
        if not Product.objects.filter(company=company, sku=sku).exists():
            return sku
    raise serializers.ValidationError({"sku": "No se pudo generar un SKU único."})


class ProductSerializer(TenantOwnedSerializer):
    category = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(), required=False, allow_null=True,
    )
    branch = serializers.PrimaryKeyRelatedField(
        queryset=Branch.objects.all(), required=False, allow_null=True,
    )
    assigned_worker = serializers.PrimaryKeyRelatedField(
        queryset=WorkerProfile.objects.all(), required=False, allow_null=True,
    )
    supplier = serializers.PrimaryKeyRelatedField(
        queryset=Supplier.objects.all(), required=False, allow_null=True,
    )
    sku = serializers.CharField(required=False, allow_blank=True, max_length=64)
    quantity = serializers.IntegerField(required=False, min_value=1)
    category_name = serializers.CharField(source="category.name", read_only=True)
    unit_display = serializers.CharField(source="get_unit_display", read_only=True)
    kind_display = serializers.CharField(source="get_kind_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    branch_name = serializers.CharField(source="branch.name", read_only=True)
    assigned_worker_name = serializers.SerializerMethodField()
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)
    photo_url = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id", "company", "kind", "kind_display", "status", "status_display",
            "sku", "name", "description", "category", "category_name", "unit",
            "unit_display", "cost", "price", "reorder_point", "barcode",
            "branch", "branch_name", "assigned_worker", "assigned_worker_name",
            "serial_number", "internal_code", "quantity", "purchase_date",
            "supplier", "supplier_name", "warranty_until", "notes",
            "photo_url", "photo_content_type", "photo_size", "active",
            "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "photo_content_type", "photo_size", "created_at", "updated_at",
        ]

    def get_assigned_worker_name(self, obj):
        return str(obj.assigned_worker) if obj.assigned_worker_id else ""

    def get_photo_url(self, obj):
        if not obj.photo:
            return ""
        return f"/api/v1/inventory/products/{obj.id}/photo/"

    def validate_category(self, category):
        return _ensure_company(category, request_tenant(self.context["request"]), "category")

    def validate_branch(self, branch):
        return _ensure_company(branch, request_tenant(self.context["request"]), "branch")

    def validate_assigned_worker(self, worker):
        return _ensure_company(worker, request_tenant(self.context["request"]), "assigned_worker")

    def validate_supplier(self, supplier):
        return _ensure_company(supplier, request_tenant(self.context["request"]), "supplier")

    def validate(self, attrs):
        tenant = request_tenant(self.context["request"])
        instance = self.instance
        kind = attrs.get("kind", getattr(instance, "kind", Product.Kind.STOCK))
        if instance is not None and "kind" in attrs and attrs["kind"] != instance.kind:
            raise serializers.ValidationError(
                {"kind": "El tipo de producto no se puede cambiar."}
            )
        if kind == Product.Kind.STOCK:
            attrs["status"] = Product.AssetStatus.AVAILABLE
            sku = (attrs.get("sku") or getattr(instance, "sku", "")).strip()
            if not sku:
                raise serializers.ValidationError(
                    {"sku": "El SKU es obligatorio para insumos con stock."}
                )
            attrs["sku"] = sku
        else:
            sku = (attrs.get("sku") or getattr(instance, "sku", "")).strip()
            attrs["sku"] = sku or _generate_asset_sku(tenant)

        existing = Product.objects.filter(company=tenant, sku=attrs["sku"])
        if instance is not None:
            existing = existing.exclude(pk=instance.pk)
        if existing.exists():
            raise serializers.ValidationError({"sku": "Ya existe un producto con este SKU."})
        return attrs


class WarehouseSerializer(TenantOwnedSerializer):
    branch = serializers.PrimaryKeyRelatedField(
        queryset=Branch.objects.all(), required=False, allow_null=True,
    )
    branch_name = serializers.CharField(source="branch.name", read_only=True)

    class Meta:
        model = Warehouse
        fields = ["id", "company", "branch", "branch_name", "name", "code", "address", "active",
                  "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_branch(self, branch):
        return _ensure_company(branch, request_tenant(self.context["request"]), "branch")

    def validate(self, attrs):
        tenant = request_tenant(self.context["request"])
        code = attrs.get("code", getattr(self.instance, "code", None))
        if code:
            existing = Warehouse.objects.filter(company=tenant, code=code)
            if self.instance is not None:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise serializers.ValidationError({"code": "Ya existe una bodega con este código."})
        return attrs


class SupplierSerializer(TenantOwnedSerializer):
    class Meta:
        model = Supplier
        fields = ["id", "company", "name", "tax_identifier", "contact_name", "email", "phone",
                  "address", "notes", "active", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class StockBalanceSerializer(serializers.ModelSerializer):
    company = serializers.UUIDField(source="company_id", read_only=True)
    warehouse = serializers.UUIDField(source="warehouse_id", read_only=True)
    warehouse_name = serializers.CharField(source="warehouse.name", read_only=True)
    product = serializers.UUIDField(source="product_id", read_only=True)
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_sku = serializers.CharField(source="product.sku", read_only=True)
    quantity = serializers.DecimalField(max_digits=14, decimal_places=3, read_only=True)
    average_cost = serializers.DecimalField(max_digits=14, decimal_places=4, read_only=True)
    value = serializers.DecimalField(max_digits=18, decimal_places=4, read_only=True)

    class Meta:
        model = StockBalance
        fields = ["id", "company", "warehouse", "warehouse_name", "product", "product_name",
                  "product_sku", "quantity", "average_cost", "value", "updated_at"]
        read_only_fields = fields


class InventoryMovementSerializer(serializers.ModelSerializer):
    company = serializers.UUIDField(source="company_id", read_only=True)
    warehouse = serializers.UUIDField(source="warehouse_id", read_only=True)
    warehouse_name = serializers.CharField(source="warehouse.name", read_only=True)
    product = serializers.UUIDField(source="product_id", read_only=True)
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_sku = serializers.CharField(source="product.sku", read_only=True)
    kind_display = serializers.CharField(source="get_kind_display", read_only=True)
    direction_display = serializers.CharField(source="get_direction_display", read_only=True)
    actor_email = serializers.EmailField(source="actor.email", read_only=True, allow_null=True)
    quantity = serializers.DecimalField(max_digits=14, decimal_places=3, read_only=True)
    unit_cost = serializers.DecimalField(max_digits=14, decimal_places=4, read_only=True)
    balance_after = serializers.DecimalField(max_digits=14, decimal_places=3, read_only=True)

    class Meta:
        model = InventoryMovement
        fields = ["id", "company", "warehouse", "warehouse_name", "product", "product_name",
                  "product_sku", "kind", "kind_display", "direction", "direction_display",
                  "quantity", "unit_cost", "balance_after", "reference_type", "reference_id",
                  "note", "actor_email", "created_at"]
        read_only_fields = fields


class ManualMovementSerializer(RejectCompanyMixin, serializers.Serializer):
    warehouse = serializers.PrimaryKeyRelatedField(queryset=Warehouse.objects.all())
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())
    kind = serializers.ChoiceField(choices=[
        InventoryMovement.Kind.ENTRY, InventoryMovement.Kind.EXIT,
    ])
    quantity = serializers.DecimalField(max_digits=14, decimal_places=3, min_value=Decimal("0.001"))
    unit_cost = serializers.DecimalField(
        max_digits=14, decimal_places=4, min_value=Decimal("0"), required=False, allow_null=True,
    )
    note = serializers.CharField(required=False, allow_blank=True, max_length=240)

    def validate(self, attrs):
        company = request_tenant(self.context["request"])
        _ensure_company(attrs["warehouse"], company, "warehouse")
        _ensure_company(attrs["product"], company, "product")
        return attrs


class PurchaseLineSerializer(serializers.ModelSerializer):
    product = serializers.UUIDField(source="product_id", read_only=True)
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_sku = serializers.CharField(source="product.sku", read_only=True)
    quantity = serializers.DecimalField(max_digits=14, decimal_places=3, read_only=True)
    unit_cost = serializers.DecimalField(max_digits=14, decimal_places=4, read_only=True)
    subtotal = serializers.DecimalField(max_digits=18, decimal_places=4, read_only=True)

    class Meta:
        model = PurchaseLine
        fields = ["id", "product", "product_name", "product_sku", "quantity", "unit_cost", "subtotal"]
        read_only_fields = fields


class PurchaseOrderSerializer(serializers.ModelSerializer):
    company = serializers.UUIDField(source="company_id", read_only=True)
    supplier = serializers.UUIDField(source="supplier_id", read_only=True)
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)
    warehouse = serializers.UUIDField(source="warehouse_id", read_only=True)
    warehouse_name = serializers.CharField(source="warehouse.name", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    lines = PurchaseLineSerializer(many=True, read_only=True)
    total = serializers.DecimalField(max_digits=18, decimal_places=4, read_only=True)
    created_by_email = serializers.EmailField(source="created_by.email", read_only=True, allow_null=True)

    class Meta:
        model = PurchaseOrder
        fields = ["id", "company", "number", "supplier", "supplier_name", "warehouse",
                  "warehouse_name", "status", "status_display", "expected_at", "ordered_at",
                  "received_at", "canceled_at", "notes", "lines", "total", "created_by_email",
                  "created_at", "updated_at"]
        read_only_fields = fields


class PurchaseLineInputSerializer(RejectCompanyMixin, serializers.Serializer):
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())
    quantity = serializers.DecimalField(max_digits=14, decimal_places=3, min_value=Decimal("0.001"))
    unit_cost = serializers.DecimalField(
        max_digits=14, decimal_places=4, min_value=Decimal("0"), required=False, default=Decimal("0"),
    )


class PurchaseOrderWriteSerializer(RejectCompanyMixin, serializers.Serializer):
    supplier = serializers.PrimaryKeyRelatedField(queryset=Supplier.objects.all())
    warehouse = serializers.PrimaryKeyRelatedField(queryset=Warehouse.objects.all())
    expected_at = serializers.DateTimeField(required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True, max_length=2000)
    lines = PurchaseLineInputSerializer(many=True)

    def validate(self, attrs):
        if self.instance is not None and "lines" in self.initial_data:
            raise serializers.ValidationError(
                {"lines": "Cancela la orden y crea una nueva para cambiar las líneas."}
            )
        return attrs


class TransferLineSerializer(serializers.ModelSerializer):
    product = serializers.UUIDField(source="product_id", read_only=True)
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_sku = serializers.CharField(source="product.sku", read_only=True)
    quantity = serializers.DecimalField(max_digits=14, decimal_places=3, read_only=True)
    unit_cost = serializers.DecimalField(max_digits=14, decimal_places=4, read_only=True)

    class Meta:
        model = TransferLine
        fields = ["id", "product", "product_name", "product_sku", "quantity", "unit_cost"]
        read_only_fields = fields


class TransferSerializer(serializers.ModelSerializer):
    company = serializers.UUIDField(source="company_id", read_only=True)
    from_warehouse = serializers.UUIDField(source="from_warehouse_id", read_only=True)
    from_warehouse_name = serializers.CharField(source="from_warehouse.name", read_only=True)
    to_warehouse = serializers.UUIDField(source="to_warehouse_id", read_only=True)
    to_warehouse_name = serializers.CharField(source="to_warehouse.name", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    lines = TransferLineSerializer(many=True, read_only=True)
    created_by_email = serializers.EmailField(source="created_by.email", read_only=True, allow_null=True)

    class Meta:
        model = Transfer
        fields = ["id", "company", "number", "from_warehouse", "from_warehouse_name",
                  "to_warehouse", "to_warehouse_name", "status", "status_display", "dispatched_at",
                  "completed_at", "canceled_at", "notes", "lines", "created_by_email",
                  "created_at", "updated_at"]
        read_only_fields = fields


class TransferLineInputSerializer(RejectCompanyMixin, serializers.Serializer):
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())
    quantity = serializers.DecimalField(max_digits=14, decimal_places=3, min_value=Decimal("0.001"))


class TransferWriteSerializer(RejectCompanyMixin, serializers.Serializer):
    from_warehouse = serializers.PrimaryKeyRelatedField(queryset=Warehouse.objects.all())
    to_warehouse = serializers.PrimaryKeyRelatedField(queryset=Warehouse.objects.all())
    lines = TransferLineInputSerializer(many=True)
    notes = serializers.CharField(required=False, allow_blank=True, max_length=2000)


class StocktakeLineSerializer(serializers.ModelSerializer):
    product = serializers.UUIDField(source="product_id", read_only=True)
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_sku = serializers.CharField(source="product.sku", read_only=True)
    counted_quantity = serializers.DecimalField(max_digits=14, decimal_places=3, read_only=True)
    expected_quantity = serializers.DecimalField(
        max_digits=14, decimal_places=3, read_only=True, allow_null=True,
    )
    difference = serializers.DecimalField(
        max_digits=14, decimal_places=3, read_only=True, allow_null=True,
    )

    class Meta:
        model = StocktakeLine
        fields = ["id", "product", "product_name", "product_sku", "counted_quantity",
                  "expected_quantity", "difference"]
        read_only_fields = fields


class StocktakeSerializer(serializers.ModelSerializer):
    company = serializers.UUIDField(source="company_id", read_only=True)
    warehouse = serializers.UUIDField(source="warehouse_id", read_only=True)
    warehouse_name = serializers.CharField(source="warehouse.name", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    lines = StocktakeLineSerializer(many=True, read_only=True)
    created_by_email = serializers.EmailField(source="created_by.email", read_only=True, allow_null=True)

    class Meta:
        model = Stocktake
        fields = ["id", "company", "number", "warehouse", "warehouse_name", "status",
                  "status_display", "completed_at", "canceled_at", "notes", "lines",
                  "created_by_email", "created_at", "updated_at"]
        read_only_fields = fields


class StocktakeLineInputSerializer(RejectCompanyMixin, serializers.Serializer):
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())
    counted_quantity = serializers.DecimalField(max_digits=14, decimal_places=3, min_value=Decimal("0"))


class StocktakeWriteSerializer(RejectCompanyMixin, serializers.Serializer):
    warehouse = serializers.PrimaryKeyRelatedField(queryset=Warehouse.objects.all())
    lines = StocktakeLineInputSerializer(many=True)
    notes = serializers.CharField(required=False, allow_blank=True, max_length=2000)


class CancelSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, max_length=240)


class DocumentSerializer(serializers.ModelSerializer):
    company = serializers.UUIDField(source="company_id", read_only=True)
    product = serializers.UUIDField(source="product_id", read_only=True)
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_sku = serializers.CharField(source="product.sku", read_only=True)
    uploaded_by_email = serializers.EmailField(
        source="uploaded_by.email", read_only=True, allow_null=True,
    )
    download_url = serializers.SerializerMethodField()

    class Meta:
        model = Document
        fields = [
            "id", "company", "client_id", "name", "original_name", "content_type",
            "size", "product", "product_name", "product_sku", "uploaded_by_email",
            "download_url", "created_at", "updated_at",
        ]
        read_only_fields = fields

    def get_download_url(self, obj):
        return f"/api/v1/inventory/documents/{obj.id}/download/"


class DocumentUploadSerializer(serializers.Serializer):
    file = serializers.FileField()
    name = serializers.CharField(required=False, allow_blank=True, max_length=180)
    product = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(), required=False, allow_null=True,
    )
    client_id = serializers.UUIDField(required=False, allow_null=True)

    def validate_file(self, upload):
        self.original_name = validate_document(upload)
        return upload

    def validate_product(self, product):
        if product is None:
            return product
        company = request_tenant(self.context["request"])
        if product.company_id != company.id:
            raise serializers.ValidationError("El producto debe pertenecer a la empresa activa.")
        if not product.active:
            raise serializers.ValidationError("El producto está inactivo.")
        return product

    def create(self, validated_data):
        request = self.context["request"]
        company = request_tenant(request)
        upload = validated_data["file"]
        original_name = getattr(self, "original_name", sanitize_filename(upload.name))
        product = validated_data.get("product")
        client_id = validated_data.get("client_id")
        limit_bytes = self.context.get("storage_limit_bytes", COMPANY_STORAGE_LIMIT_BYTES)

        with transaction.atomic():
            Company.objects.select_for_update().get(pk=company.pk)
            if client_id is not None:
                existing = Document.objects.filter(
                    company=company, client_id=client_id,
                ).first()
                if existing is not None:
                    return existing, False
            usage = storage_usage(company)
            if usage["used_bytes"] + upload.size > limit_bytes:
                raise serializers.ValidationError(
                    {"detail": "La empresa alcanzó el límite de 5 GB de almacenamiento."}
                )
            document = Document.objects.create(
                company=company,
                client_id=client_id,
                name=(validated_data.get("name") or Path(original_name).stem)[:180],
                original_name=original_name,
                content_type=(upload.content_type or "application/octet-stream")[:120],
                size=upload.size,
                file=upload,
                product=product,
                uploaded_by=request.user if request.user.is_authenticated else None,
            )
        record_event(
            company=company, actor=request.user, action="inventory.document.created",
            instance=document, metadata={"name": document.name,
                                        "product_id": str(product.id) if product else None},
        )
        return document, True


class AssetPhotoSerializer(serializers.Serializer):
    photo = serializers.ImageField()

    def validate_photo(self, photo):
        validate_asset_photo(photo)
        return photo
