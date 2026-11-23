from apps.billing.models import Subscription
from apps.billing.tests.utils import BillingScenarioMixin
from apps.mobile.models import DeviceInstallation
from apps.tenancy.tests.utils import (
    make_company, make_context, make_membership, make_user, tenant_client,
)

from django.test import TestCase


class MobileDeviceTests(BillingScenarioMixin, TestCase):
    def setUp(self):
        self.build_billing_scenario(slug="mobile-devices")

    def register(self, client=None, **overrides):
        payload = {
            "installation_id": "install-0001",
            "platform": "android",
            "push_token": "token-abc",
            "app_version": "1.0.0",
            "locale": "es-CL",
        }
        payload.update(overrides)
        return (client or self.client).post(
            "/api/v1/mobile/devices/", payload, format="json",
        )

    def test_register_and_refresh_installation(self):
        first = self.register()
        self.assertEqual(first.status_code, 200, getattr(first, "data", None))
        self.assertTrue(first.data["active"])
        self.assertEqual(first.data["installation_id"], "install-0001")

        second = self.register(push_token="token-updated")
        self.assertEqual(second.status_code, 200, getattr(second, "data", None))
        self.assertEqual(second.data["id"], first.data["id"])
        self.assertEqual(second.data["push_token"], "token-updated")
        self.assertEqual(DeviceInstallation.objects.filter(company=self.company).count(), 1)

    def test_unregister_marks_installation_inactive(self):
        self.register()

        response = self.client.delete("/api/v1/mobile/devices/install-0001/")

        self.assertEqual(response.status_code, 204, getattr(response, "data", None))
        installation = DeviceInstallation.objects.get(company=self.company)
        self.assertFalse(installation.active)

    def test_installations_are_isolated_per_company(self):
        other = make_company("mobile-devices-other", "Otra")
        owner = make_user("other-owner@example.com")
        make_membership(owner, other)
        client = tenant_client(owner, make_context(owner, other))

        own = self.register()
        foreign = self.register(client=client)

        self.assertEqual(own.status_code, 200, getattr(own, "data", None))
        self.assertEqual(foreign.status_code, 200, getattr(foreign, "data", None))
        self.assertNotEqual(own.data["id"], foreign.data["id"])
        self.assertEqual(DeviceInstallation.objects.count(), 2)

    def test_invalid_platform_is_rejected(self):
        response = self.register(platform="blackberry")
        self.assertEqual(response.status_code, 400)

    def test_device_registration_stays_reachable_with_expired_subscription(self):
        from django.utils import timezone

        Subscription.objects.filter(company=self.company).update(ended_at=timezone.now())

        response = self.register()

        self.assertEqual(response.status_code, 200, getattr(response, "data", None))
