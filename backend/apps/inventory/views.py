from decimal import Decimal
from pathlib import Path

from django.db.models import F, Q
from django.http import FileResponse
from rest_framework import permissions, status
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.mixins import ListModelMixin, RetrieveModelMixin
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from apps.audit.services import record_event
from apps.tenancy.api import TenantModelViewSet
from apps.tenancy.authentication import resolve_tenant
from apps.tenancy.permissions import HasTenantContext, HasTenantPermission

from .files import COMPANY_STORAGE_LIMIT_BYTES, sanitize_filename, storage_usage
from .models import (
    Category, Document, InventoryMovement, Product, PurchaseOrder, StockBalance, Stocktake,
    Supplier, Transfer, Warehouse,
)
from .serializers import (
    AssetPhotoSerializer, CancelSerializer, CategorySerializer, DocumentSerializer,
    DocumentUploadSerializer, InventoryMovementSerializer, ManualMovementSerializer,
    ProductSerializer, PurchaseOrderSerializer, PurchaseOrderWriteSerializer,
    StockBalanceSerializer, StocktakeSerializer, StocktakeWriteSerializer, SupplierSerializer,
    TransferSerializer, TransferWriteSerializer, WarehouseSerializer,
)
from .services import (
    cancel_purchase_order, cancel_stocktake, cancel_transfer, complete_stocktake,
    complete_transfer, create_manual_movement, create_purchase_order, create_stocktake,
    create_transfer, dispatch_transfer, receive_purchase_order, submit_purchase_order,
    update_purchase_order,
)
from .storage import private_storage

INVENTORY_READ = {"list": "inventory.read", "retrieve": "inventory.read"}
INVENTORY_WRITE = {
    "create": "inventory.write", "update": "inventory.write",
    "partial_update": "inventory.write", "destroy": "inventory.write",
}
PURCHASE_READ = {"list": "purchases.read", "retrieve": "purchases.read"}
PURCHASE_WRITE = {
    "create": "purchases.write", "update": "purchases.write",
    "partial_update": "purchases.write", "destroy": "purchases.write",
}


def _active(view, queryset):
    active = view.request.query_params.get("active")
    if active in {"true", "false"}:
        return queryset.filter(active=active == "true")
    return queryset


def _reason(request):
    serializer = CancelSerializer(data=request.data or {})
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data.get("reason", "")


class DocumentViewSet(ListModelMixin, RetrieveModelMixin, GenericViewSet):
    serializer_class = DocumentSerializer
    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [permissions.IsAuthenticated, HasTenantContext, HasTenantPermission]
    http_method_names = ["get", "post", "delete", "head", "options"]
    permission_map = {
        "list": "inventory.read", "retrieve": "inventory.read",
        "download": "inventory.read", "storage": "inventory.read",
        "create": "inventory.write", "destroy": "inventory.write",
    }

    def get_required_tenant_permission(self):
        return self.permission_map.get(self.action)

    def get_tenant(self):
        tenant = getattr(self.request, "tenant", None)
        if tenant is None:
            tenant = resolve_tenant(self.request, self.request.user)
        if tenant is None:
            raise PermissionDenied("Selecciona una empresa.")
        return tenant

    def get_queryset(self):
        return self.queryset_for_tenant(self.get_tenant())

    def queryset_for_tenant(self, tenant):
        queryset = (Document.objects.filter(company=tenant)
                    .select_related("product", "uploaded_by"))
        product = self.request.query_params.get("product")
        if product:
            queryset = queryset.filter(product_id=product)
        linked = self.request.query_params.get("linked")
        if linked == "true":
            queryset = queryset.filter(product__isnull=False)
        elif linked == "false":
            queryset = queryset.filter(product__isnull=True)
        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) | Q(original_name__icontains=search)
            )
        return queryset

    def create(self, request, *args, **kwargs):
        serializer = DocumentUploadSerializer(
            data=request.data,
            context={
                **self.get_serializer_context(),
                "storage_limit_bytes": COMPANY_STORAGE_LIMIT_BYTES,
            },
        )
        serializer.is_valid(raise_exception=True)
        document, created = serializer.save()
        status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(
            DocumentSerializer(document, context=self.get_serializer_context()).data,
            status=status_code,
        )

    def destroy(self, request, *args, **kwargs):
        document = self.get_object()
        record_event(
            company=self.get_tenant(), actor=request.user,
            action="inventory.document.deleted", instance=document,
            metadata={"name": document.name},
        )
        document.file.delete(save=False)
        document.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["get"])
    def download(self, request, pk=None):
        document = self.get_object()
        try:
            handle = document.file.open("rb")
        except FileNotFoundError:
            raise NotFound("El archivo ya no está disponible.")
        response = FileResponse(
            handle,
            as_attachment=True,
            filename=sanitize_filename(document.original_name),
            content_type=document.content_type or "application/octet-stream",
        )
        response["X-Content-Type-Options"] = "nosniff"
        response["Cache-Control"] = "private, no-store"
        record_event(
            company=self.get_tenant(), actor=request.user,
            action="inventory.document.downloaded", instance=document,
            metadata={"name": document.name},
        )
        return response

    @action(detail=False, methods=["get"])
    def storage(self, request):
        return Response(storage_usage(self.get_tenant()))


