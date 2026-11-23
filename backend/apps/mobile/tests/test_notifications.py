from datetime import datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.test import TestCase
from django.utils import timezone

from apps.billing.models import Subscription
from apps.billing.tests.utils import BillingScenarioMixin
from apps.bookings.services import create_booking
from apps.catalog.models import Service
from apps.customers.models import Customer
from apps.identity.models import Membership
from apps.inventory.models import Product, Warehouse
from apps.inventory.services import create_manual_movement
from apps.mobile.models import DeviceInstallation, PushMessage
from apps.mobile.push import deliver_push, enqueue_push
from apps.tenancy.models import Branch
from apps.tenancy.tests.utils import (
    make_company, make_membership, make_user,
)
from apps.workforce.models import WorkerProfile, WorkingHours


class MobileNotificationTests(BillingScenarioMixin, TestCase):
    def setUp(self):
        self.build_billing_scenario(slug="mobile-push")
        self.tz = ZoneInfo("America/Santiago")
        self.branch = Branch.objects.create(
            company=self.company, name="Centro", code="CEN", timezone="America/Santiago",
        )
        self.service = Service.objects.create(
            company=self.company, name="Corte", duration_minutes=30,
            price=Decimal("10000"),
        )
        self.customer = Customer.objects.create(
            company=self.company, first_name="Ana", last_name="Paz",
            email="ana@example.com",
        )
        self.worker_user = make_user("mobile-worker@example.com")
        self.worker_membership = make_membership(
            self.worker_user, self.company, Membership.Role.WORKER,
        )
        self.worker = WorkerProfile.objects.create(
            company=self.company, membership=self.worker_membership,
            first_name="Luis", last_name="Soto",
        )
        self.worker.branches.add(self.branch)
        target_day = (timezone.now().astimezone(self.tz) + timedelta(days=1)).date()
        WorkingHours.objects.create(
            company=self.company, worker=self.worker, branch=self.branch,
            weekday=target_day.weekday(), start_time=time(9, 0), end_time=time(18, 0),
        )
        self.start_at = datetime.combine(target_day, time(10, 0), tzinfo=self.tz)

    def make_message(self, user=None, company=None, **overrides):
        return PushMessage.objects.create(
            company=company or self.company,
            user=user or self.owner,
            kind=PushMessage.Kind.SYSTEM,
            title=overrides.pop("title", "Mensaje"),
            body=overrides.pop("body", "Contenido"),
            **overrides,
        )

    def test_notification_center_lists_unread_count(self):
        self.make_message(title="Uno")
        self.make_message(title="Dos", read_at=timezone.now())

        response = self.client.get("/api/v1/mobile/notifications/")

        self.assertEqual(response.status_code, 200, getattr(response, "data", None))
        self.assertEqual(response.data["unread_count"], 1)
        self.assertEqual(len(response.data["results"]), 2)

    def test_mark_message_as_read(self):
        message = self.make_message()

        response = self.client.post(f"/api/v1/mobile/notifications/{message.id}/read/")

        self.assertEqual(response.status_code, 200, getattr(response, "data", None))
        self.assertIsNotNone(response.data["read_at"])

    def test_mark_all_messages_as_read(self):
        self.make_message()
        self.make_message()

        response = self.client.post("/api/v1/mobile/notifications/read-all/")

        self.assertEqual(response.status_code, 200, getattr(response, "data", None))
        self.assertEqual(response.data["updated"], 2)

    def test_notification_center_is_isolated_by_user_and_company(self):
        self.make_message()
        other_user = make_user("other-mobile@example.com")
        self.make_message(user=other_user, title="Ajena")
        other_company = make_company("mobile-push-other", "Otra")
        foreign = PushMessage.objects.create(
            company=other_company, user=self.owner, kind=PushMessage.Kind.SYSTEM,
            title="Extranjera",
        )

        listed = self.client.get("/api/v1/mobile/notifications/")
        marked = self.client.post(f"/api/v1/mobile/notifications/{foreign.id}/read/")

        titles = [row["title"] for row in listed.data["results"]]
        self.assertEqual(titles, ["Mensaje"])
        self.assertEqual(marked.status_code, 404, getattr(marked, "data", None))

    def test_booking_creation_enqueues_push_for_worker(self):
        with self.captureOnCommitCallbacks(execute=True):
            create_booking(
                company=self.company, branch=self.branch, service=self.service,
                worker=self.worker, customer=self.customer, start_at=self.start_at,
                actor=self.owner,
            )

        message = PushMessage.objects.get(
            company=self.company, user=self.worker_user,
            kind=PushMessage.Kind.BOOKING_CREATED,
        )
        self.assertIn("Corte", message.title)
        self.assertEqual(message.data["worker_id"], str(self.worker.id))

    def test_low_stock_movement_enqueues_push_for_inventory_staff(self):
        warehouse = Warehouse.objects.create(
            company=self.company, name="Bodega", code="BOD",
        )
        product = Product.objects.create(
            company=self.company, sku="SKU-1", name="Producto",
            reorder_point=Decimal("2"), cost=Decimal("100"), price=Decimal("200"),
        )
        from apps.inventory.models import StockBalance

        StockBalance.objects.create(
            company=self.company, warehouse=warehouse, product=product,
            quantity=Decimal("5"), average_cost=Decimal("100"),
        )
        with self.captureOnCommitCallbacks(execute=True):
            create_manual_movement(
                company=self.company, warehouse=warehouse, product=product,
                kind="exit", quantity=Decimal("4"), actor=self.owner,
            )

        message = PushMessage.objects.get(
            company=self.company, kind=PushMessage.Kind.LOW_STOCK,
        )
        self.assertIn(product.sku, message.body)

    def test_push_delivery_marks_skipped_without_devices(self):
        message = enqueue_push(
            company=self.company, user=self.owner, kind=PushMessage.Kind.SYSTEM,
            title="Sin dispositivos",
        )

        deliver_push(message.pk)

        message.refresh_from_db()
        self.assertEqual(message.status, PushMessage.Status.SKIPPED)

    def test_push_delivery_marks_sent_with_console_provider(self):
        DeviceInstallation.objects.create(
            company=self.company, user=self.owner, installation_id="push-device",
            platform=DeviceInstallation.Platform.ANDROID, push_token="token-1",
        )
        message = enqueue_push(
            company=self.company, user=self.owner, kind=PushMessage.Kind.SYSTEM,
            title="Con dispositivo",
        )

        deliver_push(message.pk)

        message.refresh_from_db()
        self.assertEqual(message.status, PushMessage.Status.SENT)
        self.assertEqual(message.provider, "console")
        self.assertIsNotNone(message.sent_at)

    def test_notification_center_stays_reachable_with_expired_subscription(self):
        Subscription.objects.filter(company=self.company).update(ended_at=timezone.now())

        response = self.client.get("/api/v1/mobile/notifications/")

        self.assertEqual(response.status_code, 200, getattr(response, "data", None))
