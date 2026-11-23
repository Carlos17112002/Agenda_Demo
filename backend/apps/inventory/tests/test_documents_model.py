import shutil

from django.conf import settings
from django.core.files.base import ContentFile
from django.test import TestCase

from apps.inventory.models import Document
from .utils import InventoryScenarioMixin


class DocumentModelTests(InventoryScenarioMixin, TestCase):
    def setUp(self):
        self.build_scenario()

    def tearDown(self):
        shutil.rmtree(settings.PRIVATE_MEDIA_ROOT, ignore_errors=True)

    def test_document_stores_metadata_and_private_path(self):
        document = Document.objects.create(
            company=self.company,
            client_id="0c3f7c2e-7b1a-4a6e-9f5a-2a1b3c4d5e6f",
            name="Factura",
            original_name="factura.pdf",
            content_type="application/pdf",
            size=12,
            product=self.product,
            file=ContentFile(b"%PDF-1.4 test", name="factura.pdf"),
        )
        self.assertTrue(document.file.name.startswith(f"documents/{self.company.id}/"))
        self.assertTrue(document.file.name.endswith(".pdf"))
        self.assertTrue(document.file.storage.exists(document.file.name))
        self.assertEqual(document.product, self.product)
