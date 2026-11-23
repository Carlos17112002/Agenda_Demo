from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.audit.models import AuditEvent
from apps.identity.models import Membership, PermissionGrant
from apps.inventory.models import InventoryMovement, StockBalance
from apps.sales.models import PaymentRecord, Sale, SaleLine
from apps.tenancy.models import Branch

from .utils import SalesScenarioMixin


class SaleApiTests(SalesScenarioMixin, TestCase):
    def setUp(self):
        self.build_scenario()

    def test_create_sale_snapshots_lines_and_totals(self):
        response = self.create_sale()
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["status"], "draft")
        self.assertEqual(response.data["subtotal"], "19000.00")
        self.assertEqual(response.data["total"], "19000.00")
        self.assertEqual(response.data["balance"], "19000.00")
        descriptions = {line["description"] for line in response.data["lines"]}
        self.assertEqual(descriptions, {"Shampoo", "Corte"})
        self.assertEqual(response.data["customer_name"], "Ana Pérez")
        self.assertFalse(InventoryMovement.objects.filter(kind=InventoryMovement.Kind.SALE).exists())
        self.assertTrue(AuditEvent.objects.filter(action="sale.created").exists())

    def test_sale_with_products_requires_warehouse(self):
        response = self.create_sale(warehouse=None)
        self.assertEqual(response.status_code, 400)
        self.assertIn("warehouse", response.data)

    def test_complete_sale_charges_payments_and_stock(self):
        cash = self.open_cash(opening="5000").data
        sale = self.create_sale().data
        response = self.client.post(f"/api/v1/sales/{sale['id']}/complete/", {
            "payments": [
                {"method": "cash", "amount": "10000", "cash_session": cash["id"]},
                {"method": "transfer", "amount": "9000", "reference": "TRX-1"},
            ],
        }, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["status"], "completed")
        self.assertEqual(response.data["paid_total"], "19000.00")
        self.assertEqual(response.data["balance"], "0.00")
        self.assertIsNotNone(response.data["completed_at"])

        balance = StockBalance.objects.get(company=self.company, warehouse=self.warehouse,
                                           product=self.product)
        self.assertEqual(balance.quantity, Decimal("8"))
        movement = InventoryMovement.objects.get(kind=InventoryMovement.Kind.SALE)
        self.assertEqual(movement.reference_type, "sale")
        self.assertEqual(movement.reference_id, str(sale["id"]))
        self.assertEqual(movement.quantity, Decimal("2"))

        product_line = SaleLine.objects.get(sale_id=sale["id"], kind=SaleLine.Kind.PRODUCT)
        self.assertEqual(product_line.unit_cost, Decimal("1000"))
        service_line = SaleLine.objects.get(sale_id=sale["id"], kind=SaleLine.Kind.SERVICE)
        self.assertEqual(service_line.unit_cost, Decimal("0"))

        payments = self.client.get("/api/v1/payments/")
        self.assertEqual(payments.status_code, 200)
        self.assertEqual(len(payments.data["results"]), 2)

    def test_cash_payment_requires_open_session(self):
        sale = self.create_sale().data
        response = self.client.post(f"/api/v1/sales/{sale['id']}/complete/", {
            "payments": [{"method": "cash", "amount": "19000"}],
        }, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("payments", response.data)
        self.assertEqual(Sale.objects.get(pk=sale["id"]).status, Sale.Status.DRAFT)
        self.assertFalse(PaymentRecord.objects.exists())
        self.assertEqual(
            StockBalance.objects.get(company=self.company, warehouse=self.warehouse,
                                     product=self.product).quantity, Decimal("10"),
        )

    def test_payment_total_must_match_sale_total(self):
        sale = self.create_sale().data
        response = self.complete_transfer(sale["id"], "10000")
        self.assertEqual(response.status_code, 400)
        self.assertIn("payments", response.data)
        self.assertEqual(Sale.objects.get(pk=sale["id"]).status, Sale.Status.DRAFT)

    def test_complete_sale_is_idempotent(self):
        sale = self.create_sale().data
        first = self.complete_transfer(sale["id"], "19000")
        second = self.complete_transfer(sale["id"], "19000")
        self.assertEqual(first.status_code, 200, first.data)
        self.assertEqual(second.status_code, 200, second.data)
        self.assertEqual(PaymentRecord.objects.filter(sale_id=sale["id"]).count(), 1)
        self.assertEqual(InventoryMovement.objects.filter(
            kind=InventoryMovement.Kind.SALE).count(), 1)

    def test_insufficient_stock_leaves_sale_draft(self):
        sale = self.create_sale(lines=[
            {"product": str(self.product.id), "quantity": "99"},
            {"service": str(self.service.id), "quantity": "1"},
        ]).data
        response = self.complete_transfer(sale["id"], "213000")
        self.assertEqual(response.status_code, 409, response.data)
        self.assertEqual(Sale.objects.get(pk=sale["id"]).status, Sale.Status.DRAFT)
        self.assertFalse(PaymentRecord.objects.exists())
        self.assertEqual(InventoryMovement.objects.filter(
            kind=InventoryMovement.Kind.SALE).count(), 0)
        self.assertEqual(
            StockBalance.objects.get(company=self.company, warehouse=self.warehouse,
                                     product=self.product).quantity, Decimal("10"),
        )

    def test_cancel_completed_sale_restores_stock_and_refunds(self):
        sale = self.create_sale().data
        self.complete_transfer(sale["id"], "19000")
        response = self.client.post(f"/api/v1/sales/{sale['id']}/cancel/",
                                    {"reason": "Cliente devolvió"}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["status"], "canceled")
        self.assertEqual(response.data["canceled_reason"], "Cliente devolvió")
        self.assertEqual(
            StockBalance.objects.get(company=self.company, warehouse=self.warehouse,
                                     product=self.product).quantity, Decimal("10"),
        )
        self.assertEqual(PaymentRecord.objects.get(sale_id=sale["id"]).status,
                         PaymentRecord.Status.REFUNDED)
        self.assertTrue(InventoryMovement.objects.filter(
            kind=InventoryMovement.Kind.SALE_CANCEL).exists())

        again = self.client.post(f"/api/v1/sales/{sale['id']}/cancel/", {}, format="json")
        self.assertEqual(again.status_code, 200)
        self.assertEqual(InventoryMovement.objects.filter(
            kind=InventoryMovement.Kind.SALE_CANCEL).count(), 1)

    def test_cancel_cash_sale_with_closed_session_is_rejected(self):
        cash = self.open_cash(opening="5000").data
        sale = self.create_sale().data
        self.complete_cash(sale["id"], "19000", cash["id"])
        closed = self.client.post(f"/api/v1/cash-sessions/{cash['id']}/close/",
                                  {"closing_amount": "24000"}, format="json")
        self.assertEqual(closed.status_code, 200, closed.data)
        response = self.client.post(f"/api/v1/sales/{sale['id']}/cancel/", {}, format="json")
        self.assertEqual(response.status_code, 409, response.data)
        self.assertEqual(Sale.objects.get(pk=sale["id"]).status, Sale.Status.COMPLETED)

    def test_only_drafts_are_editable_and_lines_are_fixed(self):
        sale = self.create_sale().data
        updated = self.client.patch(f"/api/v1/sales/{sale['id']}/",
                                    {"discount": "1000", "notes": "Cortesía"}, format="json")
        self.assertEqual(updated.status_code, 200, updated.data)
        self.assertEqual(updated.data["total"], "18000.00")

        replaced = self.client.patch(f"/api/v1/sales/{sale['id']}/", {
            "lines": [{"service": str(self.service.id), "quantity": "1"}],
        }, format="json")
        self.assertEqual(replaced.status_code, 400)
        self.assertIn("lines", replaced.data)

        branch_change = self.client.patch(f"/api/v1/sales/{sale['id']}/", {
            "branch": str(self.branch.id),
        }, format="json")
        self.assertEqual(branch_change.status_code, 200)

        other_branch = Branch.objects.create(company=self.company, name="Sucursal 2", code="S2")
        moved = self.client.patch(f"/api/v1/sales/{sale['id']}/", {
            "branch": str(other_branch.id),
        }, format="json")
        self.assertEqual(moved.status_code, 400)
        self.assertIn("branch", moved.data)

        self.complete_transfer(sale["id"], "18000")
        rejected = self.client.patch(f"/api/v1/sales/{sale['id']}/",
                                     {"notes": "Tarde"}, format="json")
        self.assertEqual(rejected.status_code, 409, rejected.data)

    def test_fractional_quantity_rounds_line_total_to_cents(self):
        sale = self.create_sale(lines=[
            {"product": str(self.product.id), "quantity": "0.333", "unit_price": "2.99"},
        ]).data
        self.assertEqual(sale["subtotal"], "1.00")
        self.assertEqual(sale["total"], "1.00")
        response = self.complete_transfer(sale["id"], "1.00")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["status"], "completed")

    def test_service_only_sale_does_not_require_warehouse(self):
        sale = self.create_sale(lines=[
            {"service": str(self.service.id), "quantity": "1"},
        ], warehouse=None).data
        response = self.complete_transfer(sale["id"], "15000")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["status"], "completed")
        self.assertFalse(InventoryMovement.objects.filter(
            kind=InventoryMovement.Kind.SALE).exists())

    def test_sale_rejects_foreign_references(self):
        foreign = self.foreign_objects()
        # The branch is checked by tenant permission before the domain layer and fails closed.
        response = self.create_sale(branch=str(foreign["branch"].id))
        self.assertEqual(response.status_code, 403, response.data)
        for field, value in [
            ("customer", foreign["customer"]), ("warehouse", foreign["warehouse"]),
        ]:
            response = self.create_sale(**{field: str(value.id)})
            self.assertEqual(response.status_code, 400, (field, response.data))
        for line in [
            {"product": str(foreign["product"].id), "quantity": "1"},
            {"service": str(foreign["service"].id), "quantity": "1"},
        ]:
            response = self.create_sale(lines=[line])
            self.assertEqual(response.status_code, 400, response.data)

    def test_sales_are_isolated_by_tenant(self):
        foreign = self.foreign_objects()
        foreign_sale = Sale.objects.create(
            company=foreign["company"], branch=foreign["branch"], warehouse=foreign["warehouse"],
        )
        response = self.client.get("/api/v1/sales/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["results"], [])
        detail = self.client.get(f"/api/v1/sales/{foreign_sale.id}/")
        self.assertEqual(detail.status_code, 404)

    def test_sale_permissions(self):
        worker, _, _ = self.role_client(Membership.Role.WORKER, "worker-sales@example.com")
        self.assertEqual(worker.get("/api/v1/sales/").status_code, 403)
        self.assertEqual(worker.post("/api/v1/sales/", self.sale_payload(), format="json").status_code, 403)

        accounting, _, _ = self.role_client(Membership.Role.ACCOUNTING, "accounting-sales@example.com")
        self.assertEqual(accounting.get("/api/v1/sales/").status_code, 200)
        self.assertEqual(accounting.post("/api/v1/sales/", self.sale_payload(), format="json").status_code, 403)

        reception, membership, _ = self.role_client(Membership.Role.RECEPTION, "reception-sales@example.com")
        created = reception.post("/api/v1/sales/", self.sale_payload(), format="json")
        self.assertEqual(created.status_code, 201, created.data)

        PermissionGrant.objects.create(
            membership=membership, permission="sales.write", effect="deny",
        )
        denied = reception.post("/api/v1/sales/", self.sale_payload(), format="json")
        self.assertEqual(denied.status_code, 403)

    def test_complete_with_foreign_cash_session_is_rejected(self):
        foreign = self.foreign_objects()
        from apps.sales.models import CashSession
        foreign_session = CashSession.objects.create(
            company=foreign["company"], branch=foreign["branch"],
        )
        sale = self.create_sale().data
        response = self.client.post(f"/api/v1/sales/{sale['id']}/complete/", {
            "payments": [{
                "method": "cash", "amount": "19000", "cash_session": str(foreign_session.id),
            }],
        }, format="json")
        self.assertEqual(response.status_code, 400, response.data)
        self.assertEqual(Sale.objects.get(pk=sale["id"]).status, Sale.Status.DRAFT)

    def test_sale_filters(self):
        sale = self.create_sale().data
        self.complete_transfer(sale["id"], "19000")
        today = timezone.localdate().isoformat()
        response = self.client.get(
            f"/api/v1/sales/?status=completed&branch={self.branch.id}&date_from={today}&date_to={today}"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row["number"] for row in response.data["results"]],
                         [Sale.objects.get(pk=sale["id"]).number])
