from django.test import RequestFactory, SimpleTestCase, override_settings

from apps.identity.client_ip import client_ip


def _request(remote_addr, forwarded_for=None):
    extra = {"REMOTE_ADDR": remote_addr}
    if forwarded_for is not None:
        extra["HTTP_X_FORWARDED_FOR"] = forwarded_for
    return RequestFactory().get("/", **extra)


class ClientIPTests(SimpleTestCase):
    @override_settings(TRUST_PROXY_HEADERS=False)
    def test_ignores_forwarded_header_without_trusted_proxy(self):
        request = _request("192.0.2.10", "203.0.113.7")
        self.assertEqual(client_ip(request), "192.0.2.10")

    @override_settings(TRUST_PROXY_HEADERS=True, TRUSTED_PROXY_COUNT=1)
    def test_uses_hop_before_the_proxy_when_trusted(self):
        request = _request("10.0.0.1", "203.0.113.7, 10.0.0.1")
        self.assertEqual(client_ip(request), "203.0.113.7")

    @override_settings(TRUST_PROXY_HEADERS=True, TRUSTED_PROXY_COUNT=1)
    def test_ignores_spoofed_first_hop_from_client(self):
        request = _request("10.0.0.1", "1.2.3.4, 203.0.113.7, 10.0.0.1")
        self.assertEqual(client_ip(request), "203.0.113.7")

    @override_settings(TRUST_PROXY_HEADERS=True, TRUSTED_PROXY_COUNT=1)
    def test_falls_back_to_remote_addr_without_header(self):
        request = _request("198.51.100.9")
        self.assertEqual(client_ip(request), "198.51.100.9")

    def test_none_request_returns_empty_string(self):
        self.assertEqual(client_ip(None), "")
