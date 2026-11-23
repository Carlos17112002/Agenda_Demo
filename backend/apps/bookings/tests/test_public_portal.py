from datetime import timedelta

from django.core import mail
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.bookings.models import Booking
from apps.catalog.models import Service
from apps.customers.models import Customer
from apps.notifications.models import Notification
from apps.tenancy.models import Branch, Company
from apps.tenancy.tests.utils import make_company
from apps.workforce.models import WorkerProfile

from .utils import BookingScenarioMixin, future_day, local_dt, utc_iso


class PublicPortalTests(BookingScenarioMixin, TestCase):
    def setUp(self):
        self.build_scenario()
        self.public = APIClient()
        self.slug = self.company.slug

    def url(self, suffix=""):
        return f"/api/v1/public/{self.slug}/{suffix}"

    def public_payload(self, start_at=None, **overrides):
        start = start_at or local_dt(self.day, 10)
        payload = {
            "branch": str(self.branch.id), "service": str(self.service.id),
            "worker": str(self.worker.id),
            "start_at": start.isoformat() if hasattr(start, "isoformat") else start,
            "first_name": "María", "last_name": "López",
            "email": "maria@example.com", "phone": "+56911111111",
        }
        payload.update(overrides)
        return payload

    def public_booking(self, start_at=None, **overrides):
        return self.public.post(self.url("bookings/"), self.public_payload(start_at, **overrides), format="json")

    def public_availability(self, **overrides):
        params = {
            "branch": str(self.branch.id), "service": str(self.service.id),
            "worker": str(self.worker.id), "date": self.day.isoformat(),
        }
        params.update(overrides)
        return self.public.get(self.url("availability/"), params)

    def test_public_profile_exposes_only_public_data(self):
        response = self.public.get(self.url())
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["name"], "Agenda A")
        self.assertEqual(response.data["branches"][0]["timezone"], "America/Santiago")
        self.assertEqual(response.data["services"][0]["duration_minutes"], 30)
        self.assertEqual(response.data["services"][0]["price"], "15000.00")
        worker = response.data["workers"][0]
        self.assertEqual(worker["display_name"], "Ana Paz")
        self.assertNotIn("email", worker)
        self.assertNotIn("membership", worker)
        self.assertEqual(worker["branch_ids"], [str(self.branch.id)])

    def test_public_company_is_hidden_when_suspended_or_missing(self):
        self.assertEqual(self.public.get("/api/v1/public/no-existe/").status_code, 404)
        self.company.status = Company.Status.SUSPENDED
        self.company.save(update_fields=["status"])
        self.assertEqual(self.public.get(self.url()).status_code, 404)
        self.company.status = Company.Status.ACTIVE
        self.company.save(update_fields=["status"])
        self.assertEqual(self.public.get(self.url()).status_code, 200)

    def test_public_availability_returns_local_slots_and_validates_ranges(self):
        response = self.public_availability()
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(len(response.data["slots"]), 15)
        self.assertEqual(response.data["slots"][0]["label"], "09:00")
        self.assertEqual(response.data["slots"][0]["start_at"], utc_iso(local_dt(self.day, 9)))

        past = self.public_availability(date=(future_day(-1)).isoformat())
        self.assertEqual(past.status_code, 400)
        far = self.public_availability(date=(future_day(120)).isoformat())
        self.assertEqual(far.status_code, 400)

        foreign = Branch.objects.create(company=make_company("agenda-b", "Agenda B"), name="Otra", code="OTRA")
        self.assertEqual(self.public_availability(branch=str(foreign.id)).status_code, 400)

        unassigned = WorkerProfile.objects.create(company=self.company, first_name="Sin Sucursal")
        self.assertEqual(self.public_availability(worker=str(unassigned.id)).status_code, 400)

    def test_public_booking_creates_customer_and_sends_notification(self):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.public_booking()
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(len(response.data["public_code"]), 10)
        self.assertEqual(response.data["status"], "scheduled")
        self.assertEqual(response.data["branch_timezone"], "America/Santiago")

        booking = Booking.objects.get()
        self.assertEqual(booking.source, Booking.Source.PUBLIC)
        self.assertIsNone(booking.created_by)
        self.assertEqual(booking.start_at, local_dt(self.day, 10))
        customer = Customer.objects.get(email="maria@example.com")
        self.assertEqual(customer.company, self.company)
        self.assertEqual(customer.first_name, "María")
        notification = Notification.objects.get(booking=booking)
        self.assertEqual(notification.status, Notification.Status.SENT)
        self.assertEqual(len(mail.outbox), 1)

        detail = self.public.get(self.url(f"bookings/{response.data['public_code']}/"))
        self.assertEqual(detail.status_code, 200, detail.data)
        self.assertEqual(detail.data["public_code"], response.data["public_code"])
        self.assertEqual(
            self.public.get(self.url(f"bookings/{response.data['public_code'].lower()}/")).status_code, 200,
        )

    def test_public_booking_reuses_customer_and_rejects_conflicts(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.public_booking(local_dt(self.day, 10)).status_code, 201)
            self.assertEqual(self.public_booking(local_dt(self.day, 11)).status_code, 201)
        self.assertEqual(Customer.objects.filter(email="maria@example.com").count(), 1)

        self.assertEqual(self.public_booking(local_dt(self.day, 10)).status_code, 409)
        self.assertEqual(self.public_booking(local_dt(self.day, 10, 7)).status_code, 409)
        self.assertEqual(Booking.objects.count(), 2)

    def test_public_cancel_frees_the_slot_and_notifies(self):
        with self.captureOnCommitCallbacks(execute=True):
            created = self.public_booking()
        self.assertEqual(created.status_code, 201, created.data)
        code = created.data["public_code"]
        self.assertNotIn("10:00", [slot["label"] for slot in self.public_availability().data["slots"]])

        with self.captureOnCommitCallbacks(execute=True):
            canceled = self.public.post(self.url(f"bookings/{code}/cancel/"), {"reason": "Imprevisto"}, format="json")
        self.assertEqual(canceled.status_code, 200, canceled.data)
        self.assertEqual(canceled.data["status"], "canceled")
        booking = Booking.objects.get(public_code=code)
        self.assertEqual(booking.canceled_reason, "Imprevisto")
        self.assertEqual(Notification.objects.filter(booking=booking, kind="booking_canceled").count(), 1)
        self.assertIn("10:00", [slot["label"] for slot in self.public_availability().data["slots"]])

        self.assertEqual(
            self.public.post(self.url(f"bookings/{code}/cancel/"), {}, format="json").status_code, 409,
        )

    def test_public_cannot_cancel_a_started_booking(self):
        with self.captureOnCommitCallbacks(execute=True):
            created = self.public_booking()
        booking = Booking.objects.get(public_code=created.data["public_code"])
        past = timezone.now() - timedelta(hours=1)
        booking.start_at = past
        booking.end_at = past + timedelta(minutes=30)
        booking.block_start = past
        booking.block_end = past + timedelta(minutes=30)
        booking.save(update_fields=["start_at", "end_at", "block_start", "block_end"])
        response = self.public.post(self.url(f"bookings/{booking.public_code}/cancel/"), {}, format="json")
        self.assertEqual(response.status_code, 409, response.data)

    def test_public_booking_rejects_foreign_and_inactive_targets(self):
        other = make_company("agenda-b", "Agenda B")
        foreign_branch = Branch.objects.create(company=other, name="Otra", code="OTRA")
        foreign_service = Service.objects.create(company=other, name="Corte", duration_minutes=30)
        foreign_worker = WorkerProfile.objects.create(company=other, first_name="Ajeno")

        for field, value in [("branch", foreign_branch), ("service", foreign_service),
                             ("worker", foreign_worker)]:
            response = self.public_booking(**{field: str(value.id)})
            self.assertEqual(response.status_code, 400, (field, response.data))
        self.assertEqual(Booking.objects.count(), 0)

        second_branch = Branch.objects.create(company=self.company, name="Norte", code="NORTE")
        self.service.branches.add(second_branch)
        self.assertEqual(self.public_booking(branch=str(self.branch.id)).status_code, 400)
        self.service.branches.clear()

        self.worker.active = False
        self.worker.save(update_fields=["active"])
        self.assertEqual(self.public_booking().status_code, 400)

    def test_public_booking_codes_are_not_visible_across_companies(self):
        with self.captureOnCommitCallbacks(execute=True):
            created = self.public_booking()
        code = created.data["public_code"]
        make_company("agenda-b", "Agenda B")
        response = self.public.get(f"/api/v1/public/agenda-b/bookings/{code}/")
        self.assertEqual(response.status_code, 404)
