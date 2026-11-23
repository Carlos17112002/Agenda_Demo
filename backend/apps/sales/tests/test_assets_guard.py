from types import SimpleNamespace

from django.test import SimpleTestCase
from rest_framework.exceptions import ValidationError

from apps.sales.services import _normalize_sale_lines


class SaleAssetGuardTests(SimpleTestCase):
    def test_sale_rejects_asset_product(self):
        company = SimpleNamespace(id="company-1")
        product = SimpleNamespace(
            pk="product-1", company_id="company-1", kind="asset",
            active=True, sku="ACT-1", price=0, name="Máquina",
        )
        with self.assertRaisesMessage(ValidationError, "no maneja stock"):
            _normalize_sale_lines(
                [{"product": product, "service": None, "quantity": "1"}], company,
            )
