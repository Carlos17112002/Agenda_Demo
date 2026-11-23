"""Prueba de carga del panel del operador contra una instancia local.

Uso (4 procesos WSGI en 8001-8004):
    cd backend
    python -m locust -f loadtest/locustfile.py --headless -u 500 -r 10 -t 6m

Antes de cada ejecución vuelve a correr loadtest/seed.py para limpiar los
contextos de empresa activos (máximo 20 por usuario).

Variables opcionales:
    AGENDA_LOADTEST_READONLY=1     omite las tareas de escritura
    AGENDA_LOADTEST_PORTS=8001,... puertos WSGI a repartir entre usuarios
"""
import os
import random
import uuid
from datetime import date, timedelta

from locust import HttpUser, between, events

EMAIL_DOMAIN = "agenda.app"
PASSWORD = "Carga-2026-Agenda!"
COMPANY_SLUG = "estudio-aurora"
PORTS = [int(port) for port in os.getenv("AGENDA_LOADTEST_PORTS", "8001,8002,8003,8004").split(",")]
READONLY = os.getenv("AGENDA_LOADTEST_READONLY") == "1"
USER_COUNT = int(os.getenv("AGENDA_LOADTEST_USERS", "80"))
WAIT_MIN = float(os.getenv("AGENDA_LOADTEST_WAIT_MIN", "1"))
WAIT_MAX = float(os.getenv("AGENDA_LOADTEST_WAIT_MAX", "3"))

conflicts = {"count": 0}
db_locks = {"count": 0}

TASK_WEIGHTS = {
    "bootstrap": 4,
    "agenda_dia": 20,
    "agenda_semana": 10,
    "disponibilidad": 6,
    "clientes_lista": 10,
    "catalogo": 4,
    "equipo": 4,
    "horarios": 3,
    "resumen_ventas": 5,
    "resumen_caja": 4,
    "inventario": 2,
}
if not READONLY:
    TASK_WEIGHTS.update({
        "cliente_crear": 4,
        "reserva_notas": 5,
        "reserva_crear_y_cancelar": 3,
    })


def _results(payload):
    if isinstance(payload, dict):
        return payload.get("results", [])
    return payload or []


def _iso_today(offset_days=0):
    return (date.today() + timedelta(days=offset_days)).isoformat()


