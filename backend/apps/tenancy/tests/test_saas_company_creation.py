from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.audit.models import AuditEvent
from apps.billing.models import Subscription
from apps.billing.tests.utils import authenticated_client, make_plan, make_saas_admin
from apps.identity.models import Membership
from apps.tenancy.models import Company
from apps.tenancy.tests.utils import make_user

URL = "/api/v1/saas/companies/"


class SaasCompanyCreationTests(TestCase):
    def setUp(self):
        self.plan = make_plan("phone-default", trial_days=14, is_default=True)
        self.saas_admin = make_saas_admin()
        self.client = authenticated_client(self.saas_admin)

    def payload(self, **overrides):
        data = {
            "company_name": "Peluquería Llamada",
            "slug": "peluqueria-llamada",
            "email": "duena-llamada@example.com",
            "first_name": "María",
        }
        data.update(overrides)
        return data

    def test_non_saas_user_cannot_create_companies(self):
        owner = make_user("owner-regular@example.com")
        client = authenticated_client(owner)

        response = client.post(URL, self.payload(), format="json")

        self.assertEqual(response.status_code, 403, response.data)
        self.assertFalse(Company.objects.filter(slug="peluqueria-llamada").exists())

    def test_saas_admin_creates_company_and_returns_credentials(self):
        response = self.client.post(URL, self.payload(), format="json")

        self.assertEqual(response.status_code, 201, response.data)
        company = Company.objects.get(slug="peluqueria-llamada")
        self.assertEqual(response.data["company_id"], str(company.id))
        self.assertEqual(response.data["owner_email"], "duena-llamada@example.com")
        self.assertTrue(response.data["booking_url"].endswith("/b/peluqueria-llamada/"))
        password = response.data["temporary_password"]
        self.assertGreaterEqual(len(password), 12)

        membership = Membership.objects.get(company=company)
        self.assertEqual(membership.role, Membership.Role.OWNER)
        self.assertEqual(membership.user.email, "duena-llamada@example.com")
        self.assertTrue(membership.user.check_password(password))
        subscription = Subscription.objects.get(company=company)
        self.assertEqual(subscription.plan_id, self.plan.id)
        self.assertEqual(subscription.status, Subscription.Status.TRIALING)

    def test_operator_is_not_added_as_company_member(self):
        response = self.client.post(URL, self.payload(), format="json")

        company = Company.objects.get(pk=response.data["company_id"])
        self.assertFalse(
            Membership.objects.filter(user=self.saas_admin, company=company).exists()
        )

    def test_creation_is_audited_with_saas_origin(self):
        response = self.client.post(URL, self.payload(), format="json")

        company = Company.objects.get(pk=response.data["company_id"])
        event = AuditEvent.objects.get(company=company, action="company.registered")
        self.assertEqual(event.actor_id, self.saas_admin.id)
        self.assertEqual(event.metadata["source"], "saas_console")

    def test_saas_admin_can_choose_the_owner_password(self):
        response = self.client.post(
            URL, self.payload(password="Cliente-Fuerte-2026!"), format="json",
        )

        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["temporary_password"], "Cliente-Fuerte-2026!")
        membership = Membership.objects.get(company__slug="peluqueria-llamada")
        self.assertTrue(membership.user.check_password("Cliente-Fuerte-2026!"))

    def test_rejects_duplicates_and_weak_password(self):
        self.client.post(URL, self.payload(), format="json")

        duplicate = self.client.post(URL, self.payload(), format="json")
        self.assertEqual(duplicate.status_code, 400)

        short = self.client.post(
            URL,
            self.payload(slug="otra-empresa", email="otra@example.com", password="corta"),
            format="json",
        )
        self.assertEqual(short.status_code, 400)
        self.assertFalse(Company.objects.filter(slug="otra-empresa").exists())

    def test_saas_admin_can_choose_plan_and_trial_days(self):
        pro = make_plan("phone-pro", name="Plan Pro", trial_days=7)

        response = self.client.post(
            URL, self.payload(plan="phone-pro", trial_days=30), format="json",
        )

        self.assertEqual(response.status_code, 201, response.data)
        subscription = Subscription.objects.get(company__slug="peluqueria-llamada")
        self.assertEqual(subscription.plan_id, pro.id)
        self.assertEqual(subscription.status, Subscription.Status.TRIALING)
        self.assertEqual(response.data["subscription"]["plan"]["code"], "phone-pro")
        self.assertAlmostEqual(
            subscription.trial_ends_at,
            timezone.now() + timedelta(days=30),
            delta=timedelta(minutes=1),
        )

    def test_chosen_plan_uses_its_trial_days_when_not_overridden(self):
        make_plan("phone-pro", name="Plan Pro", trial_days=7)

        response = self.client.post(URL, self.payload(plan="phone-pro"), format="json")

        self.assertEqual(response.status_code, 201, response.data)
        subscription = Subscription.objects.get(company__slug="peluqueria-llamada")
        self.assertEqual(subscription.status, Subscription.Status.TRIALING)
        self.assertAlmostEqual(
            subscription.trial_ends_at,
            timezone.now() + timedelta(days=7),
            delta=timedelta(minutes=1),
        )

    def test_zero_trial_days_activates_the_subscription(self):
        response = self.client.post(URL, self.payload(trial_days=0), format="json")

        self.assertEqual(response.status_code, 201, response.data)
        subscription = Subscription.objects.get(company__slug="peluqueria-llamada")
        self.assertEqual(subscription.status, Subscription.Status.ACTIVE)
        self.assertIsNone(subscription.trial_ends_at)

    def test_rejects_inactive_or_unknown_plan(self):
        make_plan("phone-inactive", active=False)

        inactive = self.client.post(URL, self.payload(plan="phone-inactive"), format="json")
        unknown = self.client.post(
            URL,
            self.payload(slug="otra-empresa", email="otra@example.com", plan="no-existe"),
            format="json",
        )

        self.assertEqual(inactive.status_code, 400)
        self.assertEqual(unknown.status_code, 400)
        self.assertFalse(Company.objects.filter(slug__in=["peluqueria-llamada", "otra-empresa"]).exists())

    def test_rejects_negative_trial_days(self):
        response = self.client.post(URL, self.payload(trial_days=-1), format="json")

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Company.objects.filter(slug="peluqueria-llamada").exists())
