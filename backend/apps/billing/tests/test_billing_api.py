from datetime import timedelta

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.billing.models import Payment, Plan, PlanFeature, Subscription
from apps.billing.services import record_payment, start_subscription
from apps.billing.tests.utils import (
    FEATURE_CODES, authenticated_client, make_plan, make_saas_admin,
)
from apps.identity.models import Membership
from apps.tenancy.models import Company
from apps.tenancy.tests.utils import (
    make_company, make_context, make_membership, make_user, tenant_client,
)

from .utils import BillingScenarioMixin


class BillingApiTests(BillingScenarioMixin, TestCase):
    def setUp(self):
        self.build_billing_scenario()

    def test_owner_reads_current_subscription(self):
        response = self.client.get("/api/v1/subscription/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["plan"]["code"], self.plan.code)
        self.assertEqual(response.data["status"], Subscription.Status.TRIALING)
        self.assertEqual(response.data["effective_status"], Subscription.Status.TRIALING)
        self.assertTrue(response.data["usable"])
        self.assertGreater(response.data["days_remaining"], 0)

    def test_role_permissions_for_subscription(self):
        reception_client, _, _ = self.role_client(
            Membership.Role.RECEPTION, "reception-saas@example.com",
        )
        self.assertEqual(reception_client.get("/api/v1/subscription/").status_code, 403)
        self.assertEqual(
            reception_client.post("/api/v1/subscription/cancel/", {}, format="json").status_code,
            403,
        )

        manager_client, _, _ = self.role_client(
            Membership.Role.MANAGER, "manager-saas@example.com",
        )
        self.assertEqual(manager_client.get("/api/v1/subscription/").status_code, 200)
        self.assertEqual(
            manager_client.post("/api/v1/subscription/cancel/", {}, format="json").status_code,
            403,
        )

        accounting_client, _, _ = self.role_client(
            Membership.Role.ACCOUNTING, "accounting-saas@example.com",
        )
        self.assertEqual(accounting_client.get("/api/v1/subscription/").status_code, 200)

    def test_owner_changes_plan_cancels_and_resumes(self):
        premium = make_plan("premium-saas", name="Premium", price="29990")
        response = self.client.post(
            "/api/v1/subscription/change-plan/", {"plan": str(premium.id)}, format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["plan"]["code"], "premium-saas")

        response = self.client.post(
            "/api/v1/subscription/cancel/", {"immediate": False}, format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["cancel_at_period_end"])
        self.assertTrue(response.data["usable"])

        response = self.client.post("/api/v1/subscription/resume/", {}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["cancel_at_period_end"])

        response = self.client.post(
            "/api/v1/subscription/cancel/", {"immediate": True}, format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["usable"])
        self.assertEqual(response.data["effective_status"], Subscription.Status.CANCELED)
        self.assertEqual(self.client.get("/api/v1/subscription/").status_code, 200)
        self.assertEqual(self.client.get("/api/v1/customers/").status_code, 402)

    def test_expired_subscription_blocks_business_but_allows_billing(self):
        self.subscription.trial_ends_at = timezone.now() - timedelta(seconds=1)
        self.subscription.save(update_fields=["trial_ends_at"])

        self.assertEqual(self.client.get("/api/v1/customers/").status_code, 402)
        response = self.client.get("/api/v1/subscription/")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["usable"])
        self.assertEqual(response.data["effective_status"], Subscription.Status.EXPIRED)
        self.assertEqual(self.client.get("/api/v1/subscription/payments/").status_code, 200)
        self.assertEqual(self.client.get("/api/v1/subscription/invoices/").status_code, 200)

    def test_disabled_plan_module_returns_403(self):
        features = {code: (True, None) for code in FEATURE_CODES}
        features[PlanFeature.Code.CUSTOMERS] = (False, None)
        self.build_billing_scenario(slug="modulos", features=features)

        self.assertEqual(self.client.get("/api/v1/customers/").status_code, 403)
        self.assertEqual(self.client.get("/api/v1/branches/").status_code, 200)

    def test_branch_and_worker_limits_are_enforced(self):
        features = {code: (True, None) for code in FEATURE_CODES}
        features[PlanFeature.Code.BRANCHES] = (True, 1)
        features[PlanFeature.Code.WORKERS] = (True, 1)
        self.build_billing_scenario(slug="limites", features=features)

        first_branch = self.client.post(
            "/api/v1/branches/", {"name": "Centro", "code": "CENTRO"}, format="json",
        )
        self.assertEqual(first_branch.status_code, 201, first_branch.data)
        second_branch = self.client.post(
            "/api/v1/branches/", {"name": "Norte", "code": "NORTE"}, format="json",
        )
        self.assertEqual(second_branch.status_code, 402)

        first_worker = self.client.post(
            "/api/v1/workers/", {"first_name": "Ana"}, format="json",
        )
        self.assertEqual(first_worker.status_code, 201, first_worker.data)
        second_worker = self.client.post(
            "/api/v1/workers/", {"first_name": "Beto"}, format="json",
        )
        self.assertEqual(second_worker.status_code, 402)

    def test_public_portal_is_hidden_when_subscription_expires(self):
        response = APIClient().get(f"/api/v1/public/{self.company.slug}/")
        self.assertEqual(response.status_code, 200)
        self.subscription.trial_ends_at = timezone.now() - timedelta(seconds=1)
        self.subscription.save(update_fields=["trial_ends_at"])
        response = APIClient().get(f"/api/v1/public/{self.company.slug}/")
        self.assertEqual(response.status_code, 404)

    def test_payments_and_invoices_are_isolated_by_company(self):
        record_payment(
            self.subscription, amount="19990", method="transfer", reference="A-PAY",
        )
        other_company = make_company("saas-b", "SaaS B")
        other_owner = make_user("owner-saas-b@example.com")
        make_membership(other_owner, other_company, Membership.Role.OWNER)
        other_plan = make_plan("plan-saas-b", name="Plan B", price="9990")
        other_subscription = start_subscription(other_company, other_plan, trial_days=0)
        record_payment(
            other_subscription, amount="9990", method="cash", reference="B-PAY",
        )

        response = self.client.get("/api/v1/subscription/payments/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(
            response.data["results"][0]["company"], str(self.company.id),
        )
        response = self.client.get("/api/v1/subscription/invoices/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(
            response.data["results"][0]["company"], str(self.company.id),
        )


