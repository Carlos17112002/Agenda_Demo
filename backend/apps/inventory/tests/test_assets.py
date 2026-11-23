from decimal import Decimal

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from apps.inventory.models import Product
from .utils import InventoryScenarioMixin


class ProductAssetModelTests(InventoryScenarioMixin, TestCase):
    def setUp(self):
        self.build_scenario()

    def test_stock_is_the_default_kind(self):
        self.assertEqual(self.product.kind, Product.Kind.STOCK)
        self.assertEqual(self.product.status, Product.AssetStatus.AVAILABLE)
        self.assertEqual(self.product.quantity, 1)

    def test_asset_accepts_identification_location_and_purchase_fields(self):
        asset = Product.objects.create(
            company=self.company,
            kind=Product.Kind.ASSET,
            sku="ACT-MAQUINA",
            name="Máquina de corte",
            category=self.category,
            branch=self.branch,
            serial_number="SN-9988",
            internal_code="INT-01",
            quantity=2,
            purchase_date="2026-01-15",
            supplier=self.supplier,
            cost=Decimal("250000"),
            warranty_until="2027-01-15",
            notes="Incluye dos cuchillas.",
        )
        asset.refresh_from_db()
        self.assertEqual(asset.kind, Product.Kind.ASSET)
        self.assertEqual(asset.branch, self.branch)
        self.assertEqual(asset.supplier, self.supplier)
        self.assertEqual(asset.quantity, 2)
        self.assertEqual(str(asset.purchase_date), "2026-01-15")


class ProductAssetApiTests(InventoryScenarioMixin, APITestCase):
    def setUp(self):
        self.build_scenario()

    def test_asset_gets_automatic_sku(self):
        response = self.client.post("/api/v1/inventory/products/", {
            "kind": "asset",
            "name": "Secador",
            "serial_number": "SN-1",
            "branch": str(self.branch.id),
            "assigned_worker": None,
            "quantity": 1,
            "supplier": str(self.supplier.id),
            "cost": "120000",
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["sku"].startswith("ACT-"))
        self.assertEqual(response.data["kind"], "asset")
        self.assertEqual(str(response.data["branch"]), str(self.branch.id))

    def test_stock_requires_sku(self):
        response = self.client.post("/api/v1/inventory/products/", {
            "kind": "stock", "name": "Peine",
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("sku", response.data)

    def test_kind_cannot_change(self):
        asset = Product.objects.create(
            company=self.company, kind=Product.Kind.ASSET,
            sku="ACT-FIJO", name="Silla",
        )
        response = self.client.patch(
            f"/api/v1/inventory/products/{asset.id}/",
            {"kind": "stock"}, format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("kind", response.data)

    def test_kind_filter_and_tenant_scope(self):
        Product.objects.create(
            company=self.company, kind=Product.Kind.ASSET,
            sku="ACT-1", name="Máquina",
        )
        foreign = self.foreign_objects()
        Product.objects.create(
            company=foreign["company"], kind=Product.Kind.ASSET,
            sku="ACT-EXT", name="Externa",
        )
        response = self.client.get("/api/v1/inventory/products/", {"kind": "asset"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = {row["name"] for row in response.data["results"]}
        self.assertEqual(names, {"Máquina"})

    def test_asset_cannot_receive_stock(self):
        asset = Product.objects.create(
            company=self.company, kind=Product.Kind.ASSET,
            sku="ACT-2", name="Taladro",
        )
        response = self.entry(product=asset)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("product", response.data)

    def test_purchase_rejects_asset_line(self):
        asset = Product.objects.create(
            company=self.company, kind=Product.Kind.ASSET,
            sku="ACT-3", name="Compresor",
        )
        response = self.client.post(
            "/api/v1/purchases/",
            self.purchase_payload(lines=[
                {"product": str(asset.id), "quantity": "1", "unit_cost": "1000"},
            ]),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("lines", response.data)
