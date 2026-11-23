from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.billing.models import PlanFeature
from apps.bookings.models import Booking
from apps.catalog.models import Service
from apps.customers.models import Customer
from apps.identity.models import Membership
from apps.inventory.models import Product, StockBalance, Warehouse
from apps.tenancy.models import Branch
from apps.workforce.models import WorkerProfile

from apps.billing.tests.utils import BillingScenarioMixin


class MobileSyncTests(BillingScenarioMixin, TestCase):
    def setUp(self):
        self.build_billing_scenario(slug="mobile-sync")
        self.branch = Branch.objects.create(company=self.company, name="Centro", code="CEN")
        self.service = Service.objects.create(
            company=self.company, name="Corte", duration_minutes=30,
            price=Decimal("10000"),
        )
        self.customer = Customer.objects.create(
            company=self.company, first_name="Ana", last_name="Paz",
            email="ana@example.com",
        )
        self.worker = WorkerProfile.objects.create(
            company=self.company, first_name="Luis", last_name="Soto",
        )
        self.start = timezone.now() + timedelta(days=1)
        self.booking = self.make_booking(self.worker, self.start)

    def make_booking(self, worker, start_at):
        return Booking.objects.create(
            company=self.company, branch=self.branch, customer=self.customer,
            service=self.service, worker=worker, start_at=start_at,
            end_at=start_at + timedelta(minutes=30),
            block_start=start_at, block_end=start_at + timedelta(minutes=30),
            service_name=self.service.name, duration_minutes=30,
            price=self.service.price,
        )

    def test_sync_bookings_returns_company_records_and_cursor(self):
        response = self.client.get("/api/v1/mobile/sync/bookings/")

        self.assertEqual(response.status_code, 200, getattr(response, "data", None))
        self.assertEqual(response.data["resource"], "bookings")
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["id"], str(self.booking.id))
        self.assertIn("server_time", response.data)
        self.assertIn("next_since", response.data)

    def test_sync_since_only_returns_newer_records(self):
        since = timezone.now()
        newer = self.make_booking(self.worker, self.start + timedelta(hours=2))

        response = self.client.get("/api/v1/mobile/sync/bookings/", {"since": since.isoformat()})

        self.assertEqual(response.status_code, 200, getattr(response, "data", None))
        ids = [row["id"] for row in response.data["results"]]
        self.assertEqual(ids, [str(newer.id)])

    def test_sync_does_not_leak_other_company_records(self):
        from apps.tenancy.tests.utils import make_company

        other = make_company("mobile-other", "Mobile Other")
        other_branch = Branch.objects.create(company=other, name="Otra", code="OTR")
        other_service = Service.objects.create(
            company=other, name="Otro", duration_minutes=30, price=Decimal("5000"),
        )
        other_customer = Customer.objects.create(
            company=other, first_name="Otra", last_name="Persona", email="otra@example.com",
        )
        other_worker = WorkerProfile.objects.create(
            company=other, first_name="Otro", last_name="Trabajador",
        )
        start = timezone.now() + timedelta(days=2)
        Booking.objects.create(
            company=other, branch=other_branch, customer=other_customer,
            service=other_service, worker=other_worker, start_at=start,
            end_at=start + timedelta(minutes=30), block_start=start,
            block_end=start + timedelta(minutes=30),
            service_name=other_service.name, duration_minutes=30, price=other_service.price,
        )

        response = self.client.get("/api/v1/mobile/sync/bookings/")

        self.assertEqual(response.status_code, 200, getattr(response, "data", None))
        ids = [row["id"] for row in response.data["results"]]
        self.assertEqual(ids, [str(self.booking.id)])

    def test_worker_sync_only_returns_own_bookings(self):
        client, membership, _ = self.role_client(
            Membership.Role.WORKER, "worker-sync@example.com",
        )
        own_worker = WorkerProfile.objects.create(
            company=self.company, membership=membership,
            first_name="Wanda", last_name="Propia",
        )
        own = self.make_booking(own_worker, self.start + timedelta(hours=3))

        response = client.get("/api/v1/mobile/sync/bookings/")

        self.assertEqual(response.status_code, 200, getattr(response, "data", None))
        ids = [row["id"] for row in response.data["results"]]
        self.assertEqual(ids, [str(own.id)])

    def test_sync_enforces_resource_permissions(self):
        client, _, _ = self.role_client(
            Membership.Role.RECEPTION, "reception-sync@example.com",
        )

        self.assertEqual(
            client.get("/api/v1/mobile/sync/bookings/").status_code, 200,
        )
        self.assertEqual(
            client.get("/api/v1/mobile/sync/products/").status_code, 403,
        )

    def test_sync_respects_disabled_plan_feature(self):
        PlanFeature.objects.filter(plan=self.plan, code=PlanFeature.Code.BOOKINGS).update(
            enabled=False,
        )

        response = self.client.get("/api/v1/mobile/sync/bookings/")

        self.assertEqual(response.status_code, 403)
        self.assertIn("detail", response.data)

    def test_sync_rejects_invalid_since(self):
        response = self.client.get("/api/v1/mobile/sync/bookings/", {"since": "not-a-date"})

        self.assertEqual(response.status_code, 400)

    def test_sync_stock_and_movements_are_scoped_by_company(self):
        warehouse = Warehouse.objects.create(company=self.company, name="Bodega", code="BOD")
        product = Product.objects.create(
            company=self.company, sku="SKU-1", name="Producto",
            reorder_point=Decimal("5"), cost=Decimal("100"), price=Decimal("200"),
        )
        StockBalance.objects.create(
            company=self.company, warehouse=warehouse, product=product,
            quantity=Decimal("10"), average_cost=Decimal("100"),
        )

        stock = self.client.get("/api/v1/mobile/sync/stock/")
        movements = self.client.get("/api/v1/mobile/sync/movements/")

        self.assertEqual(stock.status_code, 200, getattr(stock, "data", None))
        self.assertEqual(stock.data["results"][0]["product_sku"], "SKU-1")
        self.assertEqual(movements.status_code, 200, getattr(movements, "data", None))
        self.assertEqual(movements.data["results"], [])

    def test_unknown_sync_resource_returns_not_found(self):
        response = self.client.get("/api/v1/mobile/sync/unknown/")

        self.assertEqual(response.status_code, 404)