class OperadorPanelBase(HttpUser):
    abstract = True
    wait_time = between(WAIT_MIN, WAIT_MAX)
    network_timeout = 30

    def on_start(self):
        self.index = random.randint(1, USER_COUNT)
        self.email = f"carga{self.index:02d}@{EMAIL_DOMAIN}"
        self.booking_ids = []
        self.company_id = None
        self.branch_id = None
        self.service_ids = []
        self.worker_ids = []
        self.customer_ids = []

        response = self.client.post(
            "/api/v1/auth/token/",
            json={"email": self.email, "password": PASSWORD},
            name="login",
        )
        if response.status_code != 200:
            raise RuntimeError(f"Login falló para {self.email}: {response.status_code}")
        self.token = response.json()["access"]
        self.headers = {"Authorization": f"Bearer {self.token}"}

        companies = self.client.get(
            "/api/v1/companies/mine/", headers=self.headers, name="mis-empresas",
        ).json()
        for company in _results(companies):
            if company.get("slug") == COMPANY_SLUG:
                self.company_id = company["id"]
                break
        if self.company_id is None:
            raise RuntimeError("La cuenta de carga no pertenece a la empresa demo.")

        context = self.client.post(
            "/api/v1/tenant-contexts/",
            json={"company": self.company_id},
            headers=self.headers,
            name="contexto-tenant",
        )
        if context.status_code != 201:
            raise RuntimeError(f"Contexto tenant falló: {context.status_code} {context.text}")
        self.headers["X-Tenant-Context"] = context.json()["id"]

        bootstrap = self.client.get(
            "/api/v1/mobile/bootstrap/", headers=self.headers, name="bootstrap",
        ).json()
        branches = bootstrap.get("branches") or []
        if branches:
            self.branch_id = branches[0]["id"]
        self.service_ids = [
            row["id"] for row in _results(self.client.get(
                "/api/v1/services/?page_size=50", headers=self.headers, name="servicios",
            ).json())
        ]
        self.worker_ids = [
            row["id"] for row in _results(self.client.get(
                "/api/v1/workers/?page_size=50", headers=self.headers, name="equipo",
            ).json())
        ]

        if not READONLY:
            created = self.client.post(
                "/api/v1/customers/",
                json={
                    "first_name": f"Carga {self.index}",
                    "last_name": uuid.uuid4().hex[:8],
                    "email": f"carga+{uuid.uuid4().hex}@ejemplo.cl",
                    "phone": "+56911112222",
                },
                headers=self.headers,
                name="cliente-crear",
            )
            if created.status_code == 201:
                self.customer_ids.append(created.json()["id"])

    def _agenda(self, params, name):
        response = self.client.get(
            "/api/v1/bookings/", params=params, headers=self.headers, name=name,
        )
        if response.status_code == 200:
            ids = [row["id"] for row in _results(response.json())]
            if ids:
                self.booking_ids = (ids + self.booking_ids)[:40]
        return response

    def bootstrap(self):
        self.client.get(
            "/api/v1/mobile/bootstrap/", headers=self.headers, name="bootstrap",
        )

    def agenda_dia(self):
        params = {"date": _iso_today(), "page_size": 100}
        if self.branch_id:
            params["branch"] = self.branch_id
        self._agenda(params, "agenda-día")

    def agenda_semana(self):
        params = {
            "date_from": _iso_today(),
            "date_to": _iso_today(6),
            "page_size": 100,
        }
        if self.branch_id:
            params["branch"] = self.branch_id
        self._agenda(params, "agenda-semana")

    def disponibilidad(self):
        if not (self.branch_id and self.service_ids and self.worker_ids):
            return
        self.client.get(
            "/api/v1/bookings/availability/",
            params={
                "branch": self.branch_id,
                "service": random.choice(self.service_ids),
                "worker": random.choice(self.worker_ids),
                "date": _iso_today(random.randint(1, 30)),
            },
            headers=self.headers,
            name="disponibilidad",
        )

    def clientes_lista(self):
        params = {"page_size": 25}
        if random.random() < 0.4:
            params["search"] = random.choice(["a", "e", "o", "n", "ro"])
        self.client.get(
            "/api/v1/customers/", params=params, headers=self.headers, name="clientes",
        )

    def catalogo(self):
        self.client.get(
            "/api/v1/services/?page_size=50", headers=self.headers, name="servicios",
        )

    def equipo(self):
        self.client.get(
            "/api/v1/workers/?page_size=50", headers=self.headers, name="equipo",
        )

    def horarios(self):
        if not self.worker_ids:
            return
        self.client.get(
            "/api/v1/working-hours/",
            params={"worker": random.choice(self.worker_ids)},
            headers=self.headers,
            name="horarios",
        )

    def resumen_ventas(self):
        params = {"date_from": _iso_today(-30), "date_to": _iso_today()}
        if self.branch_id:
            params["branch"] = self.branch_id
        self.client.get(
            "/api/v1/reports/sales-summary/", params=params,
            headers=self.headers, name="resumen-ventas",
        )

    def resumen_caja(self):
        params = {"date_from": _iso_today(-30), "date_to": _iso_today()}
        if self.branch_id:
            params["branch"] = self.branch_id
        self.client.get(
            "/api/v1/reports/cash-summary/", params=params,
            headers=self.headers, name="resumen-caja",
        )

    def inventario(self):
        self.client.get(
            "/api/v1/inventory/products/?page_size=25", headers=self.headers,
            name="inventario",
        )

    def cliente_crear(self):
        self.client.post(
            "/api/v1/customers/",
            json={
                "first_name": f"Cliente {uuid.uuid4().hex[:6]}",
                "last_name": "Carga",
                "email": f"carga+{uuid.uuid4().hex}@ejemplo.cl",
                "phone": "+56922223333",
            },
            headers=self.headers,
            name="cliente-crear",
        )

    def reserva_notas(self):
        if not self.booking_ids:
            return
        self.client.patch(
            f"/api/v1/bookings/{random.choice(self.booking_ids)}/",
            json={"notes": f"Nota de carga {uuid.uuid4().hex[:8]}"},
            headers=self.headers,
            name="reserva-notas",
        )

    def reserva_crear_y_cancelar(self):
        if not (self.branch_id and self.service_ids and self.worker_ids and self.customer_ids):
            return
        service_id = random.choice(self.service_ids)
        worker_id = random.choice(self.worker_ids)
        availability = self.client.get(
            "/api/v1/bookings/availability/",
            params={
                "branch": self.branch_id,
                "service": service_id,
                "worker": worker_id,
                "date": _iso_today(random.randint(1, 45)),
            },
            headers=self.headers,
            name="disponibilidad",
        )
        slots = (availability.json() or {}).get("slots") or [] if availability.status_code == 200 else []
        if not slots:
            return
        with self.client.post(
            "/api/v1/bookings/",
            json={
                "branch": self.branch_id,
                "customer": random.choice(self.customer_ids),
                "service": service_id,
                "worker": worker_id,
                "start_at": random.choice(slots)["start_at"],
                "notes": "Reserva de carga",
            },
            headers=self.headers,
            name="reserva-crear",
            catch_response=True,
        ) as response:
            if response.status_code == 201:
                booking_id = response.json()["id"]
                self.booking_ids = ([booking_id] + self.booking_ids)[:40]
                self.client.post(
                    f"/api/v1/bookings/{booking_id}/cancel/",
                    json={"reason": "Limpieza de carga"},
                    headers=self.headers,
                    name="reserva-cancelar",
                )
            elif response.status_code in (400, 409):
                conflicts["count"] += 1
                response.success()
            elif response.status_code >= 500:
                if "database is locked" in response.text:
                    db_locks["count"] += 1
                    response.failure("SQLite: database is locked")
                else:
                    response.failure(f"Error del servidor: {response.status_code}")


OperadorPanelBase.tasks = {
    getattr(OperadorPanelBase, name): weight for name, weight in TASK_WEIGHTS.items()
}


def _build_user_class(port):
    return type(
        f"OperadorPanel{port}",
        (OperadorPanelBase,),
        {"host": f"http://127.0.0.1:{port}", "weight": 1, "abstract": False, "__module__": __name__},
    )


for _port in PORTS:
    _user_class = _build_user_class(_port)
    globals()[_user_class.__name__] = _user_class
del _user_class


@events.quitting.add_listener
def report_conflicts(environment, **kwargs):
    print(f"Reservas rechazadas por conflicto/cupo: {conflicts['count']}")
    print(f"Escrituras rechazadas por bloqueo SQLite: {db_locks['count']}")
