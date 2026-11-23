from decimal import Decimal

from apps.catalog.models import Service
from apps.customers.models import Customer
from apps.identity.models import Membership
from apps.inventory.models import Product, Warehouse
from apps.tenancy.models import Branch
from apps.tenancy.tests.utils import (
    make_company, make_context, make_membership, make_user, tenant_client,
)


class SalesScenarioMixin:
    def build_scenario(self, slug="comercial-a"):
        self.company = make_company(slug, "Comercial A")
        self.owner = make_user(f"owner-{slug}@example.com")
        make_membership(self.owner, self.company, Membership.Role.OWNER)
        self.client = tenant_client(self.owner, make_context(self.owner, self.company))

        self.branch = Branch.objects.create(
            company=self.company, name="Centro", code="CENTRO", timezone="America/Santiago",
        )
        self.warehouse = Warehouse.objects.create(
            company=self.company, branch=self.branch, name="Central", code="CENTRAL",
        )
        self.customer = Customer.objects.create(
            company=self.company, first_name="Ana", last_name="Pérez",
            email="ana@example.com",
        )
        self.product = Product.objects.create(
            company=self.company, sku="SKU-1", name="Shampoo",
            cost=Decimal("1000"), price=Decimal("2000"),
        )
        self.product2 = Product.objects.create(
            company=self.company, sku="SKU-2", name="Acondicionador",
            cost=Decimal("800"), price=Decimal("1600"),
        )
        self.service = Service.objects.create(
            company=self.company, name="Corte", price=Decimal("15000"),
        )
        self.entry(self.product, "10", "1000")
        self.entry(self.product2, "5", "800")

    def role_client(self, role, email):
        user = make_user(email)
        membership = make_membership(user, self.company, role)
        return tenant_client(user, make_context(user, self.company)), membership, user

    def entry(self, product, quantity, cost):
        response = self.client.post("/api/v1/inventory/movements/", {
            "warehouse": str(self.warehouse.id),
            "product": str(product.id),
            "kind": "entry",
            "quantity": quantity,
            "unit_cost": cost,
        }, format="json")
        assert response.status_code == 201, response.data
        return response

    def sale_payload(self, lines=None, **overrides):
        payload = {
            "branch": str(self.branch.id),
            "customer": str(self.customer.id),
            "warehouse": str(self.warehouse.id),
            "lines": lines if lines is not None else [
                {"product": str(self.product.id), "quantity": "2"},
                {"service": str(self.service.id), "quantity": "1"},
            ],
        }
        payload.update(overrides)
        return payload

    def create_sale(self, lines=None, client=None, **overrides):
        return (client or self.client).post(
            "/api/v1/sales/", self.sale_payload(lines=lines, **overrides), format="json",
        )

    def open_cash(self, opening="5000", client=None, branch=None):
        return (client or self.client).post("/api/v1/cash-sessions/", {
            "branch": str((branch or self.branch).id),
            "opening_amount": opening,
        }, format="json")

    def complete_cash(self, sale_id, amount, cash_session_id, client=None):
        return (client or self.client).post(f"/api/v1/sales/{sale_id}/complete/", {
            "payments": [{
                "method": "cash", "amount": amount, "cash_session": str(cash_session_id),
            }],
        }, format="json")

    def complete_transfer(self, sale_id, amount, client=None):
        return (client or self.client).post(f"/api/v1/sales/{sale_id}/complete/", {
            "payments": [{"method": "transfer", "amount": amount}],
        }, format="json")

    def foreign_objects(self, slug="comercial-b"):
        company = make_company(slug, "Comercial B")
        branch = Branch.objects.create(company=company, name="Norte", code="NORTE")
        warehouse = Warehouse.objects.create(company=company, branch=branch, name="B", code="B")
        customer = Customer.objects.create(company=company, first_name="Beto")
        product = Product.objects.create(company=company, sku="B-1", name="Producto B", price=Decimal("100"))
        service = Service.objects.create(company=company, name="Servicio B", price=Decimal("200"))
        return {
            "company": company, "branch": branch, "warehouse": warehouse,
            "customer": customer, "product": product, "service": service,
        }