class CategoryViewSet(TenantModelViewSet):
    serializer_class = CategorySerializer
    audit_name = "category"
    soft_delete = True
    permission_map = {**INVENTORY_READ, **INVENTORY_WRITE}
    search_fields = ["name", "description"]
    ordering_fields = ["name", "created_at"]

    def queryset_for_tenant(self, tenant):
        return _active(self, Category.objects.filter(company=tenant))


class ProductViewSet(TenantModelViewSet):
    serializer_class = ProductSerializer
    audit_name = "product"
    soft_delete = True
    permission_map = {**INVENTORY_READ, **INVENTORY_WRITE, "photo": "inventory.write"}
    search_fields = ["sku", "name", "barcode", "description"]
    ordering_fields = ["name", "sku", "price", "cost", "created_at"]

    def get_required_tenant_permission(self):
        if self.action == "photo" and self.request.method == "GET":
            return "inventory.read"
        return super().get_required_tenant_permission()

    @action(
        detail=True, methods=["get", "post", "delete"], url_path="photo",
        parser_classes=[MultiPartParser, FormParser],
    )
    def photo(self, request, pk=None):
        product = self.get_object()

        if request.method == "GET":
            if not product.photo:
                raise NotFound("El objeto no tiene foto.")
            try:
                handle = product.photo.open("rb")
            except FileNotFoundError:
                raise NotFound("La foto ya no está disponible.")
            response = FileResponse(
                handle, as_attachment=False,
                filename=sanitize_filename(Path(product.photo.name).name),
                content_type=product.photo_content_type or "application/octet-stream",
            )
            response["X-Content-Type-Options"] = "nosniff"
            response["Cache-Control"] = "private, max-age=300"
            return response

        if product.kind != Product.Kind.ASSET:
            raise ValidationError({"detail": "Solo los objetos admiten foto."})

        if request.method == "DELETE":
            old_name = product.photo.name
            product.photo.delete(save=False)
            product.photo_content_type = ""
            product.photo_size = 0
            product.save(update_fields=[
                "photo", "photo_content_type", "photo_size", "updated_at",
            ])
            if old_name:
                private_storage.delete(old_name)
            record_event(
                company=self.get_tenant(), actor=request.user,
                action="inventory.asset.photo_removed", instance=product,
            )
            return Response(status=status.HTTP_204_NO_CONTENT)

        serializer = AssetPhotoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        upload = serializer.validated_data["photo"]
        usage = storage_usage(self.get_tenant())
        if usage["used_bytes"] + upload.size > COMPANY_STORAGE_LIMIT_BYTES:
            raise ValidationError(
                {"detail": "La empresa alcanzó el límite de 5 GB de almacenamiento."}
            )
        old_name = product.photo.name
        product.photo = upload
        product.photo_content_type = upload.content_type or "image/png"
        product.photo_size = upload.size
        product.save(update_fields=[
            "photo", "photo_content_type", "photo_size", "updated_at",
        ])
        if old_name:
            private_storage.delete(old_name)
        record_event(
            company=self.get_tenant(), actor=request.user,
            action="inventory.asset.photo_set", instance=product,
        )
        return Response(
            ProductSerializer(product, context=self.get_serializer_context()).data,
        )

    def queryset_for_tenant(self, tenant):
        queryset = (Product.objects.filter(company=tenant)
                    .select_related("category", "branch", "assigned_worker", "supplier"))
        category = self.request.query_params.get("category")
        if category:
            queryset = queryset.filter(category_id=category)
        kind = self.request.query_params.get("kind")
        if kind:
            if kind not in Product.Kind.values:
                from rest_framework.exceptions import ValidationError
                raise ValidationError({"kind": "Tipo de producto inválido."})
            queryset = queryset.filter(kind=kind)
        status_value = self.request.query_params.get("status")
        if status_value:
            if status_value not in Product.AssetStatus.values:
                from rest_framework.exceptions import ValidationError
                raise ValidationError({"status": "Estado de objeto inválido."})
            queryset = queryset.filter(status=status_value)
        branch = self.request.query_params.get("branch")
        if branch:
            queryset = queryset.filter(branch_id=branch)
        return _active(self, queryset)


