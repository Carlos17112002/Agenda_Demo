from datetime import datetime, time, timedelta, timezone as dt_timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.utils import timezone

from apps.catalog.models import Service
from apps.customers.models import Customer
from apps.identity.models import Membership
from apps.tenancy.models import Branch
from apps.tenancy.tests.utils import (
    make_company, make_context, make_membership, make_user, tenant_client,
)
from apps.workforce.models import WorkerProfile, WorkingHours

BRANCH_TZ = ZoneInfo("America/Santiago")


def future_day(days=7):
    return timezone.localdate(timezone=BRANCH_TZ) + timedelta(days=days)


def local_dt(day, hour, minute=0, tz=BRANCH_TZ):
    return datetime.combine(day, time(hour, minute), tzinfo=tz)


def utc_iso(value):
    return value.astimezone(dt_timezone.utc).isoformat()


def parse_api_datetime(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class BookingScenarioMixin:
    def build_scenario(self, slug="agenda-a", days_ahead=7, branch_timezone="America/Santiago"):
        self.company = make_company(slug, "Agenda A")
        self.owner = make_user(f"owner-{slug}@example.com")
        make_membership(self.owner, self.company, Membership.Role.OWNER)
        self.client = tenant_client(self.owner, make_context(self.owner, self.company))
        self.branch = Branch.objects.create(
            company=self.company, name="Centro", code="CENTRO", timezone=branch_timezone,
        )
        self.service = Service.objects.create(
            company=self.company, name="Corte", duration_minutes=30, price=Decimal("15000"),
        )
        self.worker = WorkerProfile.objects.create(
            company=self.company, first_name="Ana", last_name="Paz",
        )
        self.worker.branches.add(self.branch)
        self.customer = Customer.objects.create(
            company=self.company, first_name="Luis", last_name="Soto", email="luis@example.com",
        )
        self.day = future_day(days_ahead)
        self.shift = WorkingHours.objects.create(
            company=self.company, worker=self.worker, branch=self.branch,
            weekday=self.day.weekday(), start_time=time(9), end_time=time(13),
        )

    def add_worker(self, first_name="Bruno", email=None, shift=(9, 13)):
        worker = WorkerProfile.objects.create(company=self.company, first_name=first_name)
        worker.branches.add(self.branch)
        WorkingHours.objects.create(
            company=self.company, worker=worker, branch=self.branch, weekday=self.day.weekday(),
            start_time=time(shift[0]), end_time=time(shift[1]),
        )
        if email:
            user = make_user(email)
            membership = make_membership(user, self.company, Membership.Role.WORKER)
            worker.membership = membership
            worker.save(update_fields=["membership"])
            return worker, user, membership
        return worker

    def booking_payload(self, start_at=None, **overrides):
        start = start_at or local_dt(self.day, 10)
        payload = {
            "branch": str(self.branch.id),
            "service": str(self.service.id),
            "worker": str(self.worker.id),
            "customer": str(self.customer.id),
            "start_at": start.isoformat() if hasattr(start, "isoformat") else start,
        }
        payload.update(overrides)
        return payload

    def create_booking(self, start_at=None, client=None, **overrides):
        return (client or self.client).post(
            "/api/v1/bookings/", self.booking_payload(start_at, **overrides), format="json",
        )

    def availability(self, client=None, **overrides):
        params = {
            "branch": str(self.branch.id), "service": str(self.service.id),
            "worker": str(self.worker.id), "date": self.day.isoformat(),
        }
        params.update(overrides)
        return (client or self.client).get("/api/v1/bookings/availability/", params)
