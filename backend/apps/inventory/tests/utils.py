from decimal import Decimal

from apps.identity.models import Membership
from apps.inventory.models import Category, Product, Supplier, Warehouse
from apps.tenancy.models import Branch
from apps.tenancy.tests.utils import (
    make_company, make_context, make_membership, make_user, tenant_client,
)


class InventoryScenarioMixin:
    def build_scenario(self, slug="inventario-a"):
        self.company = make_company(slug, "Inventario A")
        self.owner = make_user(f"owner-{slug}@example.com")
        make_membership(self.owner, self.company, Membership.Role.OWNER)
        self.client = tenant_client(self.owner, make_context(self.owner, self.company))
        self.branch = Branch.objects.create(company=self.company, name="Centro", code="CENTRO")
        self.category = Category.objects.create(company=self.company, name="Cuidado")
        self.product = Product.objects.create(
            company=self.company, sku="SKU-1", name="Shampoo", category=self.category,
            cost=Decimal("1000"), price=Decimal("2000"), reorder_point=Decimal("5"),
        )
        self.product2 = Product.objects.create(
            company=self.company, sku="SKU-2", name="Acondicionador",
            cost=Decimal("800"), price=Decimal("1600"), reorder_point=Decimal("2"),
        )
        self.warehouse = Warehouse.objects.create(
            company=self.company, branch=self.branch, name="Central", code="CENTRAL",
        )
        self.warehouse2 = Warehouse.objects.create(
            company=self.company, name="Anexo", code="ANEXO",
        )
        self.supplier = Supplier.objects.create(
            company=self.company, name="Distribuidora Sur", email="ventas@sur.example.com",
        )

    def role_client(self, role, email):
        user = make_user(email)
        membership = make_membership(user, self.company, role)
        return tenant_client(user, make_context(user, self.company)), membership, user

    def foreign_objects(self, slug="inventario-b"):
        company = make_company(slug, "Inventario B")
        branch = Branch.objects.create(company=company, name="Norte", code="NORTE")
        warehouse = Warehouse.objects.create(company=company, name="Bodega B", code="B")
        product = Product.objects.create(company=company, sku="B-1", name="Producto B")
        supplier = Supplier.objects.create(company=company, name="Proveedor B")
        return {
            "company": company, "branch": branch, "warehouse": warehouse,
            "product": product, "supplier": supplier,
        }

    def entry(self, quantity="10", cost="1000", product=None, warehouse=None, client=None):
        payload = {
            "warehouse": str((warehouse or self.warehouse).id),
            "product": str((product or self.product).id),
            "kind": "entry",
            "quantity": str(quantity),
        }
        if cost is not None:
            payload["unit_cost"] = str(cost)
        return (client or self.client).post("/api/v1/inventory/movements/", payload, format="json")

    def exit_stock(self, quantity="1", product=None, warehouse=None, client=None):
        return (client or self.client).post("/api/v1/inventory/movements/", {
            "warehouse": str((warehouse or self.warehouse).id),
            "product": str((product or self.product).id),
            "kind": "exit",
            "quantity": str(quantity),
        }, format="json")

    def purchase_payload(self, lines=None, **overrides):
        payload = {
            "supplier": str(self.supplier.id),
            "warehouse": str(self.warehouse.id),
            "lines": lines if lines is not None else [
                {"product": str(self.product.id), "quantity": "5", "unit_cost": "1000"},
                {"product": str(self.product2.id), "quantity": "2", "unit_cost": "500"},
            ],
        }
        payload.update(overrides)
        return payload

    def transfer_payload(self, lines=None, **overrides):
        payload = {
            "from_warehouse": str(self.warehouse.id),
            "to_warehouse": str(self.warehouse2.id),
            "lines": lines if lines is not None else [{"product": str(self.product.id), "quantity": "4"}],
        }
        payload.update(overrides)
        return payload

    def stocktake_payload(self, lines=None, **overrides):
        payload = {
            "warehouse": str(self.warehouse.id),
            "lines": lines if lines is not None else [
                {"product": str(self.product.id), "counted_quantity": "7"},
                {"product": str(self.product2.id), "counted_quantity": "3"},
            ],
        }
        payload.update(overrides)
        return payload
