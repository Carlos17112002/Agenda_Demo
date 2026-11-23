from decimal import Decimal

from rest_framework import status
from rest_framework.test import APITestCase

from apps.audit.models import AuditEvent
from apps.identity.models import Membership, PermissionGrant
from apps.inventory.models import (
    InventoryMovement, Product, PurchaseLine, PurchaseOrder, StockBalance, Supplier, Warehouse,
)
from .utils import InventoryScenarioMixin


class InventoryCatalogTests(InventoryScenarioMixin, APITestCase):
    def setUp(self):
        self.build_scenario()

    def test_product_company_category_and_sku_validation(self):
        response = self.client.post("/api/v1/inventory/products/", {
            "sku": "SKU-9", "name": "Jabón", "company": str(self.company.id),
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("company", response.data)

        foreign = self.foreign_objects()
        foreign_category = self.category.__class__.objects.create(company=foreign["company"], name="Externa")
        response = self.client.post("/api/v1/inventory/products/", {
            "sku": "SKU-9", "name": "Jabón", "category": str(foreign_category.id),
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        response = self.client.post("/api/v1/inventory/products/", {
            "sku": "SKU-9", "name": "Jabón", "category": str(self.category.id),
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(str(response.data["company"]), str(self.company.id))

        duplicate = self.client.post("/api/v1/inventory/products/", {
            "sku": "SKU-9", "name": "Otro",
        }, format="json")
        self.assertEqual(duplicate.status_code, status.HTTP_400_BAD_REQUEST)

    def test_product_soft_delete_and_tenant_listing(self):
        foreign = self.foreign_objects()
        response = self.client.get("/api/v1/inventory/products/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = {row["id"] for row in response.data["results"]}
        self.assertNotIn(str(foreign["product"].id), ids)

        response = self.client.delete(f"/api/v1/inventory/products/{self.product.id}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.product.refresh_from_db()
        self.assertFalse(self.product.active)
        response = self.client.get("/api/v1/inventory/products/", {"active": "true"})
        ids = {row["id"] for row in response.data["results"]}
        self.assertNotIn(str(self.product.id), ids)

    def test_warehouse_branch_and_supplier_validation(self):
        foreign = self.foreign_objects()
        response = self.client.post("/api/v1/inventory/warehouses/", {
            "name": "Externa", "code": "EXT", "branch": str(foreign["branch"].id),
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        response = self.client.post("/api/v1/inventory/suppliers/", {
            "name": "Nuevo proveedor", "email": "compras@example.com",
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        supplier = Supplier.objects.get(pk=response.data["id"])
        self.assertEqual(supplier.company, self.company)

        response = self.client.delete(f"/api/v1/inventory/suppliers/{supplier.id}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        supplier.refresh_from_db()
        self.assertFalse(supplier.active)


class InventoryLedgerTests(InventoryScenarioMixin, APITestCase):
    def setUp(self):
        self.build_scenario()

    def test_manual_movements_weighted_average_and_valuation(self):
        response = self.entry(quantity="10", cost="1000")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["direction"], "in")
        self.assertEqual(response.data["balance_after"], "10.000")

        response = self.entry(quantity="10", cost="2000")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        stock = self.client.get("/api/v1/inventory/stock/", {"warehouse": str(self.warehouse.id)})
        self.assertEqual(stock.status_code, status.HTTP_200_OK)
        row = stock.data["results"][0]
        self.assertEqual(row["quantity"], "20.000")
        self.assertEqual(row["average_cost"], "1500.0000")
        self.assertEqual(row["value"], "30000.0000")

        response = self.exit_stock(quantity="5")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["direction"], "out")
        self.assertEqual(response.data["unit_cost"], "1500.0000")
        self.assertEqual(response.data["balance_after"], "15.000")

        valuation = self.client.get("/api/v1/inventory/stock/valuation/")
        self.assertEqual(valuation.status_code, status.HTTP_200_OK)
        self.assertEqual(valuation.data["total_quantity"], "15.000")
        self.assertEqual(valuation.data["total_value"], "22500.00")
        self.assertEqual(valuation.data["warehouses"][0]["warehouse"], "Central")

        movements = self.client.get("/api/v1/inventory/movements/")
        self.assertEqual(len(movements.data["results"]), 3)
        movement_id = movements.data["results"][0]["id"]
        self.assertEqual(self.client.patch(
            f"/api/v1/inventory/movements/{movement_id}/", {"note": "cambio"}, format="json",
        ).status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertEqual(self.client.delete(
            f"/api/v1/inventory/movements/{movement_id}/",
        ).status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

        response = self.exit_stock(quantity="100")
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(
            self.client.get("/api/v1/inventory/movements/").data["count"], 3,
        )

        self.assertEqual(AuditEvent.objects.filter(action="inventory.entry").count(), 2)
        self.assertEqual(AuditEvent.objects.filter(action="inventory.exit").count(), 1)

    def test_manual_movement_validation(self):
        response = self.entry(quantity="0")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response = self.client.post("/api/v1/inventory/movements/", {
            "warehouse": str(self.warehouse.id), "product": str(self.product.id),
            "kind": "purchase_receipt", "quantity": "1",
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class PurchaseOrderTests(InventoryScenarioMixin, APITestCase):
    def setUp(self):
        self.build_scenario()

    def _create(self, **overrides):
        return self.client.post(
            "/api/v1/purchases/", self.purchase_payload(**overrides), format="json",
        )

    def test_purchase_flow_receive_is_idempotent(self):
        response = self._create()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], "draft")
        self.assertEqual(response.data["total"], "6000.0000")
        self.assertEqual(len(response.data["lines"]), 2)
        order_id = response.data["id"]

        response = self.client.post(f"/api/v1/purchases/{order_id}/submit/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "ordered")

        response = self.client.post(f"/api/v1/purchases/{order_id}/receive/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "received")

        stock = self.client.get("/api/v1/inventory/stock/", {"warehouse": str(self.warehouse.id)})
        rows = {row["product_sku"]: row for row in stock.data["results"]}
        self.assertEqual(rows["SKU-1"]["quantity"], "5.000")
        self.assertEqual(rows["SKU-1"]["average_cost"], "1000.0000")
        self.assertEqual(rows["SKU-2"]["quantity"], "2.000")
        self.assertEqual(rows["SKU-2"]["average_cost"], "500.0000")
        self.product2.refresh_from_db()
        self.assertEqual(self.product2.cost, Decimal("500.0000"))

        response = self.client.post(f"/api/v1/purchases/{order_id}/receive/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        stock = self.client.get("/api/v1/inventory/stock/", {"warehouse": str(self.warehouse.id)})
        rows = {row["product_sku"]: row for row in stock.data["results"]}
        self.assertEqual(rows["SKU-1"]["quantity"], "5.000")

        response = self.client.post(f"/api/v1/purchases/{order_id}/cancel/")
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertTrue(AuditEvent.objects.filter(action="purchase_order.received").exists())

    def test_purchase_cancel_draft_and_edit_only_draft(self):
        response = self._create()
        order_id = response.data["id"]

        response = self.client.patch(f"/api/v1/purchases/{order_id}/", {"notes": "Urgente"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["notes"], "Urgente")

        response = self.client.patch(f"/api/v1/purchases/{order_id}/", {
            "lines": [{"product": str(self.product.id), "quantity": "1", "unit_cost": "1"}],
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        self.client.post(f"/api/v1/purchases/{order_id}/submit/")
        response = self.client.patch(f"/api/v1/purchases/{order_id}/", {"notes": "Tarde"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

        response = self._create()
        draft_id = response.data["id"]
        response = self.client.post(f"/api/v1/purchases/{draft_id}/cancel/", {"reason": "Duplicada"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "canceled")
        self.assertEqual(StockBalance.objects.filter(company=self.company).count(), 0)

    def test_purchase_validation_and_cross_tenant_rejection(self):
        response = self.client.post("/api/v1/purchases/", self.purchase_payload(lines=[]), format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        duplicated = [
            {"product": str(self.product.id), "quantity": "1", "unit_cost": "1"},
            {"product": str(self.product.id), "quantity": "2", "unit_cost": "1"},
        ]
        response = self.client.post("/api/v1/purchases/", self.purchase_payload(lines=duplicated), format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        response = self.client.post("/api/v1/purchases/", self.purchase_payload(lines=[
            {"product": str(self.product.id), "quantity": "0", "unit_cost": "1"},
        ]), format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        foreign = self.foreign_objects()
        response = self.client.post("/api/v1/purchases/", self.purchase_payload(
            supplier=str(foreign["supplier"].id),
        ), format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response = self.client.post("/api/v1/purchases/", self.purchase_payload(
            warehouse=str(foreign["warehouse"].id),
        ), format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response = self.client.post("/api/v1/purchases/", self.purchase_payload(lines=[
            {"product": str(foreign["product"].id), "quantity": "1", "unit_cost": "1"},
        ]), format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        response = self._create(company=str(self.company.id))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        response = self._create()
        response = self.client.post(f"/api/v1/purchases/{response.data['id']}/receive/")
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)


class TransferTests(InventoryScenarioMixin, APITestCase):
    def setUp(self):
        self.build_scenario()
        self.entry(quantity="10", cost="1000")

    def _create(self, **overrides):
        return self.client.post(
            "/api/v1/inventory/transfers/", self.transfer_payload(**overrides), format="json",
        )

    def test_transfer_dispatch_complete_and_idempotency(self):
        response = self._create()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], "draft")
        transfer_id = response.data["id"]

        response = self.client.post(f"/api/v1/inventory/transfers/{transfer_id}/dispatch/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "in_transit")
        self.assertEqual(response.data["lines"][0]["unit_cost"], "1000.0000")
        stock = self.client.get("/api/v1/inventory/stock/", {"warehouse": str(self.warehouse.id)})
        self.assertEqual(stock.data["results"][0]["quantity"], "6.000")

        response = self.client.post(f"/api/v1/inventory/transfers/{transfer_id}/complete/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "completed")
        stock = self.client.get("/api/v1/inventory/stock/", {"warehouse": str(self.warehouse2.id)})
        self.assertEqual(stock.data["results"][0]["quantity"], "4.000")
        self.assertEqual(stock.data["results"][0]["average_cost"], "1000.0000")

        response = self.client.post(f"/api/v1/inventory/transfers/{transfer_id}/complete/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        stock = self.client.get("/api/v1/inventory/stock/", {"warehouse": str(self.warehouse2.id)})
        self.assertEqual(stock.data["results"][0]["quantity"], "4.000")

        valuation = self.client.get("/api/v1/inventory/stock/valuation/")
        self.assertEqual(valuation.data["total_quantity"], "10.000")
        self.assertEqual(valuation.data["total_value"], "10000.00")
        response = self.client.post(f"/api/v1/inventory/transfers/{transfer_id}/cancel/")
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertTrue(AuditEvent.objects.filter(action="transfer.completed").exists())

    def test_transfer_insufficient_stock_and_cancel_in_transit(self):
        response = self._create(lines=[{"product": str(self.product.id), "quantity": "100"}])
        transfer_id = response.data["id"]
        response = self.client.post(f"/api/v1/inventory/transfers/{transfer_id}/dispatch/")
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(
            self.client.get(f"/api/v1/inventory/transfers/{transfer_id}/").data["status"], "draft",
        )
        stock = self.client.get("/api/v1/inventory/stock/", {"warehouse": str(self.warehouse.id)})
        self.assertEqual(stock.data["results"][0]["quantity"], "10.000")
        self.client.post(f"/api/v1/inventory/transfers/{transfer_id}/cancel/")

        response = self._create(lines=[{"product": str(self.product.id), "quantity": "3"}])
        transfer_id = response.data["id"]
        self.client.post(f"/api/v1/inventory/transfers/{transfer_id}/dispatch/")
        stock = self.client.get("/api/v1/inventory/stock/", {"warehouse": str(self.warehouse.id)})
        self.assertEqual(stock.data["results"][0]["quantity"], "7.000")
        response = self.client.post(f"/api/v1/inventory/transfers/{transfer_id}/cancel/", {"reason": "Error"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "canceled")
        stock = self.client.get("/api/v1/inventory/stock/", {"warehouse": str(self.warehouse.id)})
        self.assertEqual(stock.data["results"][0]["quantity"], "10.000")
        stock = self.client.get("/api/v1/inventory/stock/", {"warehouse": str(self.warehouse2.id)})
        self.assertEqual(stock.data["count"], 0)

    def test_transfer_validation(self):
        response = self.client.post("/api/v1/inventory/transfers/", self.transfer_payload(
            to_warehouse=str(self.warehouse.id),
        ), format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        foreign = self.foreign_objects()
        response = self.client.post("/api/v1/inventory/transfers/", self.transfer_payload(
            to_warehouse=str(foreign["warehouse"].id),
        ), format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        response = self.client.post("/api/v1/inventory/transfers/", self.transfer_payload(
            lines=[{"product": str(self.product.id), "quantity": "0"}],
        ), format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class StocktakeTests(InventoryScenarioMixin, APITestCase):
    def setUp(self):
        self.build_scenario()
        self.entry(quantity="10", cost="1000")

    def _create(self, **overrides):
        return self.client.post(
            "/api/v1/inventory/stocktakes/", self.stocktake_payload(**overrides), format="json",
        )

    def test_stocktake_reconciles_differences_once(self):
        response = self._create()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        stocktake_id = response.data["id"]

        response = self.client.post(f"/api/v1/inventory/stocktakes/{stocktake_id}/complete/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "completed")
        rows = {line["product_sku"]: line for line in response.data["lines"]}
        self.assertEqual(rows["SKU-1"]["expected_quantity"], "10.000")
        self.assertEqual(rows["SKU-1"]["difference"], "-3.000")
        self.assertEqual(rows["SKU-2"]["expected_quantity"], "0.000")
        self.assertEqual(rows["SKU-2"]["difference"], "3.000")

        stock = self.client.get("/api/v1/inventory/stock/", {"warehouse": str(self.warehouse.id)})
        rows = {row["product_sku"]: row for row in stock.data["results"]}
        self.assertEqual(rows["SKU-1"]["quantity"], "7.000")
        self.assertEqual(rows["SKU-2"]["quantity"], "3.000")
        movements = self.client.get("/api/v1/inventory/movements/", {"kind": "stocktake"})
        self.assertEqual(movements.data["count"], 2)

        response = self.client.post(f"/api/v1/inventory/stocktakes/{stocktake_id}/complete/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            self.client.get("/api/v1/inventory/movements/", {"kind": "stocktake"}).data["count"], 2,
        )
        response = self.client.post(f"/api/v1/inventory/stocktakes/{stocktake_id}/cancel/")
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertTrue(AuditEvent.objects.filter(action="stocktake.completed").exists())

    def test_stocktake_without_differences_and_validation(self):
        response = self._create(lines=[{"product": str(self.product.id), "counted_quantity": "10"}])
        stocktake_id = response.data["id"]
        response = self.client.post(f"/api/v1/inventory/stocktakes/{stocktake_id}/complete/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            self.client.get("/api/v1/inventory/movements/", {"kind": "stocktake"}).data["count"], 0,
        )

        duplicated = [
            {"product": str(self.product.id), "counted_quantity": "1"},
            {"product": str(self.product.id), "counted_quantity": "2"},
        ]
        response = self._create(lines=duplicated)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response = self._create(lines=[{"product": str(self.product.id), "counted_quantity": "-1"}])
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class StockFiltersTests(InventoryScenarioMixin, APITestCase):
    def setUp(self):
        self.build_scenario()
        self.entry(quantity="3", cost="1000")
        self.entry(quantity="5", cost="400", product=self.product2)

    def test_low_stock_search_and_valuation_filters(self):
        response = self.client.get("/api/v1/inventory/stock/", {"below_reorder": "true"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([row["product_sku"] for row in response.data["results"]], ["SKU-1"])

        response = self.client.get("/api/v1/inventory/stock/", {"search": "Acondicionador"})
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["product_sku"], "SKU-2")

        response = self.client.get("/api/v1/inventory/stock/valuation/", {"warehouse": str(self.warehouse.id)})
        self.assertEqual(response.data["total_quantity"], "8.000")
        self.assertEqual(response.data["total_value"], "5000.00")

        self.assertEqual(
            self.client.post("/api/v1/inventory/stock/", {}, format="json").status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def test_positive_filter_excludes_zero_balance(self):
        response = self.client.post("/api/v1/inventory/stocktakes/", self.stocktake_payload(
            lines=[{"product": str(self.product.id), "counted_quantity": "0"}],
        ), format="json")
        stocktake_id = response.data["id"]
        self.client.post(f"/api/v1/inventory/stocktakes/{stocktake_id}/complete/")
        response = self.client.get("/api/v1/inventory/stock/", {"positive": "true"})
        self.assertEqual([row["product_sku"] for row in response.data["results"]], ["SKU-2"])


class InventoryPermissionTests(InventoryScenarioMixin, APITestCase):
    def setUp(self):
        self.build_scenario()

    def test_inventory_and_accounting_roles(self):
        inventory_client, _, _ = self.role_client(Membership.Role.INVENTORY, "inventario@example.com")
        self.assertEqual(inventory_client.get("/api/v1/inventory/products/").status_code, 200)
        self.assertEqual(self.entry(client=inventory_client).status_code, 201)
        self.assertEqual(inventory_client.get("/api/v1/purchases/").status_code, 200)
        response = inventory_client.post("/api/v1/purchases/", self.purchase_payload(), format="json")
        self.assertEqual(response.status_code, 201)

        accounting_client, _, _ = self.role_client(Membership.Role.ACCOUNTING, "contabilidad@example.com")
        self.assertEqual(accounting_client.get("/api/v1/inventory/stock/").status_code, 200)
        self.assertEqual(self.entry(client=accounting_client).status_code, 403)
        self.assertEqual(accounting_client.get("/api/v1/purchases/").status_code, 403)

        reception_client, _, _ = self.role_client(Membership.Role.RECEPTION, "recepcion@example.com")
        self.assertEqual(reception_client.get("/api/v1/inventory/products/").status_code, 403)
        self.assertEqual(reception_client.get("/api/v1/inventory/stock/").status_code, 403)

    def test_manager_can_read_but_not_write_purchases(self):
        manager_client, _, _ = self.role_client(Membership.Role.MANAGER, "manager@example.com")
        self.assertEqual(manager_client.get("/api/v1/purchases/").status_code, 200)
        response = manager_client.post("/api/v1/purchases/", self.purchase_payload(), format="json")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(manager_client.get("/api/v1/inventory/stock/").status_code, 200)

    def test_explicit_deny_blocks_inventory_writes(self):
        inventory_client, membership, _ = self.role_client(
            Membership.Role.INVENTORY, "denegado@example.com",
        )
        PermissionGrant.objects.create(
            membership=membership, permission="inventory.write", effect=PermissionGrant.Effect.DENY,
        )
        self.assertEqual(inventory_client.get("/api/v1/inventory/products/").status_code, 200)
        self.assertEqual(self.entry(client=inventory_client).status_code, 403)


class InventoryIsolationTests(InventoryScenarioMixin, APITestCase):
    def setUp(self):
        self.build_scenario()
        self.foreign = self.foreign_objects()
        self.foreign_movement = InventoryMovement.objects.create(
            company=self.foreign["company"], warehouse=self.foreign["warehouse"],
            product=self.foreign["product"], kind=InventoryMovement.Kind.ENTRY,
            direction=InventoryMovement.Direction.IN, quantity=Decimal("1"),
            unit_cost=Decimal("10"), balance_after=Decimal("1"),
        )
        StockBalance.objects.create(
            company=self.foreign["company"], warehouse=self.foreign["warehouse"],
            product=self.foreign["product"], quantity=Decimal("1"), average_cost=Decimal("10"),
        )
        self.foreign_order = PurchaseOrder.objects.create(
            company=self.foreign["company"], supplier=self.foreign["supplier"],
            warehouse=self.foreign["warehouse"],
        )
        PurchaseLine.objects.create(
            company=self.foreign["company"], purchase=self.foreign_order,
            product=self.foreign["product"], quantity=Decimal("1"), unit_cost=Decimal("10"),
        )

    def test_lists_and_details_are_tenant_scoped(self):
        response = self.client.get("/api/v1/inventory/products/")
        ids = {row["id"] for row in response.data["results"]}
        self.assertNotIn(str(self.foreign["product"].id), ids)
        self.assertEqual(
            self.client.get(f"/api/v1/inventory/products/{self.foreign['product'].id}/").status_code,
            status.HTTP_404_NOT_FOUND,
        )

        response = self.client.get("/api/v1/inventory/movements/")
        self.assertEqual(response.data["count"], 0)
        self.assertEqual(
            self.client.get(f"/api/v1/inventory/movements/{self.foreign_movement.id}/").status_code,
            status.HTTP_404_NOT_FOUND,
        )
        response = self.client.get("/api/v1/inventory/stock/")
        self.assertEqual(response.data["count"], 0)

        response = self.client.get("/api/v1/purchases/")
        self.assertEqual(response.data["count"], 0)
        self.assertEqual(
            self.client.get(f"/api/v1/purchases/{self.foreign_order.id}/").status_code,
            status.HTTP_404_NOT_FOUND,
        )
        self.assertEqual(
            self.client.post(f"/api/v1/purchases/{self.foreign_order.id}/cancel/").status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_cross_tenant_writes_are_rejected(self):
        response = self.entry(warehouse=self.foreign["warehouse"])
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response = self.entry(product=self.foreign["product"])
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        response = self.client.post("/api/v1/inventory/transfers/", self.transfer_payload(
            from_warehouse=str(self.foreign["warehouse"].id),
        ), format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        response = self.client.post("/api/v1/purchases/", self.purchase_payload(
            supplier=str(self.foreign["supplier"].id),
        ), format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response = self.client.post("/api/v1/inventory/stocktakes/", self.stocktake_payload(
            warehouse=str(self.foreign["warehouse"].id),
        ), format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
