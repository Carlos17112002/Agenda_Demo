from rest_framework.test import APITestCase

from apps.tenancy.tests.utils import make_company, make_membership, make_user


class MyCompaniesTests(APITestCase):
    def setUp(self):
        self.user = make_user("owner-estados@example.com")
        self.active = make_company("empresa-activa", "Empresa Activa")
        self.active.status = "active"
        self.active.save(update_fields=["status"])
        self.suspended = make_company("empresa-suspendida", "Empresa Suspendida")
        self.suspended.status = "suspended"
        self.suspended.save(update_fields=["status"])
        make_membership(self.user, self.active)
        make_membership(self.user, self.suspended)
        self.client.force_authenticate(user=self.user)

    def test_default_listing_hides_suspended_companies(self):
        response = self.client.get("/api/v1/companies/mine/")

        self.assertEqual(response.status_code, 200)
        rows = {row["slug"]: row["status"] for row in response.data}
        self.assertEqual(rows, {"empresa-activa": "active"})

    def test_include_all_lists_suspended_companies_with_status(self):
        response = self.client.get("/api/v1/companies/mine/", {"include": "all"})

        self.assertEqual(response.status_code, 200)
        rows = {row["slug"]: row["status"] for row in response.data}
        self.assertEqual(rows, {"empresa-activa": "active", "empresa-suspendida": "suspended"})
