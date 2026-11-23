from datetime import timedelta
from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from apps.identity.models import User

@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class AuthenticationFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="reset@example.com", email="reset@example.com",
            password="Correct-Horse-Battery-983!")
        self.client = APIClient()

    def _request_reset(self, email):
        return self.client.post("/api/v1/auth/password-reset/", {"email": email}, format="json")

    def test_password_reset_does_not_reveal_if_email_exists(self):
        existing = self._request_reset(self.user.email)
        missing = APIClient().post("/api/v1/auth/password-reset/", {"email": "missing@example.com"}, format="json",
            REMOTE_ADDR="203.0.113.42")
        self.assertEqual(existing.status_code, 200)
        self.assertEqual(existing.data, missing.data)
        self.assertEqual(len(mail.outbox), 1)

    def test_password_reset_token_is_single_use_and_revokes_old_sessions(self):
        old_refresh = str(RefreshToken.for_user(self.user))
        old_access = str(RefreshToken(old_refresh).access_token)
        self._request_reset(self.user.email)
        token = mail.outbox[-1].body.split(": ", 1)[1].splitlines()[0]
        response = self.client.post("/api/v1/auth/password-reset/confirm/", {
            "token": token, "new_password": "Another-Strong-Horse-284!"
        }, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(self.user.__class__.objects.get(pk=self.user.pk).check_password("Another-Strong-Horse-284!"))
        second_use = self.client.post("/api/v1/auth/password-reset/confirm/", {
            "token": token, "new_password": "Yet-Another-Strong-Horse-284!"
        }, format="json")
        self.assertEqual(second_use.status_code, 400)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {old_access}")
        old_access_response = self.client.get("/api/v1/companies/mine/")
        self.assertEqual(old_access_response.status_code, 401)
        self.client.credentials()
        refresh_response = self.client.post("/api/v1/auth/token/refresh/", {"refresh": old_refresh}, format="json")
        self.assertEqual(refresh_response.status_code, 401)

    def test_reset_token_expires(self):
        from django.core import signing
        token = signing.dumps({"uid": str(self.user.pk), "epoch": 0}, salt="identity.password-reset")
        with override_settings(PASSWORD_RESET_TIMEOUT=0):
            response = APIClient().post("/api/v1/auth/password-reset/confirm/", {
                "token": token, "new_password": "Another-Strong-Horse-284!"
            }, format="json")
        self.assertEqual(response.status_code, 400)

    def test_deactivating_user_revokes_access_and_refresh_tokens(self):
        refresh = RefreshToken.for_user(self.user)
        access = str(refresh.access_token)
        self.user.is_active = False
        self.user.save()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        response = self.client.get("/api/v1/companies/mine/")
        self.assertEqual(response.status_code, 401)
        response = self.client.post("/api/v1/auth/token/refresh/", {"refresh": str(refresh)}, format="json")
        self.assertEqual(response.status_code, 401)

    def test_login_returns_user_flags(self):
        self.user.is_saas_admin = True
        self.user.save(update_fields=["is_saas_admin"])

        response = APIClient().post("/api/v1/auth/token/", {
            "email": self.user.email, "password": "Correct-Horse-Battery-983!"
        }, format="json")

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["user"]["email"], self.user.email)
        self.assertTrue(response.data["user"]["is_saas_admin"])
        self.assertFalse(response.data["user"]["is_superuser"])

    def test_login_identifies_django_superuser(self):
        self.user.is_staff = True
        self.user.is_superuser = True
        self.user.save(update_fields=["is_staff", "is_superuser"])

        response = APIClient().post("/api/v1/auth/token/", {
            "email": self.user.email, "password": "Correct-Horse-Battery-983!"
        }, format="json")

        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(response.data["user"]["is_superuser"])

    def test_me_returns_current_user_flags(self):
        self.user.is_saas_admin = True
        self.user.save(update_fields=["is_saas_admin"])
        self.client.force_authenticate(user=self.user)

        response = self.client.get("/api/v1/auth/me/")

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["email"], self.user.email)
        self.assertTrue(response.data["is_saas_admin"])
        self.assertFalse(response.data["is_superuser"])

    def test_me_requires_authentication(self):
        response = APIClient().get("/api/v1/auth/me/")
        self.assertEqual(response.status_code, 401)

    def test_logout_blacklists_refresh_token(self):
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}")
        response = self.client.post("/api/v1/auth/logout/", {"refresh": str(refresh)}, format="json")
        self.assertEqual(response.status_code, 204)
        self.client.credentials()
        response = self.client.post("/api/v1/auth/token/refresh/", {"refresh": str(refresh)}, format="json")
        self.assertEqual(response.status_code, 401)


class PasswordChangeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="change@example.com", email="change@example.com",
            password="Correct-Horse-Battery-983!", must_change_password=True,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_login_reports_must_change_password(self):
        response = APIClient().post("/api/v1/auth/token/", {
            "email": self.user.email, "password": "Correct-Horse-Battery-983!",
        }, format="json")

        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(response.data["user"]["must_change_password"])

    def test_change_requires_the_current_password(self):
        response = self.client.post("/api/v1/auth/password/change/", {
            "current_password": "Incorrecta-123!",
            "new_password": "Another-Strong-Horse-284!",
        }, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertIn("current_password", response.data)

    def test_change_rejects_the_same_password(self):
        response = self.client.post("/api/v1/auth/password/change/", {
            "current_password": "Correct-Horse-Battery-983!",
            "new_password": "Correct-Horse-Battery-983!",
        }, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertIn("new_password", response.data)

    def test_change_issues_new_tokens_and_revokes_the_old_ones(self):
        old_refresh = RefreshToken.for_user(self.user)
        old_access = str(old_refresh.access_token)

        response = self.client.post("/api/v1/auth/password/change/", {
            "current_password": "Correct-Horse-Battery-983!",
            "new_password": "Another-Strong-Horse-284!",
        }, format="json")

        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(response.data["must_change_password"])
        self.user.refresh_from_db()
        self.assertFalse(self.user.must_change_password)
        self.assertTrue(self.user.check_password("Another-Strong-Horse-284!"))

        old_client = APIClient()
        old_client.credentials(HTTP_AUTHORIZATION=f"Bearer {old_access}")
        self.assertEqual(old_client.get("/api/v1/companies/mine/").status_code, 401)
        self.assertEqual(
            APIClient().post("/api/v1/auth/token/refresh/", {"refresh": str(old_refresh)}, format="json").status_code,
            401,
        )

        new_client = APIClient()
        new_client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
        self.assertEqual(new_client.get("/api/v1/companies/mine/").status_code, 200)
        self.assertEqual(
            APIClient().post("/api/v1/auth/token/refresh/", {"refresh": response.data["refresh"]}, format="json").status_code,
            200,
        )

    def test_change_enforces_the_password_policy(self):
        response = self.client.post("/api/v1/auth/password/change/", {
            "current_password": "Correct-Horse-Battery-983!",
            "new_password": "corta",
        }, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertIn("new_password", response.data)