class SaasAdminApiTests(BillingScenarioMixin, TestCase):
    def setUp(self):
        self.build_billing_scenario()
        self.saas_admin = make_saas_admin("panel@example.com")
        self.saas_client = authenticated_client(self.saas_admin)

    def test_saas_endpoints_require_saas_admin(self):
        self.assertEqual(self.client.get("/api/v1/saas/plans/").status_code, 403)
        self.assertEqual(APIClient().get("/api/v1/saas/plans/").status_code, 401)
        self.assertEqual(self.saas_client.get("/api/v1/saas/plans/").status_code, 200)

    def test_saas_admin_manages_plans_with_features(self):
        payload = {
            "code": "empresa-saas", "name": "Empresa", "price": "49990",
            "billing_period": "yearly", "trial_days": 30, "is_default": True,
            "features": [
                {"code": "sales", "enabled": True},
                {"code": "branches", "enabled": True, "limit_value": 5},
            ],
        }
        response = self.saas_client.post("/api/v1/saas/plans/", payload, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        plan = Plan.objects.get(code="empresa-saas")
        self.assertTrue(plan.is_default)
        self.assertEqual(plan.features.count(), 2)
        self.assertEqual(plan.features.get(code="branches").limit_value, 5)

        response = self.saas_client.patch(
            f"/api/v1/saas/plans/{plan.id}/", {"name": "Empresa Plus"}, format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        plan.refresh_from_db()
        self.assertEqual(plan.name, "Empresa Plus")

        other = self.saas_client.post(
            "/api/v1/saas/plans/",
            {"code": "otro-default", "name": "Otro", "is_default": True},
            format="json",
        )
        self.assertEqual(other.status_code, 201, other.data)
        plan.refresh_from_db()
        self.assertFalse(plan.is_default)
        self.assertEqual(Plan.objects.filter(is_default=True).count(), 1)

    def test_saas_admin_creates_subscription_records_payment_and_lists_companies(self):
        company = make_company("saas-nueva", "SaaS Nueva")
        response = self.saas_client.post("/api/v1/saas/subscriptions/", {
            "company": str(company.id), "plan": str(self.plan.id), "trial_days": 0,
        }, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["status"], Subscription.Status.ACTIVE)
        self.assertTrue(response.data["usable"])
        subscription_id = response.data["id"]

        response = self.saas_client.post(
            f"/api/v1/saas/subscriptions/{subscription_id}/record-payment/",
            {"amount": "19990", "method": "transfer", "reference": "SAAS-1"},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["payment"]["status"], Payment.Status.COMPLETED)
        self.assertEqual(response.data["invoices"][0]["number"], "FAC-000001")
        self.assertTrue(response.data["subscription"]["usable"])

        self.assertEqual(self.saas_client.get("/api/v1/saas/payments/").status_code, 200)
        self.assertEqual(self.saas_client.get("/api/v1/saas/invoices/").status_code, 200)
        companies = self.saas_client.get("/api/v1/saas/companies/")
        self.assertEqual(companies.status_code, 200)
        codes = [row["slug"] for row in companies.data["results"]]
        self.assertIn("saas-nueva", codes)

        summary = self.saas_client.get("/api/v1/saas/summary/")
        self.assertEqual(summary.status_code, 200)
        for key in ("companies_by_status", "subscriptions_by_effective_status",
                    "mrr", "revenue_this_month", "trials_expiring_in_7_days"):
            self.assertIn(key, summary.data)

    def test_saas_admin_changes_company_status(self):
        company = make_company("saas-suspend", "SaaS Suspender")
        response = self.saas_client.post(
            f"/api/v1/saas/companies/{company.id}/change-status/",
            {"status": "suspended"}, format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        company.refresh_from_db()
        self.assertEqual(company.status, "suspended")
        response = self.saas_client.post(
            f"/api/v1/saas/companies/{company.id}/change-status/",
            {"status": "invalid"}, format="json",
        )
        self.assertEqual(response.status_code, 400)


class RegistrationAndLegacyTests(TestCase):
    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_verified_registration_uses_default_plan_trial(self):
        import re
        from urllib.parse import unquote
        from django.core import mail
        plan = make_plan("starter-default", trial_days=7, is_default=True)
        response = APIClient().post("/api/v1/auth/register-company/", {
            "company_name": "Nueva SaaS", "email": "owner-nueva@example.com",
            "password": "Strong-Horse-Battery-483!", "first_name": "Dueña",
        }, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        company = Company.objects.get(slug="nueva-saas")
        self.assertFalse(Subscription.objects.filter(company=company).exists())

        token = unquote(re.search(r"/verificar\?token=(\S+)", mail.outbox[-1].body).group(1))
        verified = APIClient().post("/api/v1/auth/verify-email/", {"token": token}, format="json")
        self.assertEqual(verified.status_code, 200, verified.data)

        subscription = Subscription.objects.get(company=company)
        self.assertEqual(subscription.plan_id, plan.id)
        self.assertEqual(subscription.status, Subscription.Status.TRIALING)
        self.assertGreater(subscription.trial_ends_at, timezone.now())
        self.assertEqual(company.status, "trial")
        self.assertEqual(Membership.objects.get(company=company).role, Membership.Role.OWNER)

    def test_company_without_subscription_keeps_legacy_access(self):
        company = make_company("legacy-co", "Legacy")
        user = make_user("owner-legacy@example.com")
        make_membership(user, company, Membership.Role.OWNER)
        client = tenant_client(user, make_context(user, company))
        self.assertEqual(client.get("/api/v1/customers/").status_code, 200)
        self.assertEqual(client.get("/api/v1/subscription/").status_code, 404)
