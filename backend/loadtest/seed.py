"""Datos y usuarios para las pruebas de carga (base loadtest.sqlite3).

Uso:
    cd backend
    DJANGO_SETTINGS_MODULE=config.settings_loadtest python loadtest/seed.py
"""
import os
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings_loadtest")

import django  # noqa: E402

django.setup()

from django.conf import settings  # noqa: E402
from django.utils import timezone  # noqa: E402

from apps.bookings.models import Booking  # noqa: E402
from apps.catalog.models import Service  # noqa: E402
from apps.customers.models import Customer  # noqa: E402
from apps.identity.models import Membership, User  # noqa: E402
from apps.tenancy.models import Branch, Company, TenantContext  # noqa: E402
from apps.workforce.models import WorkerProfile  # noqa: E402

COMPANY_SLUG = "estudio-aurora"
USER_COUNT = int(os.getenv("AGENDA_LOADTEST_USERS", "80"))
PASSWORD = "Carga-2026-Agenda!"
CUSTOMER_COUNT = 5000
BOOKING_COUNT = 15000
TZ = ZoneInfo(settings.TIME_ZONE)

FIRST_NAMES = ["Ana", "Bruno", "Carla", "Diego", "Elena", "Felipe", "Gabriela",
               "Hugo", "Inés", "Javier", "Karen", "Luis", "María", "Nicolás",
               "Olivia", "Pablo", "Quimey", "Rocío", "Sofía", "Tomás"]
LAST_NAMES = ["Araya", "Bravo", "Contreras", "Díaz", "Espinoza", "Fuentes",
              "Gómez", "Hernández", "Ibarra", "Jara", "Klein", "López",
              "Muñoz", "Núñez", "Ortiz", "Pérez", "Quezada", "Rojas",
              "Silva", "Torres", "Urrutia", "Vega", "Wright", "Yáñez", "Zúñiga"]


def ensure_users(company, branch):
    users = []
    for index in range(1, USER_COUNT + 1):
        email = f"carga{index:02d}@agenda.app"
        user, _ = User.objects.get_or_create(
            email=email,
            defaults={"username": email, "first_name": f"Carga {index:02d}"},
        )
        user.set_password(PASSWORD)
        user.save(update_fields=["password"])
        Membership.objects.get_or_create(
            company=company, user=user,
            defaults={"role": Membership.Role.OWNER, "default_branch": branch, "active": True},
        )
        users.append(email)
    return users


def ensure_customers(company):
    existing = Customer.objects.filter(company=company).count()
    missing = CUSTOMER_COUNT - existing
    if missing <= 0:
        return
    batch = []
    for index in range(existing + 1, CUSTOMER_COUNT + 1):
        batch.append(Customer(
            company=company,
            first_name=random.choice(FIRST_NAMES),
            last_name=f"{random.choice(LAST_NAMES)} {index}",
            email=f"cliente{index}@ejemplo.cl",
            phone=f"+569{random.randint(10000000, 99999999)}",
        ))
    Customer.objects.bulk_create(batch, batch_size=1000)


def ensure_bookings(company, branch):
    existing = Booking.objects.filter(company=company).count()
    missing = BOOKING_COUNT - existing
    if missing <= 0:
        return
    customers = list(Customer.objects.filter(company=company, active=True))
    services = list(Service.objects.filter(company=company, active=True))
    workers = list(WorkerProfile.objects.filter(company=company, active=True))
    if not (customers and services and workers):
        raise SystemExit("Faltan clientes, servicios o trabajadores para sembrar reservas.")
    today = timezone.localdate()
    batch = []
    for _ in range(missing):
        service = random.choice(services)
        offset = random.randint(-60, 60)
        day = today + timedelta(days=offset)
        while day.weekday() == 6:
            day += timedelta(days=1)
        start = datetime(day.year, day.month, day.day, random.randint(8, 18),
                         random.choice([0, 15, 30, 45]), tzinfo=TZ)
        end = start + timedelta(minutes=service.duration_minutes)
        status = random.choices(
            [Booking.Status.SCHEDULED, Booking.Status.CONFIRMED,
             Booking.Status.COMPLETED, Booking.Status.CANCELED, Booking.Status.NO_SHOW],
            weights=[30, 25, 25, 15, 5],
        )[0]
        batch.append(Booking(
            company=company, branch=branch,
            customer=random.choice(customers), service=service,
            worker=random.choice(workers),
            start_at=start, end_at=end, block_start=start, block_end=end,
            status=status, source=Booking.Source.STAFF,
            service_name=service.name, duration_minutes=service.duration_minutes,
            price=service.price, buffer_before_minutes=0, buffer_after_minutes=0,
        ))
    Booking.objects.bulk_create(batch, batch_size=1000)


def main():
    company = Company.objects.get(slug=COMPANY_SLUG)
    branch = Branch.objects.filter(company=company).order_by("name").first()
    if branch is None:
        raise SystemExit("La empresa demo no tiene sucursales.")
    users = ensure_users(company, branch)
    ensure_customers(company)
    ensure_bookings(company, branch)
    TenantContext.objects.all().delete()
    print(f"Usuarios de carga: {len(users)} (ejemplo: {users[0]} / {PASSWORD})")
    print(f"Clientes: {Customer.objects.filter(company=company).count()}")
    print(f"Reservas: {Booking.objects.filter(company=company).count()}")
    print(f"Sucursal: {branch.name} ({branch.pk}) | Empresa: {company.name} ({company.pk})")


if __name__ == "__main__":
    sys.exit(main())
