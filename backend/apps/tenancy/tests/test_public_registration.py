import re
from urllib.parse import unquote

from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.audit.models import AuditEvent
from apps.billing.models import Subscription
from apps.billing.tests.utils import make_plan
from apps.identity.models import Membership, User
from apps.tenancy.models import Company


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class PublicRegistrationTests(TestCase):
    def setUp(self):
        mail.outbox.clear()
        self.client = APIClient()

    def register(self, **overrides):
        payload = {
            "company_name": "Barbería Central", "email": "dueno@example.com",
            "password": "Strong-Horse-Battery-483!", "first_name": "Dueña",
        }
        payload.update(overrides)
        return self.client.post("/api/v1/auth/register-company/", payload, format="json")

    def verification_token(self):
        body = mail.outbox[-1].body
        match = re.search(r"/verificar\?token=(\S+)", body)
        self.assertIsNotNone(match, "el correo debe incluir el enlace de verificación")
        return unquote(match.group(1))

    def test_registration_creates_inactive_owner_without_slug(self):
        response = self.register()
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["email"], "dueno@example.com")
        company = Company.objects.get(slug="barberia-central")
        user = User.objects.get(email="dueno@example.com")
        self.assertFalse(user.is_active)
        self.assertEqual(Membership.objects.get(company=company).role, Membership.Role.OWNER)
        self.assertFalse(Subscription.objects.filter(company=company).exists())
        self.assertEqual(company.status, "trial")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, "Activa tu cuenta de AGENDA")
        self.assertIn("/verificar?token=", mail.outbox[0].body)
        self.assertTrue(AuditEvent.objects.filter(company=company,
            action="company.registered").exists())

    def test_duplicate_name_gets_numeric_slug_suffix(self):
        self.register()
        self.register(email="otro@example.com")
        self.assertTrue(Company.objects.filter(slug="barberia-central-2").exists())

    def test_inactive_user_cannot_login_before_verification(self):
        self.register()
        response = self.client.post("/api/v1/auth/token/", {
            "email": "dueno@example.com", "password": "Strong-Horse-Battery-483!",
        }, format="json")
        self.assertEqual(response.status_code, 401)

    def test_existing_active_email_is_rejected_with_login_hint(self):
        User.objects.create_user(username="ana@example.com", email="ana@example.com",
                                 password="Correct-horse-123")
        response = self.register(email="ana@example.com")
        self.assertEqual(response.status_code, 400)
        self.assertIn("Ya existe una cuenta con este correo", str(response.data))

    def test_pending_email_is_rejected_with_resend_hint(self):
        self.register()
        response = self.register(email="dueno@example.com")
        self.assertEqual(response.status_code, 400)
        self.assertIn("registro pendiente", str(response.data))

    def test_chosen_plan_is_stored_in_audit_metadata(self):
        plan = make_plan("pro-choice")
        response = self.register(plan=plan.code)
        self.assertEqual(response.status_code, 201, response.data)
        company = Company.objects.get(slug="barberia-central")
        event = AuditEvent.objects.get(company=company, action="company.registered")
        self.assertEqual(event.metadata["plan"], plan.code)

    def test_inactive_plan_code_is_rejected(self):
        make_plan("viejo", active=False)
        response = self.register(plan="viejo")
        self.assertEqual(response.status_code, 400)
        self.assertIn("plan", response.data)

    def test_verification_activates_user_and_starts_chosen_plan(self):
        plan = make_plan("pro-trial", trial_days=21)
        self.register(plan=plan.code)
        response = self.client.post("/api/v1/auth/verify-email/",
                                    {"token": self.verification_token()}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        user = User.objects.get(email="dueno@example.com")
        self.assertTrue(user.is_active)
        subscription = Subscription.objects.get(company=user.memberships.get().company)
        self.assertEqual(subscription.plan_id, plan.id)
        self.assertEqual(subscription.status, Subscription.Status.TRIALING)
        self.assertGreater(subscription.trial_ends_at, timezone.now())
        self.assertTrue(AuditEvent.objects.filter(company=subscription.company,
            action="company.email_verified").exists())

    def test_verification_falls_back_to_default_plan_when_plan_is_gone(self):
        make_plan("base-default", is_default=True, trial_days=7)
        plan = make_plan("temporal")
        self.register(plan=plan.code)
        plan.active = False
        plan.save(update_fields=["active"])
        response = self.client.post("/api/v1/auth/verify-email/",
                                    {"token": self.verification_token()}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        subscription = Subscription.objects.get(company__slug="barberia-central")
        self.assertEqual(subscription.plan.code, "base-default")

    def test_token_is_single_use(self):
        self.register()
        token = self.verification_token()
        first = self.client.post("/api/v1/auth/verify-email/", {"token": token}, format="json")
        self.assertEqual(first.status_code, 200)
        second = self.client.post("/api/v1/auth/verify-email/", {"token": token}, format="json")
        self.assertEqual(second.status_code, 400)
        self.assertIn("ya está verificada", str(second.data))

    def test_invalid_token_is_rejected(self):
        response = self.client.post("/api/v1/auth/verify-email/",
                                    {"token": "basura"}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("no es válido", str(response.data))

    def test_resend_is_generic_and_only_emails_pending_accounts(self):
        self.register()
        mail.outbox.clear()
        response = self.client.post("/api/v1/auth/resend-verification/",
                                    {"email": "nadie@example.com"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)
        response = self.client.post("/api/v1/auth/resend-verification/",
                                    {"email": "dueno@example.com"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("/verificar?token=", mail.outbox[0].body)