class WarehouseViewSet(TenantModelViewSet):
    serializer_class = WarehouseSerializer
    audit_name = "warehouse"
    soft_delete = True
    permission_map = {**INVENTORY_READ, **INVENTORY_WRITE}
    search_fields = ["name", "code", "address"]
    ordering_fields = ["name", "code", "created_at"]

    def queryset_for_tenant(self, tenant):
        queryset = Warehouse.objects.filter(company=tenant).select_related("branch")
        branch = self.request.query_params.get("branch")
        if branch:
            queryset = queryset.filter(branch_id=branch)
        return _active(self, queryset)


class SupplierViewSet(TenantModelViewSet):
    serializer_class = SupplierSerializer
    audit_name = "supplier"
    soft_delete = True
    permission_map = {**INVENTORY_READ, **INVENTORY_WRITE}
    search_fields = ["name", "tax_identifier", "contact_name", "email", "phone"]
    ordering_fields = ["name", "created_at"]

    def queryset_for_tenant(self, tenant):
        return _active(self, Supplier.objects.filter(company=tenant))


class StockBalanceViewSet(TenantModelViewSet):
    serializer_class = StockBalanceSerializer
    http_method_names = ["get", "head", "options"]
    permission_map = {
        **INVENTORY_READ, "valuation": "inventory.read", "create": "inventory.read",
        "update": "inventory.read", "partial_update": "inventory.read", "destroy": "inventory.read",
    }
    search_fields = ["product__name", "product__sku", "warehouse__name"]
    ordering_fields = ["quantity", "average_cost", "updated_at", "product__name", "warehouse__name"]

    def queryset_for_tenant(self, tenant):
        queryset = (StockBalance.objects.filter(company=tenant)
                    .select_related("warehouse", "product"))
        warehouse = self.request.query_params.get("warehouse")
        if warehouse:
            queryset = queryset.filter(warehouse_id=warehouse)
        product = self.request.query_params.get("product")
        if product:
            queryset = queryset.filter(product_id=product)
        if self.request.query_params.get("below_reorder") in {"true", "1"}:
            queryset = queryset.filter(quantity__lte=F("product__reorder_point"))
        if self.request.query_params.get("positive") in {"true", "1"}:
            queryset = queryset.filter(quantity__gt=0)
        return queryset

    @action(detail=False, methods=["get"])
    def valuation(self, request):
        balances = self.filter_queryset(self.get_queryset())
        grouped = {}
        total_quantity = Decimal("0")
        total_value = Decimal("0")
        for balance in balances:
            total_quantity += balance.quantity
            total_value += balance.value
            row = grouped.setdefault(balance.warehouse_id, {
                "warehouse_id": str(balance.warehouse_id),
                "warehouse": balance.warehouse.name,
                "quantity": Decimal("0"),
                "value": Decimal("0"),
            })
            row["quantity"] += balance.quantity
            row["value"] += balance.value
        rows = [
            {**row, "quantity": f"{row['quantity']:.3f}", "value": f"{row['value']:.2f}"}
            for row in sorted(grouped.values(), key=lambda entry: entry["warehouse"])
        ]
        return Response({
            "warehouses": rows,
            "total_quantity": f"{total_quantity:.3f}",
            "total_value": f"{total_value:.2f}",
        })


