from django.core.cache import cache
from django.http import HttpResponseForbidden
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from rest_framework.test import APIClient
from apps.audit.middleware import ADMIN_LOGIN_MAX_ATTEMPTS, SecurityEventsMiddleware


class SecurityLoggingTests(TestCase):
    def test_failed_login_is_logged_with_masked_email(self):
        with self.assertLogs("agenda.security", level="WARNING") as logs:
            response = APIClient().post(
                "/api/v1/auth/token/",
                {"email": "victima@example.com", "password": "incorrecta"},
                format="json",
                REMOTE_ADDR="203.0.113.90",
            )
        self.assertEqual(response.status_code, 401)
        message = "\n".join(logs.output)
        self.assertIn("login_failed", message)
        self.assertIn("v***@example.com", message)
        self.assertIn("ip=203.0.113.90", message)

    def test_invalid_reset_token_is_logged(self):
        with self.assertLogs("agenda.security", level="WARNING") as logs:
            response = APIClient().post(
                "/api/v1/auth/password-reset/confirm/",
                {"token": "token-invalido", "new_password": "Another-Strong-Horse-284!"},
                format="json",
                REMOTE_ADDR="203.0.113.91",
            )
        self.assertEqual(response.status_code, 400)
        self.assertIn("password_reset_invalid_token", "\n".join(logs.output))


class SecurityEventsMiddlewareTests(SimpleTestCase):
    def test_forbidden_response_is_logged(self):
        request = RequestFactory().get(
            "/api/v1/privado/", REMOTE_ADDR="203.0.113.92",
        )
        middleware = SecurityEventsMiddleware(lambda r: HttpResponseForbidden())
        with self.assertLogs("agenda.security", level="WARNING") as logs:
            response = middleware(request)
        self.assertEqual(response.status_code, 403)
        message = "\n".join(logs.output)
        self.assertIn("request_denied status=403", message)
        self.assertIn("path=/api/v1/privado/", message)
        self.assertIn("ip=203.0.113.92", message)

    def test_anonymous_401_is_not_logged_as_suspicious(self):
        from django.http import HttpResponse

        request = RequestFactory().get("/api/v1/privado/")
        middleware = SecurityEventsMiddleware(lambda r: HttpResponse(status=401))
        with self.assertNoLogs("agenda.security", level="WARNING"):
            middleware(request)


@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "admin-login-throttle-tests",
        }
    },
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
)
class AdminLoginThrottleTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_admin_login_page_loads_for_anonymous_users(self):
        response = self.client.get("/admin/login/")
        self.assertEqual(response.status_code, 200)

    def _post_login(self, client, ip):
        return client.post(
            "/admin/login/",
            {"username": "nadie", "password": "incorrecta"},
            REMOTE_ADDR=ip,
        )

    def test_blocks_admin_login_after_repeated_attempts(self):
        client = APIClient()
        for _ in range(ADMIN_LOGIN_MAX_ATTEMPTS):
            response = self._post_login(client, "198.51.100.10")
            self.assertNotEqual(response.status_code, 429)
        with self.assertLogs("agenda.security", level="WARNING") as logs:
            blocked = self._post_login(client, "198.51.100.10")
        self.assertEqual(blocked.status_code, 429)
        self.assertIn("admin_login_throttled", "\n".join(logs.output))

    def test_throttle_is_per_ip(self):
        client = APIClient()
        for _ in range(ADMIN_LOGIN_MAX_ATTEMPTS + 1):
            self._post_login(client, "198.51.100.11")
        response = self._post_login(client, "198.51.100.12")
        self.assertNotEqual(response.status_code, 429)
