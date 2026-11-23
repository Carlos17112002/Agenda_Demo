from dataclasses import dataclass

from apps.bookings.models import Booking
from apps.bookings.serializers import BookingSerializer
from apps.catalog.models import Service
from apps.catalog.serializers import ServiceSerializer
from apps.customers.models import Customer
from apps.customers.serializers import CustomerSerializer
from apps.inventory.models import (
    Category, Document, InventoryMovement, Product, StockBalance, Supplier, Warehouse,
)
from apps.inventory.serializers import (
    CategorySerializer, DocumentSerializer, InventoryMovementSerializer,
    ProductSerializer, StockBalanceSerializer, SupplierSerializer, WarehouseSerializer,
)
from apps.tenancy.models import Branch
from apps.tenancy.serializers import BranchSerializer
from apps.workforce.models import WorkerProfile
from apps.workforce.serializers import WorkerProfileSerializer


@dataclass(frozen=True)
class SyncResource:
    model: type
    serializer: type
    permissions: tuple
    feature: str = None
    cursor_field: str = "updated_at"
    select_related: tuple = ()
    prefetch_related: tuple = ()


SYNC_REGISTRY = {
    "branches": SyncResource(
        Branch, BranchSerializer, ("branches.read",),
    ),
    "services": SyncResource(
        Service, ServiceSerializer, ("catalog.read",), feature="catalog",
        prefetch_related=("branches",),
    ),
    "workers": SyncResource(
        WorkerProfile, WorkerProfileSerializer, ("workforce.read",),
        feature="workforce", prefetch_related=("branches",),
    ),
    "customers": SyncResource(
        Customer, CustomerSerializer, ("customers.read",), feature="customers",
    ),
    "bookings": SyncResource(
        Booking, BookingSerializer, ("bookings.read", "bookings.own.read"),
        feature="bookings",
        select_related=("branch", "customer", "service", "worker"),
    ),
    "products": SyncResource(
        Product, ProductSerializer, ("inventory.read",), feature="inventory",
        select_related=("category",),
    ),
    "categories": SyncResource(
        Category, CategorySerializer, ("inventory.read",), feature="inventory",
    ),
    "suppliers": SyncResource(
        Supplier, SupplierSerializer, ("inventory.read",), feature="inventory",
    ),
    "documents": SyncResource(
        Document, DocumentSerializer, ("inventory.read",), feature="inventory",
        select_related=("product", "uploaded_by"),
    ),
    "warehouses": SyncResource(
        Warehouse, WarehouseSerializer, ("inventory.read",), feature="inventory",
        select_related=("branch",),
    ),
    "stock": SyncResource(
        StockBalance, StockBalanceSerializer, ("inventory.read",), feature="inventory",
        select_related=("warehouse", "product"),
    ),
    "movements": SyncResource(
        InventoryMovement, InventoryMovementSerializer, ("inventory.read",),
        feature="inventory", cursor_field="created_at",
        select_related=("warehouse", "product", "actor"),
    ),
}
