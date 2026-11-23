from django.test import TestCase

from apps.identity.models import Membership
from apps.tenancy.models import Branch
from apps.tenancy.tests.utils import (
    make_company, make_context, make_membership, make_user, tenant_client,
)
from apps.catalog.models import Service


class ServiceApiTests(TestCase):
    def setUp(self):
        self.company = make_company("empresa-a", "Empresa A")
        self.other_company = make_company("empresa-b", "Empresa B")
        self.owner = make_user("owner@example.com")
        make_membership(self.owner, self.company, Membership.Role.OWNER)
        self.manager = make_user("manager@example.com")
        make_membership(self.manager, self.company, Membership.Role.MANAGER)
        self.reception = make_user("reception@example.com")
        make_membership(self.reception, self.company, Membership.Role.RECEPTION)
        self.client = tenant_client(self.owner, make_context(self.owner, self.company))
        self.branch = Branch.objects.create(company=self.company, name="Centro", code="CENTRO")
        self.foreign_branch = Branch.objects.create(company=self.other_company, name="Otra", code="OTRA")

    def _create(self, client=None, **overrides):
        payload = {"name": "Corte", "duration_minutes": 45, "price": "15000.00", **overrides}
        return (client or self.client).post("/api/v1/services/", payload, format="json")

    def test_create_service_with_branch(self):
        response = self._create(branches=[str(self.branch.id)])
        self.assertEqual(response.status_code, 201, response.data)
        service = Service.objects.get(pk=response.data["id"])
        self.assertEqual(service.company, self.company)
        self.assertEqual(list(service.branches.all()), [self.branch])

    def test_service_cannot_use_branch_of_other_company(self):
        response = self._create(branches=[str(self.foreign_branch.id)])
        self.assertEqual(response.status_code, 400)
        self.assertIn("branches", response.data)

    def test_invalid_duration_and_negative_price_are_rejected(self):
        self.assertEqual(self._create(duration_minutes=2).status_code, 400)
        self.assertEqual(self._create(name="Otro", price="-1.00").status_code, 400)

    def test_only_manager_or_above_can_write(self):
        manager_client = tenant_client(self.manager, make_context(self.manager, self.company))
        reception_client = tenant_client(self.reception, make_context(self.reception, self.company))
        self.assertEqual(self._create(client=manager_client).status_code, 201)
        self.assertEqual(self._create(client=reception_client, name="Otro").status_code, 403)

    def test_list_is_tenant_scoped_and_filters_by_branch(self):
        self._create(branches=[str(self.branch.id)])
        Service.objects.create(company=self.other_company, name="Ajeno")
        response = self.client.get("/api/v1/services/", {"branch": str(self.branch.id)})
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row["name"] for row in response.data["results"]], ["Corte"])

    def test_destroy_deactivates_service(self):
        service_id = self._create().data["id"]
        response = self.client.delete(f"/api/v1/services/{service_id}/")
        self.assertEqual(response.status_code, 204)
        self.assertFalse(Service.objects.get(pk=service_id).active)
