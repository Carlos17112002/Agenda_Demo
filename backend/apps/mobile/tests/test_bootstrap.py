from rest_framework.test import APIClient
from django.test import TestCase

from apps.billing.tests.utils import BillingScenarioMixin
from apps.identity.models import Membership, PermissionGrant
from apps.tenancy.models import Branch
from apps.tenancy.tests.utils import (
    make_company, make_context, make_membership, make_user, tenant_client,
)


class MobileBootstrapTests(BillingScenarioMixin, TestCase):
    def setUp(self):
        self.build_billing_scenario(slug="mobile-bootstrap")
        self.branch = Branch.objects.create(
            company=self.company, name="Centro", code="CEN",
        )

    def test_bootstrap_returns_profile_permissions_features_and_branches(self):
        response = self.client.get("/api/v1/mobile/bootstrap/")

        self.assertEqual(response.status_code, 200, getattr(response, "data", None))
        self.assertEqual(response.data["user"]["email"], self.owner.email)
        self.assertEqual(response.data["company"]["id"], str(self.company.id))
        self.assertEqual(response.data["company"]["slug"], self.company.slug)
        self.assertEqual(response.data["membership"]["role"], "owner")
        self.assertIn("bookings.write", response.data["permissions"])
        self.assertIn("inventory.write", response.data["permissions"])
        self.assertIn("subscription.manage", response.data["permissions"])
        self.assertTrue(response.data["features"]["bookings"])
        self.assertTrue(response.data["features"]["inventory"])
        self.assertEqual(response.data["branches"][0]["code"], "CEN")
        self.assertEqual(response.data["subscription"]["effective_status"], "trialing")
        self.assertEqual(response.data["billing_state"], "usable")
        self.assertIn("server_time", response.data)
        self.assertIn("bookings", response.data["sync_resources"])
        self.assertIn("stock", response.data["sync_resources"])
        self.assertIn(self.company.slug, [row["slug"] for row in response.data["companies"]])

    def test_bootstrap_applies_role_defaults_and_deny_grants(self):
        client, membership, _ = self.role_client(
            Membership.Role.RECEPTION, "reception-mobile@example.com",
        )
        PermissionGrant.objects.create(
            membership=membership, permission="bookings.write", effect="deny",
        )

        response = client.get("/api/v1/mobile/bootstrap/")

        self.assertEqual(response.status_code, 200, getattr(response, "data", None))
        self.assertIn("bookings.read", response.data["permissions"])
        self.assertNotIn("bookings.write", response.data["permissions"])
        self.assertIn("sales.write", response.data["permissions"])
        self.assertNotIn("inventory.write", response.data["permissions"])

    def test_worker_bootstrap_uses_own_booking_permissions(self):
        client, membership, _ = self.role_client(
            Membership.Role.WORKER, "worker-mobile@example.com",
        )
        from apps.workforce.models import WorkerProfile

        worker = WorkerProfile.objects.create(
            company=self.company, membership=membership,
            first_name="Wanda", last_name="Propia",
        )

        response = client.get("/api/v1/mobile/bootstrap/")

        self.assertEqual(response.status_code, 200, getattr(response, "data", None))
        self.assertIn("bookings.own.read", response.data["permissions"])
        self.assertIn("bookings.own.write", response.data["permissions"])
        self.assertNotIn("bookings.read", response.data["permissions"])
        self.assertNotIn("customers.read", response.data["permissions"])
        self.assertEqual(response.data["worker"]["id"], str(worker.id))
        self.assertEqual(response.data["worker"]["name"], "Wanda Propia")

    def test_bootstrap_requires_tenant_context(self):
        client = APIClient()
        client.force_authenticate(user=self.owner)

        response = client.get("/api/v1/mobile/bootstrap/")

        self.assertEqual(response.status_code, 403)

    def test_company_without_subscription_keeps_legacy_access(self):
        company = make_company("mobile-legacy", "Mobile Legacy")
        user = make_user("legacy-owner@example.com")
        make_membership(user, company, Membership.Role.OWNER)
        client = tenant_client(user, make_context(user, company))

        response = client.get("/api/v1/mobile/bootstrap/")

        self.assertEqual(response.status_code, 200, getattr(response, "data", None))
        self.assertEqual(response.data["billing_state"], "legacy")
        self.assertIsNone(response.data["subscription"])
        self.assertTrue(all(response.data["features"].values()))

    def test_bootstrap_exposes_member_management_context(self):
        membership = self.owner.memberships.get(company=self.company)
        membership.default_branch = self.branch
        membership.save(update_fields=["default_branch"])
        self.owner.must_change_password = True
        self.owner.save(update_fields=["must_change_password"])

        response = self.client.get("/api/v1/mobile/bootstrap/")

        self.assertEqual(response.status_code, 200, getattr(response, "data", None))
        self.assertTrue(response.data["user"]["must_change_password"])
        self.assertEqual(response.data["membership"]["default_branch"]["id"], str(self.branch.id))
        self.assertEqual(response.data["membership"]["default_branch"]["name"], "Centro")
        self.assertIn("company.manage", response.data["permission_catalog"])
        self.assertIn("bookings.read", response.data["role_defaults"]["reception"])
        self.assertNotIn("inventory.write", response.data["role_defaults"]["reception"])
        self.assertIn("company.manage", response.data["role_defaults"]["owner"])
