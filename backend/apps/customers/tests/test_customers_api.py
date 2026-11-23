from django.test import TestCase

from apps.audit.models import AuditEvent
from apps.customers.models import Customer
from apps.identity.models import Membership
from apps.tenancy.models import Branch
from apps.tenancy.tests.utils import (
    make_company, make_context, make_membership, make_user, tenant_client,
)


class CustomerApiTests(TestCase):
    def setUp(self):
        self.company = make_company("empresa-a", "Empresa A")
        self.other_company = make_company("empresa-b", "Empresa B")
        self.owner = make_user("owner@example.com")
        self.owner_membership = make_membership(self.owner, self.company, Membership.Role.OWNER)
        self.reception = make_user("reception@example.com")
        make_membership(self.reception, self.company, Membership.Role.RECEPTION)
        self.worker_user = make_user("worker@example.com")
        make_membership(self.worker_user, self.company, Membership.Role.WORKER)
        self.other_owner = make_user("other@example.com")
        make_membership(self.other_owner, self.other_company, Membership.Role.OWNER)
        self.client = tenant_client(self.owner, make_context(self.owner, self.company))
        self.other_client = tenant_client(self.other_owner, make_context(self.other_owner, self.other_company))
        self.branch = Branch.objects.create(company=self.company, name="Centro", code="CENTRO")

    def _create(self, client=None, **overrides):
        payload = {"first_name": "Ana", "last_name": "Pérez", "email": "ana@cliente.cl",
                   "phone": "+56911111111", **overrides}
        return (client or self.client).post("/api/v1/customers/", payload, format="json")

    def test_owner_creates_customer_and_company_is_server_assigned(self):
        response = self._create()
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(str(response.data["company"]), str(self.company.id))
        customer = Customer.objects.get(pk=response.data["id"])
        self.assertEqual(customer.company, self.company)
        self.assertEqual(AuditEvent.objects.filter(action="customer.created", entity_id=str(customer.id)).count(), 1)

    def test_client_cannot_supply_company(self):
        response = self._create(company=str(self.other_company.id))
        self.assertEqual(response.status_code, 400)
        self.assertIn("company", response.data)

    def test_list_only_returns_customers_of_active_company(self):
        self._create()
        Customer.objects.create(company=self.other_company, first_name="Ajena")
        response = self.client.get("/api/v1/customers/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row["first_name"] for row in response.data["results"]], ["Ana"])

    def test_customer_from_other_company_is_not_reachable(self):
        foreign = Customer.objects.create(company=self.other_company, first_name="Ajena")
        response = self.client.get(f"/api/v1/customers/{foreign.id}/")
        self.assertEqual(response.status_code, 404)

    def test_role_permissions_for_writes(self):
        reception_client = tenant_client(self.reception, make_context(self.reception, self.company))
        worker_client = tenant_client(self.worker_user, make_context(self.worker_user, self.company))
        self.assertEqual(self._create(client=reception_client).status_code, 201)
        self.assertEqual(self._create(client=worker_client).status_code, 403)

    def test_destroy_deactivates_instead_of_deleting(self):
        customer_id = self._create().data["id"]
        response = self.client.delete(f"/api/v1/customers/{customer_id}/")
        self.assertEqual(response.status_code, 204)
        customer = Customer.objects.get(pk=customer_id)
        self.assertFalse(customer.active)
        self.assertTrue(AuditEvent.objects.filter(action="customer.deactivated").exists())

    def test_search_and_active_filters(self):
        self._create()
        self._create(first_name="Bruno", last_name="Soto", email="bruno@cliente.cl", active=False)
        response = self.client.get("/api/v1/customers/", {"search": "Pérez"})
        self.assertEqual([row["first_name"] for row in response.data["results"]], ["Ana"])
        response = self.client.get("/api/v1/customers/", {"active": "false"})
        self.assertEqual([row["first_name"] for row in response.data["results"]], ["Bruno"])

    def test_other_tenant_cannot_create_in_my_company(self):
        response = self.other_client.post("/api/v1/customers/", {"first_name": "Intruso"}, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(str(response.data["company"]), str(self.other_company.id))