class InventoryMovementViewSet(TenantModelViewSet):
    serializer_class = InventoryMovementSerializer
    http_method_names = ["get", "post", "head", "options"]
    permission_map = {
        "list": "inventory.read", "retrieve": "inventory.read", "create": "inventory.write",
        "update": "inventory.write", "partial_update": "inventory.write", "destroy": "inventory.write",
    }
    search_fields = ["product__name", "product__sku", "note", "reference_id"]
    ordering_fields = ["created_at", "quantity", "balance_after"]

    def get_serializer_class(self):
        if self.action == "create":
            return ManualMovementSerializer
        return InventoryMovementSerializer

    def queryset_for_tenant(self, tenant):
        queryset = InventoryMovement.objects.filter(company=tenant).select_related(
            "warehouse", "product", "actor",
        )
        params = self.request.query_params
        if params.get("warehouse"):
            queryset = queryset.filter(warehouse_id=params["warehouse"])
        if params.get("product"):
            queryset = queryset.filter(product_id=params["product"])
        if params.get("kind") in InventoryMovement.Kind.values:
            queryset = queryset.filter(kind=params["kind"])
        if params.get("direction") in InventoryMovement.Direction.values:
            queryset = queryset.filter(direction=params["direction"])
        if params.get("reference_type"):
            queryset = queryset.filter(reference_type=params["reference_type"])
        if params.get("reference_id"):
            queryset = queryset.filter(reference_id=params["reference_id"])
        return queryset

    def create(self, request, *args, **kwargs):
        serializer = ManualMovementSerializer(data=request.data, context=self.get_serializer_context())
        serializer.is_valid(raise_exception=True)
        movement = create_manual_movement(
            company=self.get_tenant(), actor=request.user, **serializer.validated_data,
        )
        return Response(InventoryMovementSerializer(movement).data, status=status.HTTP_201_CREATED)


