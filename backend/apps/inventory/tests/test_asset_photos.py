import base64
import shutil

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status
from rest_framework.test import APITestCase

from apps.inventory.models import Product
from .utils import InventoryScenarioMixin

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAEklEQVR4nGM8IRfFwMDAxAAGAA+YAURpO7lOAAAAAElFTkSuQmCC"
)


class AssetPhotoTests(InventoryScenarioMixin, APITestCase):
    def setUp(self):
        self.build_scenario()
        self.asset = Product.objects.create(
            company=self.company, kind=Product.Kind.ASSET,
            sku="ACT-FOTO", name="Máquina",
        )

    def tearDown(self):
        shutil.rmtree(settings.PRIVATE_MEDIA_ROOT, ignore_errors=True)

    def upload(self, content=PNG, name="foto.png", content_type="image/png"):
        return self.client.post(
            f"/api/v1/inventory/products/{self.asset.id}/photo/",
            {"photo": SimpleUploadedFile(name, content, content_type=content_type)},
            format="multipart",
        )

    def test_upload_get_replace_and_delete_photo(self):
        response = self.upload()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.asset.refresh_from_db()
        first_name = self.asset.photo.name
        self.assertTrue(first_name.startswith(f"assets/{self.company.id}/"))

        image = self.client.get(f"/api/v1/inventory/products/{self.asset.id}/photo/")
        self.assertEqual(image.status_code, status.HTTP_200_OK)
        self.assertEqual(image["Content-Type"], "image/png")
        image.close()

        response = self.upload()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.asset.refresh_from_db()
        self.assertNotEqual(self.asset.photo.name, first_name)
        self.assertFalse(settings.PRIVATE_MEDIA_ROOT.joinpath(first_name).exists())

        deleted = self.client.delete(
            f"/api/v1/inventory/products/{self.asset.id}/photo/"
        )
        self.assertEqual(deleted.status_code, status.HTTP_204_NO_CONTENT)
        self.asset.refresh_from_db()
        self.assertFalse(self.asset.photo)

    def test_stock_product_rejects_photo(self):
        response = self.client.post(
            f"/api/v1/inventory/products/{self.product.id}/photo/",
            {"photo": SimpleUploadedFile("foto.png", PNG, content_type="image/png")},
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("detail", response.data)

    def test_invalid_image_is_rejected(self):
        response = self.upload(content=b"no es una imagen", name="foto.png")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("photo", response.data)
