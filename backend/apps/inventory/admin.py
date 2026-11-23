from django.contrib import admin

from apps.tenancy.admin import TenantScopedAdmin

from .models import (
    Category, Document, InventoryMovement, Product, PurchaseLine, PurchaseOrder, StockBalance,
    Stocktake, StocktakeLine, Supplier, Transfer, TransferLine, Warehouse,
)


@admin.register(Category)
class CategoryAdmin(TenantScopedAdmin):
    list_display = ("name", "company", "active")
    list_filter = ("active", "company")
    search_fields = ("name",)


@admin.register(Product)
class ProductAdmin(TenantScopedAdmin):
    list_display = ("sku", "name", "kind", "category", "unit", "cost", "price", "reorder_point", "active", "company")
    list_filter = ("kind", "active", "company", "category", "unit")
    search_fields = ("sku", "name", "barcode", "serial_number", "internal_code")


@admin.register(Document)
class DocumentAdmin(TenantScopedAdmin):
    list_display = ("name", "original_name", "content_type", "size", "product", "company")
    list_filter = ("company", "content_type")
    search_fields = ("name", "original_name")
    readonly_fields = ("size", "created_at", "updated_at")


@admin.register(Warehouse)
class WarehouseAdmin(TenantScopedAdmin):
    list_display = ("name", "code", "branch", "active", "company")
    list_filter = ("active", "company", "branch")
    search_fields = ("name", "code", "address")


@admin.register(Supplier)
class SupplierAdmin(TenantScopedAdmin):
    list_display = ("name", "tax_identifier", "contact_name", "email", "active", "company")
    list_filter = ("active", "company")
    search_fields = ("name", "tax_identifier", "contact_name", "email")


@admin.register(StockBalance)
class StockBalanceAdmin(TenantScopedAdmin):
    list_display = ("warehouse", "product", "quantity", "average_cost", "company")
    list_filter = ("company", "warehouse")
    search_fields = ("product__sku", "product__name", "warehouse__name")
    readonly_fields = [field.name for field in StockBalance._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(InventoryMovement)
class InventoryMovementAdmin(TenantScopedAdmin):
    list_display = ("created_at", "kind", "direction", "quantity", "product", "warehouse", "balance_after", "company")
    list_filter = ("kind", "direction", "company", "warehouse")
    search_fields = ("product__sku", "product__name", "reference_id", "note")
    date_hierarchy = "created_at"
    readonly_fields = [field.name for field in InventoryMovement._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class PurchaseLineInline(admin.TabularInline):
    model = PurchaseLine
    extra = 0
    readonly_fields = ("product", "quantity", "unit_cost", "created_at", "updated_at")
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(TenantScopedAdmin):
    list_display = ("number", "supplier", "warehouse", "status", "expected_at", "received_at", "company")
    list_filter = ("status", "company", "warehouse", "supplier")
    search_fields = ("number", "supplier__name", "notes")
    readonly_fields = [field.name for field in PurchaseOrder._meta.fields]
    inlines = [PurchaseLineInline]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class TransferLineInline(admin.TabularInline):
    model = TransferLine
    extra = 0
    readonly_fields = ("product", "quantity", "unit_cost", "created_at", "updated_at")
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Transfer)
class TransferAdmin(TenantScopedAdmin):
    list_display = ("number", "from_warehouse", "to_warehouse", "status", "dispatched_at", "completed_at", "company")
    list_filter = ("status", "company", "from_warehouse", "to_warehouse")
    search_fields = ("number", "notes")
    readonly_fields = [field.name for field in Transfer._meta.fields]
    inlines = [TransferLineInline]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class StocktakeLineInline(admin.TabularInline):
    model = StocktakeLine
    extra = 0
    readonly_fields = ("product", "counted_quantity", "expected_quantity", "difference", "created_at", "updated_at")
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Stocktake)
class StocktakeAdmin(TenantScopedAdmin):
    list_display = ("number", "warehouse", "status", "completed_at", "company")
    list_filter = ("status", "company", "warehouse")
    search_fields = ("number", "notes")
    readonly_fields = [field.name for field in Stocktake._meta.fields]
    inlines = [StocktakeLineInline]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
