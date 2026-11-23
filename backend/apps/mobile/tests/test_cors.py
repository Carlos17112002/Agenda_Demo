from django.test import TestCase


class MobileCorsTests(TestCase):
    def test_preflight_allows_tenant_context_header(self):
        response = self.client.options(
            "/api/v1/mobile/bootstrap/",
            HTTP_ORIGIN="http://localhost:8090",
            HTTP_ACCESS_CONTROL_REQUEST_METHOD="GET",
            HTTP_ACCESS_CONTROL_REQUEST_HEADERS="authorization,x-tenant-context",
        )

        self.assertEqual(response.status_code, 200)
        allowed = response.headers.get("access-control-allow-headers", "")
        self.assertIn("x-tenant-context", allowed)
