from datetime import timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.core import mail
from django.test import TestCase

from apps.audit.models import AuditEvent
from apps.bookings.models import Booking
from apps.catalog.models import Service
from apps.customers.models import Customer
from apps.identity.models import Membership
from apps.notifications.models import Notification
from apps.tenancy.models import Branch
from apps.tenancy.tests.utils import make_context, make_membership, make_user, tenant_client
from apps.workforce.models import BlockedSlot, Break, TimeOff, WorkerProfile, WorkingHours

from .utils import BookingScenarioMixin, local_dt, parse_api_datetime, utc_iso


class BookingApiTests(BookingScenarioMixin, TestCase):
    def setUp(self):
        self.build_scenario()

    def labels(self, response):
        return [slot["label"] for slot in response.data["slots"]]

    def action(self, booking, name, data=None):
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(f"/api/v1/bookings/{booking.id}/{name}/", data or {}, format="json")

    def reschedule(self, booking, start_at, **extra):
        payload = {"start_at": start_at.isoformat() if hasattr(start_at, "isoformat") else start_at, **extra}
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(f"/api/v1/bookings/{booking.id}/reschedule/", payload, format="json")

    def test_availability_lists_slots_in_branch_timezone(self):
        response = self.availability()
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["timezone"], "America/Santiago")
        self.assertEqual(self.labels(response)[0], "09:00")
        self.assertEqual(self.labels(response)[-1], "12:30")
        self.assertEqual(len(self.labels(response)), 15)
        self.assertEqual(response.data["slots"][0]["start_at"], utc_iso(local_dt(self.day, 9)))

    def test_each_branch_uses_its_own_timezone(self):
        self.branch.timezone = "America/New_York"
        self.branch.save(update_fields=["timezone"])
        response = self.availability()
        expected = utc_iso(local_dt(self.day, 9, tz=ZoneInfo("America/New_York")))
        self.assertEqual(response.data["slots"][0]["start_at"], expected)
        self.assertEqual(self.labels(response)[0], "09:00")

    def test_create_booking_snapshots_service_and_notifies(self):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.create_booking()
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["status"], "scheduled")
        self.assertEqual(len(response.data["public_code"]), 10)

        booking = Booking.objects.get()
        self.assertEqual(booking.company, self.company)
        self.assertEqual(booking.branch, self.branch)
        self.assertEqual(booking.worker, self.worker)
        self.assertEqual(booking.customer, self.customer)
        self.assertEqual(booking.start_at, local_dt(self.day, 10))
        self.assertEqual(booking.end_at, local_dt(self.day, 10, 30))
        self.assertEqual(booking.block_start, booking.start_at)
        self.assertEqual(booking.block_end, booking.end_at)
        self.assertEqual(booking.service_name, "Corte")
        self.assertEqual(booking.duration_minutes, 30)
        self.assertEqual(booking.price, Decimal("15000.00"))
        self.assertEqual(booking.source, Booking.Source.STAFF)
        self.assertEqual(booking.created_by, self.owner)
        self.assertTrue(AuditEvent.objects.filter(company=self.company, action="booking.created").exists())

        notification = Notification.objects.get(booking=booking)
        self.assertEqual(notification.kind, Notification.Kind.BOOKING_CREATED)
        self.assertEqual(notification.status, Notification.Status.SENT)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(booking.public_code, mail.outbox[0].body)

    def test_conflicts_off_grid_and_outside_shift_are_rejected(self):
        off_grid = self.create_booking(local_dt(self.day, 10, 7))
        self.assertEqual(off_grid.status_code, 409, off_grid.data)
        self.assertEqual(Booking.objects.count(), 0)

        with self.captureOnCommitCallbacks(execute=True):
            first = self.create_booking(local_dt(self.day, 10))
        self.assertEqual(first.status_code, 201, first.data)

        duplicate = self.create_booking(local_dt(self.day, 10))
        self.assertEqual(duplicate.status_code, 409, duplicate.data)
        before_shift = self.create_booking(local_dt(self.day, 8))
        self.assertEqual(before_shift.status_code, 409, before_shift.data)
        other_day = self.create_booking(local_dt(self.day + timedelta(days=1), 10))
        self.assertEqual(other_day.status_code, 409, other_day.data)
        self.assertEqual(Booking.objects.count(), 1)

    def test_booking_buffers_block_adjacent_slots(self):
        self.service.buffer_after_minutes = 15
        self.service.save(update_fields=["buffer_after_minutes"])
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.create_booking(local_dt(self.day, 10)).status_code, 201)

        response = self.availability()
        labels = self.labels(response)
        self.assertNotIn("10:15", labels)
        self.assertNotIn("10:30", labels)
        self.assertIn("10:45", labels)
        self.assertEqual(self.create_booking(local_dt(self.day, 10, 30)).status_code, 409)
        self.assertEqual(self.create_booking(local_dt(self.day, 10, 45)).status_code, 201)

    def test_time_off_blocks_availability_and_creation(self):
        TimeOff.objects.create(
            company=self.company, worker=self.worker, branch=self.branch,
            starts_at=local_dt(self.day, 10), ends_at=local_dt(self.day, 11), reason="Médico",
        )
        labels = self.labels(self.availability())
        self.assertNotIn("10:00", labels)
        self.assertNotIn("10:45", labels)
        self.assertIn("11:00", labels)
        self.assertEqual(self.create_booking(local_dt(self.day, 10, 30)).status_code, 409)

    def test_breaks_and_blocked_slots_remove_availability(self):
        Break.objects.create(
            company=self.company, worker=self.worker, branch=self.branch,
            weekday=self.day.weekday(), start_time=local_dt(self.day, 10).time(),
            end_time=local_dt(self.day, 10, 30).time(), label="Café",
        )
        labels = self.labels(self.availability())
        self.assertNotIn("10:00", labels)
        self.assertNotIn("10:15", labels)
        self.assertIn("10:30", labels)
        self.assertEqual(self.create_booking(local_dt(self.day, 10)).status_code, 409)

        BlockedSlot.objects.create(
            company=self.company, worker=self.worker, branch=self.branch,
            starts_at=local_dt(self.day, 11), ends_at=local_dt(self.day, 11, 30), reason="Reunión",
        )
        labels = self.labels(self.availability())
        self.assertNotIn("11:00", labels)
        self.assertNotIn("11:15", labels)
        self.assertIn("11:30", labels)
        self.assertEqual(self.create_booking(local_dt(self.day, 11)).status_code, 409)

    def test_booking_validates_active_targets_and_future_start(self):
        self.service.active = False
        self.service.save(update_fields=["active"])
        self.assertEqual(self.create_booking().status_code, 400)
        self.service.active = True
        self.service.save(update_fields=["active"])

        self.worker.branches.clear()
        self.assertEqual(self.create_booking().status_code, 400)
        self.worker.branches.add(self.branch)

        past = self.create_booking(local_dt(self.day - timedelta(days=14), 10))
        self.assertEqual(past.status_code, 400, past.data)

        response = self.client.patch(f"/api/v1/branches/{self.branch.id}/",
                                     {"timezone": "Not/AZone"}, format="json")
        self.assertEqual(response.status_code, 400)
        response = self.client.patch(f"/api/v1/branches/{self.branch.id}/",
                                     {"timezone": "America/New_York"}, format="json")
        self.assertEqual(response.status_code, 200, response.data)

    def test_worker_role_only_sees_and_books_own_agenda(self):
        staff_user = make_user("ana.worker@example.com")
        staff_membership = make_membership(staff_user, self.company, Membership.Role.WORKER)
        self.worker.membership = staff_membership
        self.worker.save(update_fields=["membership"])
        other_worker = self.add_worker("Bruno")

        with self.captureOnCommitCallbacks(execute=True):
            own = self.create_booking(local_dt(self.day, 10))
            foreign = self.create_booking(local_dt(self.day, 10), worker=str(other_worker.id))
        self.assertEqual(own.status_code, 201, own.data)
        self.assertEqual(foreign.status_code, 201, foreign.data)

        worker_client = tenant_client(staff_user, make_context(staff_user, self.company))
        listing = worker_client.get("/api/v1/bookings/")
        self.assertEqual(listing.status_code, 200)
        self.assertEqual([row["id"] for row in listing.data["results"]], [own.data["id"]])
        self.assertEqual(worker_client.get(f"/api/v1/bookings/{foreign.data['id']}/").status_code, 404)
        self.assertEqual(self.availability(client=worker_client, worker=str(other_worker.id)).status_code, 403)
        self.assertEqual(self.availability(client=worker_client).status_code, 200)
        blocked = self.create_booking(local_dt(self.day, 11), client=worker_client,
                                      worker=str(other_worker.id))
        self.assertEqual(blocked.status_code, 403)
        allowed = self.create_booking(local_dt(self.day, 11), client=worker_client)
        self.assertEqual(allowed.status_code, 201, allowed.data)

    def test_status_transitions_are_audited_and_idempotent(self):
        with self.captureOnCommitCallbacks(execute=True):
            booking = Booking.objects.get(pk=self.create_booking().data["id"])

        response = self.action(booking, "confirm")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["status"], "confirmed")
        kinds = set(Notification.objects.filter(booking=booking).values_list("kind", flat=True))
        self.assertEqual(kinds, {"booking_created", "booking_confirmed"})

        self.assertEqual(self.action(booking, "confirm").status_code, 200)
        self.assertEqual(Notification.objects.filter(booking=booking).count(), 2)

        self.assertEqual(self.action(booking, "complete").data["status"], "completed")
        self.assertEqual(self.action(booking, "cancel").status_code, 409)
        self.assertEqual(self.client.delete(f"/api/v1/bookings/{booking.id}/").status_code, 405)
        notes = self.client.patch(f"/api/v1/bookings/{booking.id}/", {"notes": "Llegó temprano"}, format="json")
        self.assertEqual(notes.status_code, 200, notes.data)
        self.assertEqual(notes.data["notes"], "Llegó temprano")

        with self.captureOnCommitCallbacks(execute=True):
            cancelable = Booking.objects.get(pk=self.create_booking(local_dt(self.day, 11)).data["id"])
        canceled = self.action(cancelable, "cancel", {"reason": "Viaje"})
        self.assertEqual(canceled.status_code, 200, canceled.data)
        canceled = Booking.objects.get(pk=cancelable.pk)
        self.assertEqual(canceled.status, Booking.Status.CANCELED)
        self.assertIsNotNone(canceled.canceled_at)
        self.assertEqual(canceled.canceled_reason, "Viaje")
        kinds = set(Notification.objects.filter(booking=canceled).values_list("kind", flat=True))
        self.assertEqual(kinds, {"booking_created", "booking_canceled"})

        with self.captureOnCommitCallbacks(execute=True):
            absent = Booking.objects.get(pk=self.create_booking(local_dt(self.day, 12)).data["id"])
        self.assertEqual(self.action(absent, "no-show").data["status"], "no_show")
        self.assertEqual(
            set(Notification.objects.filter(booking=absent).values_list("kind", flat=True)),
            {"booking_created"},
        )

    def test_reschedule_moves_booking_and_checks_conflicts(self):
        with self.captureOnCommitCallbacks(execute=True):
            first = Booking.objects.get(pk=self.create_booking(local_dt(self.day, 10)).data["id"])
            self.assertEqual(self.create_booking(local_dt(self.day, 11)).status_code, 201)

        self.assertEqual(self.reschedule(first, local_dt(self.day, 11)).status_code, 409)
        self.assertEqual(self.reschedule(first, local_dt(self.day, 8)).status_code, 409)

        moved = self.reschedule(first, local_dt(self.day, 12))
        self.assertEqual(moved.status_code, 200, moved.data)
        first.refresh_from_db()
        self.assertEqual(first.start_at, local_dt(self.day, 12))
        self.assertEqual(first.end_at, local_dt(self.day, 12, 30))
        self.assertEqual(Notification.objects.filter(booking=first, kind="booking_rescheduled").count(), 1)

        self.assertEqual(self.reschedule(first, local_dt(self.day, 12)).status_code, 200)
        self.assertEqual(Notification.objects.filter(booking=first, kind="booking_rescheduled").count(), 1)

        other_worker = self.add_worker("Bruno")
        changed = self.reschedule(first, local_dt(self.day, 12), worker=str(other_worker.id))
        self.assertEqual(changed.status_code, 200, changed.data)
        first.refresh_from_db()
        self.assertEqual(first.worker, other_worker)

        self.assertEqual(self.action(first, "complete").status_code, 200)
        self.assertEqual(self.reschedule(first, local_dt(self.day, 12, 30)).status_code, 409)

    def test_calendar_filters_and_notes(self):
        with self.captureOnCommitCallbacks(execute=True):
            first = self.create_booking(local_dt(self.day, 10))
            self.create_booking(local_dt(self.day, 11))
        self.assertEqual(first.status_code, 201)

        by_day = self.client.get("/api/v1/bookings/", {"date": self.day.isoformat()})
        self.assertEqual(len(by_day.data["results"]), 2)
        empty_day = self.client.get("/api/v1/bookings/", {"date": (self.day + timedelta(days=2)).isoformat()})
        self.assertEqual(len(empty_day.data["results"]), 0)
        by_status = self.client.get("/api/v1/bookings/", {"status": "scheduled"})
        self.assertEqual(len(by_status.data["results"]), 2)
        by_search = self.client.get("/api/v1/bookings/", {"search": "luis@example.com"})
        self.assertEqual(len(by_search.data["results"]), 2)
        ordered = self.client.get("/api/v1/bookings/", {"ordering": "-start_at"})
        self.assertEqual(parse_api_datetime(ordered.data["results"][0]["start_at"]),
                         local_dt(self.day, 11))

    def test_tenant_isolation_for_bookings(self):
        other_company = self.add_other_company()
        foreign_branch = Branch.objects.create(company=other_company, name="Otra", code="OTRA")
        foreign_service = Service.objects.create(company=other_company, name="Corte", duration_minutes=30)
        foreign_worker = WorkerProfile.objects.create(company=other_company, first_name="Ajeno")
        foreign_customer = Customer.objects.create(company=other_company, first_name="Otro")

        for field, value in [
            ("branch", foreign_branch), ("service", foreign_service),
            ("worker", foreign_worker), ("customer", foreign_customer),
        ]:
            response = self.create_booking(**{field: str(value.id)})
            self.assertIn(response.status_code, {400, 403}, (field, response.data))
        self.assertEqual(Booking.objects.count(), 0)

        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.create_booking().status_code, 201)
        Booking.objects.create(
            company=other_company, branch=foreign_branch, service=foreign_service,
            worker=foreign_worker, customer=foreign_customer,
            start_at=local_dt(self.day, 10), end_at=local_dt(self.day, 10, 30),
            block_start=local_dt(self.day, 10), block_end=local_dt(self.day, 10, 30),
            service_name="Corte", duration_minutes=30, price=Decimal("0"),
        )
        mine = self.client.get("/api/v1/bookings/")
        self.assertEqual(len(mine.data["results"]), 1)
        self.assertEqual(mine.data["results"][0]["company"], str(self.company.id))

        other_owner = make_user("other-owner@example.com")
        make_membership(other_owner, other_company, Membership.Role.OWNER)
        other_client = tenant_client(other_owner, make_context(other_owner, other_company))
        theirs = other_client.get("/api/v1/bookings/")
        self.assertEqual(len(theirs.data["results"]), 1)
        self.assertEqual(theirs.data["results"][0]["company"], str(other_company.id))

    def test_customer_without_email_skips_notifications(self):
        self.customer.email = ""
        self.customer.save(update_fields=["email"])
        with self.captureOnCommitCallbacks(execute=True):
            response = self.create_booking()
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(Notification.objects.count(), 0)
        self.assertEqual(len(mail.outbox), 0)

    def add_other_company(self):
        from apps.tenancy.tests.utils import make_company
        return make_company("agenda-b", "Agenda B")
