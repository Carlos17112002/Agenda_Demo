from django.test import TestCase

from apps.identity.models import Membership
from apps.tenancy.models import Branch
from apps.tenancy.tests.utils import (
    make_company, make_context, make_membership, make_user, tenant_client,
)

URL = "/api/v1/branches/"


class BranchApiTests(TestCase):
    def setUp(self):
        self.company = make_company("branches-api", "Sucursales API")
        self.owner = make_user("owner-branches@example.com")
        make_membership(self.owner, self.company, Membership.Role.OWNER)
        self.client = tenant_client(self.owner, make_context(self.owner, self.company))
        self.other_company = make_company("branches-foreign", "Ajena")
        Branch.objects.create(company=self.other_company, name="Otra", code="OTRA")

    def _client_for(self, role, email):
        user = make_user(email)
        make_membership(user, self.company, role)
        return tenant_client(user, make_context(user, self.company))

    def payload(self, **overrides):
        data = {
            "name": "Providencia",
            "code": "PROV",
            "address": "Av. Providencia 123",
            "timezone": "America/Santiago",
        }
        data.update(overrides)
        return data

    def test_owner_creates_branch_in_the_active_company(self):
        response = self.client.post(URL, self.payload(), format="json")

        self.assertEqual(response.status_code, 201, response.data)
        branch = Branch.objects.get(pk=response.data["id"])
        self.assertEqual(branch.company, self.company)
        self.assertTrue(branch.active)
        self.assertEqual(branch.timezone, "America/Santiago")

    def test_owner_cannot_send_a_foreign_company(self):
        response = self.client.post(
            URL, {**self.payload(), "company": str(self.other_company.id)}, format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Branch.objects.filter(code="PROV").exists())

    def test_admin_cannot_create_branches(self):
        client = self._client_for(Membership.Role.ADMIN, "admin-branches@example.com")

        response = client.post(URL, self.payload(), format="json")

        self.assertEqual(response.status_code, 403, response.data)
        self.assertFalse(Branch.objects.filter(code="PROV").exists())

    def test_reception_can_list_but_not_create(self):
        Branch.objects.create(company=self.company, name="Centro", code="CEN")
        client = self._client_for(Membership.Role.RECEPTION, "reception-branches@example.com")

        listing = client.get(URL)
        creation = client.post(URL, self.payload(code="NORTE"), format="json")

        self.assertEqual(listing.status_code, 200)
        names = [row["name"] for row in listing.data["results"]]
        self.assertEqual(names, ["Centro"])
        self.assertEqual(creation.status_code, 403)
        self.assertFalse(Branch.objects.filter(code="NORTE").exists())

    def test_owner_updates_and_deactivates_a_branch(self):
        branch = Branch.objects.create(company=self.company, name="Centro", code="CEN")

        updated = self.client.patch(
            f"{URL}{branch.id}/", {"name": "Centro Histórico"}, format="json",
        )
        removed = self.client.delete(f"{URL}{branch.id}/")

        self.assertEqual(updated.status_code, 200, updated.data)
        self.assertEqual(updated.data["name"], "Centro Histórico")
        self.assertEqual(removed.status_code, 204)
        branch.refresh_from_db()
        self.assertFalse(branch.active)

    def test_admin_cannot_deactivate_branches(self):
        branch = Branch.objects.create(company=self.company, name="Centro", code="CEN")
        client = self._client_for(Membership.Role.ADMIN, "admin-off@example.com")

        response = client.delete(f"{URL}{branch.id}/")

        self.assertEqual(response.status_code, 403)
        branch.refresh_from_db()
        self.assertTrue(branch.active)

    def test_duplicate_code_returns_a_field_error(self):
        Branch.objects.create(company=self.company, name="Centro", code="CEN")

        response = self.client.post(URL, self.payload(code="CEN"), format="json")

        self.assertEqual(response.status_code, 400)
        self.assertIn("code", response.data)

    def test_same_code_is_allowed_in_another_company(self):
        Branch.objects.create(company=self.company, name="Centro", code="CEN")

        foreign = Branch.objects.create(company=self.other_company, name="Centro", code="CEN")

        self.assertEqual(foreign.company, self.other_company)
