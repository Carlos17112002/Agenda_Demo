import uuid
from datetime import datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.test import TestCase
from django.utils import timezone

from apps.bookings.models import Booking
from apps.catalog.models import Service
from apps.customers.models import Customer
from apps.identity.models import Membership
from apps.inventory.models import InventoryMovement, Product, StockBalance, Warehouse
from apps.tenancy.models import Branch
from apps.workforce.models import WorkerProfile, WorkingHours

from apps.billing.tests.utils import BillingScenarioMixin


class MobileOperationTests(BillingScenarioMixin, TestCase):
    def setUp(self):
        self.build_billing_scenario(slug="mobile-ops")
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
        self.worker = WorkerProfile.objects.create(
            company=self.company, first_name="Luis", last_name="Soto",
        )
        self.worker.branches.add(self.branch)
        target_day = (timezone.now().astimezone(self.tz) + timedelta(days=1)).date()
        self.start_at = datetime.combine(target_day, time(10, 0), tzinfo=self.tz)
        WorkingHours.objects.create(
            company=self.company, worker=self.worker, branch=self.branch,
            weekday=target_day.weekday(), start_time=time(9, 0), end_time=time(18, 0),
        )
        self.warehouse = Warehouse.objects.create(
            company=self.company, name="Bodega", code="BOD",
        )
        self.product = Product.objects.create(
            company=self.company, sku="SKU-1", name="Producto",
            reorder_point=Decimal("2"), cost=Decimal("100"), price=Decimal("200"),
        )
        StockBalance.objects.create(
            company=self.company, warehouse=self.warehouse, product=self.product,
            quantity=Decimal("5"), average_cost=Decimal("100"),
        )

    def create_payload(self, **overrides):
        data = {
            "branch": str(self.branch.id),
            "customer": str(self.customer.id),
            "service": str(self.service.id),
            "worker": str(self.worker.id),
            "start_at": self.start_at.isoformat(),
            "notes": "Creada desde móvil",
        }
        data.update(overrides)
        return data

    def post_operations(self, operations, client=None):
        return (client or self.client).post(
            "/api/v1/mobile/operations/", {"operations": operations}, format="json",
        )

    def operation(self, op_type, payload, client_id=None):
        return {
            "client_id": str(client_id or uuid.uuid4()),
            "type": op_type,
            "payload": payload,
        }

    def test_booking_create_is_applied_and_idempotent(self):
        client_id = uuid.uuid4()
        operation = self.operation("booking.create", self.create_payload(), client_id)

        first = self.post_operations([operation])
        second = self.post_operations([operation])

        self.assertEqual(first.status_code, 200, getattr(first, "data", None))
        self.assertEqual(first.data["results"][0]["status"], "applied")
        booking_id = first.data["results"][0]["data"]["id"]
        self.assertEqual(second.data["results"][0]["data"]["id"], booking_id)
        self.assertEqual(second.data["results"][0]["status"], "applied")
        self.assertEqual(Booking.objects.filter(company=self.company).count(), 1)

    def test_booking_create_returns_conflict_when_slot_is_taken(self):
        first = self.post_operations([
            self.operation("booking.create", self.create_payload()),
        ])
        self.assertEqual(first.status_code, 200, getattr(first, "data", None))
        self.assertEqual(first.data["results"][0]["status"], "applied")

        second = self.post_operations([
            self.operation("booking.create", self.create_payload()),
        ])

        self.assertEqual(second.status_code, 200, getattr(second, "data", None))
        self.assertEqual(second.data["results"][0]["status"], "conflict")
        self.assertIn("detail", second.data["results"][0]["error"])
        self.assertEqual(Booking.objects.filter(company=self.company).count(), 1)

    def test_booking_cancel_and_stale_reschedule_are_reported(self):
        created = self.post_operations([
            self.operation("booking.create", self.create_payload()),
        ]).data["results"][0]["data"]
        booking = Booking.objects.get(pk=created["id"])

        stale = self.post_operations([self.operation("booking.reschedule", {
            "booking": str(booking.id),
            "start_at": (self.start_at + timedelta(hours=1)).isoformat(),
            "expected_start_at": (self.start_at + timedelta(minutes=1)).isoformat(),
        })])
        self.assertEqual(stale.data["results"][0]["status"], "conflict")

        canceled = self.post_operations([self.operation("booking.cancel", {
            "booking": str(booking.id), "reason": "Cliente avisó",
        })])
        self.assertEqual(canceled.status_code, 200, getattr(canceled, "data", None))
        self.assertEqual(canceled.data["results"][0]["status"], "applied")
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.Status.CANCELED)

    def test_inventory_movement_is_idempotent_and_detects_insufficient_stock(self):
        client_id = uuid.uuid4()
        movement = self.operation("inventory.movement", {
            "warehouse": str(self.warehouse.id),
            "product": str(self.product.id),
            "kind": "entry",
            "quantity": "3",
            "note": "Reposición",
        }, client_id)

        first = self.post_operations([movement])
        second = self.post_operations([movement])

        self.assertEqual(first.status_code, 200, getattr(first, "data", None))
        self.assertEqual(first.data["results"][0]["status"], "applied")
        self.assertEqual(second.data["results"][0]["data"]["id"],
                         first.data["results"][0]["data"]["id"])
        self.assertEqual(InventoryMovement.objects.filter(company=self.company).count(), 1)
        self.assertEqual(
            StockBalance.objects.get(company=self.company).quantity, Decimal("8.000"),
        )

        insufficient = self.post_operations([self.operation("inventory.movement", {
            "warehouse": str(self.warehouse.id),
            "product": str(self.product.id),
            "kind": "exit",
            "quantity": "50",
        })])
        self.assertEqual(insufficient.data["results"][0]["status"], "conflict")

    def test_operations_reject_other_company_booking(self):
        from apps.tenancy.tests.utils import make_company

        other = make_company("mobile-ops-other", "Otra")
        other_branch = Branch.objects.create(company=other, name="Otra", code="OTR")
        other_service = Service.objects.create(
            company=other, name="Otro", duration_minutes=30, price=Decimal("1000"),
        )
        other_customer = Customer.objects.create(
            company=other, first_name="Otra", last_name="Persona", email="otra@example.com",
        )
        other_worker = WorkerProfile.objects.create(
            company=other, first_name="Otro", last_name="Trabajador",
        )
        start = self.start_at
        foreign = Booking.objects.create(
            company=other, branch=other_branch, customer=other_customer,
            service=other_service, worker=other_worker, start_at=start,
            end_at=start + timedelta(minutes=30), block_start=start,
            block_end=start + timedelta(minutes=30),
            service_name=other_service.name, duration_minutes=30, price=other_service.price,
        )

        response = self.post_operations([self.operation("booking.cancel", {
            "booking": str(foreign.id), "reason": "No permitido",
        })])

        self.assertEqual(response.status_code, 200, getattr(response, "data", None))
        self.assertEqual(response.data["results"][0]["status"], "rejected")
        self.assertEqual(response.data["results"][0]["http_status"], 404)
        foreign.refresh_from_db()
        self.assertNotEqual(foreign.status, Booking.Status.CANCELED)

    def test_worker_can_only_operate_on_own_worker_bookings(self):
        client, membership, _ = self.role_client(
            Membership.Role.WORKER, "worker-ops@example.com",
        )
        own_worker = WorkerProfile.objects.create(
            company=self.company, membership=membership,
            first_name="Wanda", last_name="Propia",
        )
        own_worker.branches.add(self.branch)
        target_day = (timezone.now().astimezone(self.tz) + timedelta(days=1)).date()
        WorkingHours.objects.create(
            company=self.company, worker=own_worker, branch=self.branch,
            weekday=target_day.weekday(), start_time=time(9, 0), end_time=time(18, 0),
        )
        payload = self.create_payload(worker=str(own_worker.id))

        allowed = self.post_operations(
            [self.operation("booking.create", payload)], client=client,
        )
        denied = self.post_operations(
            [self.operation("booking.create", self.create_payload())], client=client,
        )

        self.assertEqual(allowed.data["results"][0]["status"], "applied")
        self.assertEqual(denied.data["results"][0]["status"], "rejected")
        self.assertEqual(denied.data["results"][0]["http_status"], 403)

    def test_batch_validation_rejects_non_list_and_unknown_type(self):
        response = self.client.post(
            "/api/v1/mobile/operations/", {"operations": "invalid"}, format="json",
        )
        self.assertEqual(response.status_code, 400)

        unknown = self.post_operations([self.operation("booking.unknown", {})])
        self.assertEqual(unknown.status_code, 200)
        self.assertEqual(unknown.data["results"][0]["status"], "rejected")
        self.assertEqual(unknown.data["results"][0]["http_status"], 400)

    def test_client_id_cannot_be_reused_for_another_operation_type(self):
        client_id = uuid.uuid4()
        first = self.post_operations([
            self.operation("booking.create", self.create_payload(), client_id),
        ])
        self.assertEqual(first.data["results"][0]["status"], "applied")

        reused = self.post_operations([self.operation("inventory.movement", {
            "warehouse": str(self.warehouse.id),
            "product": str(self.product.id),
            "kind": "entry",
            "quantity": "1",
        }, client_id)])

        self.assertEqual(reused.data["results"][0]["status"], "rejected")
        self.assertEqual(reused.data["results"][0]["http_status"], 409)
