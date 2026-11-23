from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status
from rest_framework.test import APITestCase

from apps.inventory.models import Document, Product
from apps.inventory.tests.utils import InventoryScenarioMixin


class InventoryMobileTests(InventoryScenarioMixin, APITestCase):
    def setUp(self):
        self.build_scenario()

    def test_bootstrap_includes_inventory_resources(self):
        response = self.client.get("/api/v1/mobile/bootstrap/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for resource in ("categories", "suppliers", "documents", "products"):
            self.assertIn(resource, response.data["sync_resources"])

    def test_documents_sync_is_tenant_scoped(self):
        Document.objects.create(
            company=self.company, name="Propio", original_name="propio.pdf",
            content_type="application/pdf", size=4,
            file=SimpleUploadedFile("propio.pdf", b"%PDF", content_type="application/pdf"),
        )
        foreign = self.foreign_objects()
        Document.objects.create(
            company=foreign["company"], name="Ajeno", original_name="ajeno.pdf",
            content_type="application/pdf", size=4,
            file=SimpleUploadedFile("ajeno.pdf", b"%PDF", content_type="application/pdf"),
        )
        response = self.client.get("/api/v1/mobile/sync/documents/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = {row["name"] for row in response.data["results"]}
        self.assertEqual(names, {"Propio"})

    def test_asset_create_operation_is_idempotent(self):
        payload = {
            "operations": [{
                "client_id": "11111111-1111-4111-8111-111111111111",
                "type": "inventory.asset.create",
                "payload": {
                    "kind": "asset", "name": "Máquina", "branch": str(self.branch.id),
                    "quantity": 1, "cost": "1000",
                },
            }],
        }
        first = self.client.post("/api/v1/mobile/operations/", payload, format="json")
        second = self.client.post("/api/v1/mobile/operations/", payload, format="json")
        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        self.assertEqual(first.data["results"][0]["status"], "applied")
        self.assertEqual(second.data["results"][0]["status"], "applied")
        self.assertEqual(
            first.data["results"][0]["data"]["id"],
            second.data["results"][0]["data"]["id"],
        )
        self.assertEqual(Product.objects.filter(kind=Product.Kind.ASSET).count(), 1)

    def test_document_delete_operation(self):
        document = Document.objects.create(
            company=self.company, name="Borrar", original_name="borrar.pdf",
            content_type="application/pdf", size=4,
            file=SimpleUploadedFile("borrar.pdf", b"%PDF", content_type="application/pdf"),
        )
        response = self.client.post("/api/v1/mobile/operations/", {
            "operations": [{
                "client_id": "22222222-2222-4222-8222-222222222222",
                "type": "inventory.document.delete",
                "payload": {"document": str(document.id)},
            }],
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["results"][0]["status"], "applied")
        self.assertFalse(Document.objects.filter(pk=document.id).exists())
