import shutil
from unittest.mock import patch

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status
from rest_framework.test import APITestCase

from apps.inventory.models import Document
from .utils import InventoryScenarioMixin


PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF"


class DocumentApiTests(InventoryScenarioMixin, APITestCase):
    def setUp(self):
        self.build_scenario()

    def tearDown(self):
        shutil.rmtree(settings.PRIVATE_MEDIA_ROOT, ignore_errors=True)

    def upload(self, *, name="factura.pdf", content=PDF, content_type="application/pdf",
               product=None, client_id=None):
        payload = {
            "file": SimpleUploadedFile(name, content, content_type=content_type),
            "name": "Factura",
        }
        if product is not None:
            payload["product"] = str(product.id)
        if client_id is not None:
            payload["client_id"] = str(client_id)
        return self.client.post("/api/v1/inventory/documents/", payload, format="multipart")

    def test_upload_lists_and_downloads_with_private_headers(self):
        response = self.upload(product=self.product)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(str(response.data["product"]), str(self.product.id))
        self.assertEqual(response.data["content_type"], "application/pdf")
        self.assertGreater(response.data["size"], 0)

        listing = self.client.get("/api/v1/inventory/documents/")
        self.assertEqual(listing.status_code, status.HTTP_200_OK)
        self.assertEqual(listing.data["count"], 1)

        download = self.client.get(
            f"/api/v1/inventory/documents/{response.data['id']}/download/"
        )
        self.assertEqual(download.status_code, status.HTTP_200_OK)
        self.assertEqual(download["X-Content-Type-Options"], "nosniff")
        self.assertEqual(download["Cache-Control"], "private, no-store")
        self.assertIn("attachment", download["Content-Disposition"])

    def test_client_id_is_idempotent(self):
        client_id = "8f1f6a60-4f7a-4c6f-9c1f-2c3d4e5f6a7b"
        first = self.upload(client_id=client_id)
        second = self.upload(client_id=client_id)
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        self.assertEqual(first.data["id"], second.data["id"])
        self.assertEqual(Document.objects.count(), 1)

    def test_invalid_format_is_rejected(self):
        response = self.upload(
            name="script.exe", content=b"MZ...", content_type="application/octet-stream",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("file", response.data)

    def test_foreign_product_is_rejected(self):
        foreign = self.foreign_objects()
        response = self.upload(product=foreign["product"])
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("product", response.data)

    def test_quota_exceeded(self):
        with patch("apps.inventory.views.COMPANY_STORAGE_LIMIT_BYTES", 10):
            response = self.upload()
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("detail", response.data)

    def test_foreign_document_is_not_visible(self):
        response = self.upload()
        foreign = self.foreign_objects()
        foreign_doc = Document.objects.create(
            company=foreign["company"], name="Externo", original_name="externo.pdf",
            content_type="application/pdf", size=4,
            file=SimpleUploadedFile("externo.pdf", PDF, content_type="application/pdf"),
        )
        listing = self.client.get("/api/v1/inventory/documents/")
        ids = {row["id"] for row in listing.data["results"]}
        self.assertNotIn(str(foreign_doc.id), ids)
        download = self.client.get(
            f"/api/v1/inventory/documents/{foreign_doc.id}/download/"
        )
        self.assertEqual(download.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_removes_file(self):
        response = self.upload()
        document = Document.objects.get(pk=response.data["id"])
        path = document.file.path
        file_name = document.file.name
        deleted = self.client.delete(f"/api/v1/inventory/documents/{document.id}/")
        self.assertEqual(deleted.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Document.objects.filter(pk=document.id).exists())
        self.assertFalse(settings.PRIVATE_MEDIA_ROOT.joinpath(file_name).exists())
        self.assertTrue(path)

    def test_storage_usage(self):
        self.upload()
        response = self.client.get("/api/v1/inventory/documents/storage/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreater(response.data["used_bytes"], 0)
        self.assertEqual(response.data["limit_bytes"], 5_368_709_120)
        self.assertEqual(response.data["document_count"], 1)