class PurchaseOrderViewSet(TenantModelViewSet):
    serializer_class = PurchaseOrderSerializer
    audit_name = "purchase_order"
    http_method_names = ["get", "post", "patch", "head", "options"]
    permission_map = {
        **PURCHASE_READ, **PURCHASE_WRITE,
        "submit": "purchases.write", "receive": "purchases.write", "cancel": "purchases.write",
    }
    search_fields = ["number", "supplier__name", "notes"]
    ordering_fields = ["created_at", "expected_at", "ordered_at", "status", "number"]

    def get_serializer_class(self):
        if self.action in {"create", "partial_update"}:
            return PurchaseOrderWriteSerializer
        return PurchaseOrderSerializer

    def queryset_for_tenant(self, tenant):
        queryset = (PurchaseOrder.objects.filter(company=tenant)
                    .select_related("supplier", "warehouse", "created_by")
                    .prefetch_related("lines__product"))
        params = self.request.query_params
        if params.get("status") in PurchaseOrder.Status.values:
            queryset = queryset.filter(status=params["status"])
        if params.get("supplier"):
            queryset = queryset.filter(supplier_id=params["supplier"])
        if params.get("warehouse"):
            queryset = queryset.filter(warehouse_id=params["warehouse"])
        return queryset

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = create_purchase_order(
            company=self.get_tenant(), actor=request.user, **serializer.validated_data,
        )
        return Response(
            PurchaseOrderSerializer(order, context=self.get_serializer_context()).data,
            status=status.HTTP_201_CREATED,
        )

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        order = update_purchase_order(
            order=instance, actor=request.user, **serializer.validated_data,
        )
        return Response(PurchaseOrderSerializer(order, context=self.get_serializer_context()).data)

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        order = submit_purchase_order(order=self.get_object(), actor=request.user)
        return Response(PurchaseOrderSerializer(order, context=self.get_serializer_context()).data)

    @action(detail=True, methods=["post"])
    def receive(self, request, pk=None):
        order = receive_purchase_order(order=self.get_object(), actor=request.user)
        return Response(PurchaseOrderSerializer(order, context=self.get_serializer_context()).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        order = cancel_purchase_order(
            order=self.get_object(), actor=request.user, reason=_reason(request),
        )
        return Response(PurchaseOrderSerializer(order, context=self.get_serializer_context()).data)


class TransferViewSet(TenantModelViewSet):
    serializer_class = TransferSerializer
    audit_name = "transfer"
    http_method_names = ["get", "post", "head", "options"]
    permission_map = {
        **INVENTORY_READ, "create": "inventory.write",
        "ship": "inventory.write", "complete": "inventory.write", "cancel": "inventory.write",
        "update": "inventory.write", "partial_update": "inventory.write", "destroy": "inventory.write",
    }
    search_fields = ["number", "notes"]
    ordering_fields = ["created_at", "dispatched_at", "completed_at", "status", "number"]

    def get_serializer_class(self):
        if self.action == "create":
            return TransferWriteSerializer
        return TransferSerializer

    def queryset_for_tenant(self, tenant):
        queryset = (Transfer.objects.filter(company=tenant)
                    .select_related("from_warehouse", "to_warehouse", "created_by")
                    .prefetch_related("lines__product"))
        params = self.request.query_params
        if params.get("status") in Transfer.Status.values:
            queryset = queryset.filter(status=params["status"])
        if params.get("warehouse"):
            warehouse = params["warehouse"]
            queryset = queryset.filter(
                Q(from_warehouse_id=warehouse) | Q(to_warehouse_id=warehouse)
            )
        return queryset

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        transfer = create_transfer(
            company=self.get_tenant(), actor=request.user, **serializer.validated_data,
        )
        return Response(
            TransferSerializer(transfer, context=self.get_serializer_context()).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"], url_path="dispatch")
    def ship(self, request, pk=None):
        transfer = dispatch_transfer(transfer=self.get_object(), actor=request.user)
        return Response(TransferSerializer(transfer, context=self.get_serializer_context()).data)

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        transfer = complete_transfer(transfer=self.get_object(), actor=request.user)
        return Response(TransferSerializer(transfer, context=self.get_serializer_context()).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        transfer = cancel_transfer(
            transfer=self.get_object(), actor=request.user, reason=_reason(request),
        )
        return Response(TransferSerializer(transfer, context=self.get_serializer_context()).data)


class StocktakeViewSet(TenantModelViewSet):
    serializer_class = StocktakeSerializer
    audit_name = "stocktake"
    http_method_names = ["get", "post", "head", "options"]
    permission_map = {
        **INVENTORY_READ, "create": "inventory.write", "complete": "inventory.write",
        "cancel": "inventory.write", "update": "inventory.write",
        "partial_update": "inventory.write", "destroy": "inventory.write",
    }
    search_fields = ["number", "notes"]
    ordering_fields = ["created_at", "completed_at", "status", "number"]

    def get_serializer_class(self):
        if self.action == "create":
            return StocktakeWriteSerializer
        return StocktakeSerializer

    def queryset_for_tenant(self, tenant):
        queryset = (Stocktake.objects.filter(company=tenant)
                    .select_related("warehouse", "created_by")
                    .prefetch_related("lines__product"))
        params = self.request.query_params
        if params.get("status") in Stocktake.Status.values:
            queryset = queryset.filter(status=params["status"])
        if params.get("warehouse"):
            queryset = queryset.filter(warehouse_id=params["warehouse"])
        return queryset

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        stocktake = create_stocktake(
            company=self.get_tenant(), actor=request.user, **serializer.validated_data,
        )
        return Response(
            StocktakeSerializer(stocktake, context=self.get_serializer_context()).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        stocktake = complete_stocktake(stocktake=self.get_object(), actor=request.user)
        return Response(StocktakeSerializer(stocktake, context=self.get_serializer_context()).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        stocktake = cancel_stocktake(
            stocktake=self.get_object(), actor=request.user, reason=_reason(request),
        )
        return Response(StocktakeSerializer(stocktake, context=self.get_serializer_context()).data)
