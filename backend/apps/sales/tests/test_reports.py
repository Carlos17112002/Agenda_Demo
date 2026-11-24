from datetime import datetime, time, timedelta
from decimal import Decimal
from io import BytesIO
from zoneinfo import ZoneInfo

import openpyxl
from django.test import TestCase
from django.utils import timezone

from apps.bookings.models import Booking
from apps.identity.models import Membership, PermissionGrant
from apps.sales.models import CashSession, Sale
from apps.tenancy.tests.utils import make_context, make_membership, make_user, tenant_client
from apps.workforce.models import WorkerProfile

from .utils import SalesScenarioMixin


class ReportApiTests(SalesScenarioMixin, TestCase):
    def setUp(self):
        self.build_scenario()
        self.today = timezone.localdate().isoformat()
        self.cash = self.open_cash(opening="5000").data
        self.sale_one = self.create_sale().data
        self.complete_cash(self.sale_one["id"], "19000", self.cash["id"])
        self.sale_two = self.create_sale(lines=[
            {"product": str(self.product2.id), "quantity": "2"},
        ]).data
        self.complete_transfer(self.sale_two["id"], "3200")
        self.expense = self.client.post("/api/v1/expenses/", {
            "branch": str(self.branch.id), "cash_session": self.cash["id"],
            "category": "Insumos", "amount": "1000", "method": "cash",
        }, format="json").data
        self.client.post(f"/api/v1/cash-sessions/{self.cash['id']}/close/",
                         {"closing_amount": "23500"}, format="json")

    def report(self, client=None, url=None):
        return (client or self.client).get(
            url or f"/api/v1/reports/sales-summary/?date_from={self.today}&date_to={self.today}"
        )

    def test_sales_summary_totals_and_breakdowns(self):
        response = self.report()
        self.assertEqual(response.status_code, 200, response.data)
        totals = response.data["totals"]
        self.assertEqual(totals["sales"], 2)
        self.assertEqual(totals["subtotal"], "22200.00")
        self.assertEqual(totals["total"], "22200.00")
        self.assertEqual(totals["paid"], "22200.00")
        self.assertEqual(totals["cost"], "3600.00")
        self.assertEqual(totals["profit"], "18600.00")
        self.assertEqual(totals["margin_percent"], "83.78")
        self.assertEqual(totals["average_ticket"], "11100.00")

        methods = {row["method"]: row["amount"] for row in response.data["by_payment_method"]}
        self.assertEqual(methods, {"cash": "19000.00", "transfer": "3200.00"})

        self.assertEqual(len(response.data["by_day"]), 1)
        self.assertEqual(response.data["by_day"][0]["date"], self.today)
        self.assertEqual(response.data["by_day"][0]["total"], "22200.00")

        products = {row["description"]: row for row in response.data["top_products"]}
        self.assertEqual(products["Shampoo"]["total"], "4000.00")
        self.assertEqual(products["Acondicionador"]["total"], "3200.00")
        self.assertEqual(response.data["top_services"][0]["description"], "Corte")
        self.assertEqual(response.data["top_services"][0]["total"], "15000.00")

        self.assertEqual(response.data["by_branch"][0]["total"], "22200.00")

    def test_reports_respect_branch_filter(self):
        response = self.client.get(
            f"/api/v1/reports/sales-summary/?date_from={self.today}&date_to={self.today}"
            f"&branch={self.branch.id}"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["totals"]["sales"], 2)

        foreign = self.foreign_objects()
        response = self.client.get(
            f"/api/v1/reports/sales-summary/?date_from={self.today}&branch={foreign['branch'].id}"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("branch", response.data)

    def test_reports_validate_dates(self):
        response = self.client.get("/api/v1/reports/sales-summary/?date_from=2026-13-01")
        self.assertEqual(response.status_code, 400)
        self.assertIn("date_from", response.data)
        later = (timezone.localdate() + timedelta(days=1)).isoformat()
        response = self.client.get(
            f"/api/v1/reports/sales-summary/?date_from={later}&date_to={self.today}"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("date_to", response.data)

    def test_cash_summary_includes_sessions_and_expenses(self):
        response = self.client.get(
            f"/api/v1/reports/cash-summary/?date_from={self.today}&date_to={self.today}"
        )
        self.assertEqual(response.status_code, 200, response.data)
        totals = response.data["totals"]
        self.assertEqual(totals["sessions"], 1)
        self.assertEqual(totals["closed"], 1)
        self.assertEqual(totals["opening"], "5000.00")
        self.assertEqual(totals["cash_sales"], "19000.00")
        self.assertEqual(totals["cash_expenses"], "1000.00")
        self.assertEqual(totals["expected"], "23000.00")
        self.assertEqual(totals["closing"], "23500.00")
        self.assertEqual(totals["difference"], "500.00")
        self.assertEqual(totals["expenses"], "1000.00")
        self.assertEqual(
            response.data["expenses_by_category"][0],
            {"category": "Insumos", "total": "1000.00"},
        )
        self.assertEqual(response.data["sessions"][0]["number"], self.cash["number"])

    def test_reports_are_isolated_by_tenant(self):
        foreign = self.foreign_objects()
        foreign_sale = Sale.objects.create(
            company=foreign["company"], branch=foreign["branch"],
            status=Sale.Status.COMPLETED, completed_at=timezone.now(),
        )
        foreign_session = CashSession.objects.create(
            company=foreign["company"], branch=foreign["branch"],
            status=CashSession.Status.CLOSED, opening_amount=Decimal("99999"),
        )
        sales = self.report()
        self.assertEqual(sales.data["totals"]["sales"], 2)
        cash = self.client.get(
            f"/api/v1/reports/cash-summary/?date_from={self.today}&date_to={self.today}"
        )
        self.assertEqual(cash.data["totals"]["sessions"], 1)
        self.assertNotIn(str(foreign_sale.id), [row.get("id") for row in sales.data["by_day"]])

    def test_report_permissions(self):
        worker, _, _ = self.role_client(Membership.Role.WORKER, "worker-reports@example.com")
        self.assertEqual(self.report(client=worker).status_code, 403)

        reception, _, _ = self.role_client(Membership.Role.RECEPTION, "reception-reports@example.com")
        self.assertEqual(self.report(client=reception).status_code, 403)

        accounting, membership, _ = self.role_client(
            Membership.Role.ACCOUNTING, "accounting-reports@example.com",
        )
        self.assertEqual(self.report(client=accounting).status_code, 200)
        PermissionGrant.objects.create(
            membership=membership, permission="reports.read", effect="deny",
        )
        self.assertEqual(self.report(client=accounting).status_code, 403)

    def export(self, fmt, client=None, extra=""):
        return (client or self.client).get(
            f"/api/v1/reports/export/?fmt={fmt}"
            f"&date_from={self.today}&date_to={self.today}{extra}"
        )

    def test_export_pdf_returns_attachment(self):
        response = self.export("pdf")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertIn(".pdf", response["Content-Disposition"])
        self.assertTrue(response.content.startswith(b"%PDF"))

    def test_export_excel_returns_workbook(self):
        response = self.export("excel")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response["Content-Type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        self.assertIn(".xlsx", response["Content-Disposition"])
        self.assertTrue(response.content.startswith(b"PK"))
        workbook = openpyxl.load_workbook(BytesIO(response.content))
        self.assertIn("Resumen", workbook.sheetnames)
        self.assertIn("Por trabajador", workbook.sheetnames)
        self.assertIn("Ventas por día", workbook.sheetnames)

    def test_export_rejects_unknown_format(self):
        response = self.export("word")
        self.assertEqual(response.status_code, 400)
        self.assertIn("fmt", response.data)

    def test_export_requires_reports_permission(self):
        worker, _, _ = self.role_client(Membership.Role.WORKER, "worker-export@example.com")
        self.assertEqual(self.export("pdf", client=worker).status_code, 403)


class WorkerReportTests(SalesScenarioMixin, TestCase):
    def setUp(self):
        self.build_scenario()
        self.tz = ZoneInfo("America/Santiago")
        self.day = datetime.now(self.tz).date()
        self.today = self.day.isoformat()

        client_a, membership_a, self.user_a = self.role_client(
            Membership.Role.MANAGER, "ana-soto@example.com",
        )
        self.worker_a = WorkerProfile.objects.create(
            company=self.company, membership=membership_a,
            first_name="Ana", last_name="Soto",
        )
        self.worker_a.branches.set([self.branch])
        self.worker_b = WorkerProfile.objects.create(
            company=self.company, first_name="Beto", last_name="Rojas",
        )
        self.worker_c = WorkerProfile.objects.create(
            company=self.company, first_name="Carla", last_name="Muñoz",
        )

        noon = time(12, 0)
        self.booking(self.worker_a, Booking.Status.COMPLETED, noon)
        self.booking(self.worker_a, Booking.Status.CANCELED, time(13, 0))
        self.booking(self.worker_b, Booking.Status.NO_SHOW, time(14, 0))

        worker_sale = self.create_sale(client=client_a).data
        self.complete_transfer(worker_sale["id"], "19000", client=client_a)
        owner_sale = self.create_sale().data
        self.complete_transfer(owner_sale["id"], "19000")

    def booking(self, worker, status, start_time):
        start = datetime.combine(self.day, start_time, tzinfo=self.tz)
        return Booking.objects.create(
            company=self.company,
            branch=self.branch,
            customer=self.customer,
            service=self.service,
            worker=worker,
            start_at=start,
            end_at=start + timedelta(minutes=30),
            block_start=start,
            block_end=start + timedelta(minutes=30),
            status=status,
            service_name=self.service.name,
            duration_minutes=30,
            price=self.service.price,
        )

    def report(self, extra=""):
        return self.client.get(
            f"/api/v1/reports/sales-summary/?date_from={self.today}&date_to={self.today}{extra}"
        )

    def test_sales_summary_adds_bookings_and_worker_breakdown(self):
        response = self.report()
        self.assertEqual(response.status_code, 200, response.data)
        totals = response.data["totals"]
        self.assertEqual(totals["sales"], 2)
        self.assertEqual(totals["bookings"], {
            "total": 3, "scheduled": 0, "confirmed": 0,
            "completed": 1, "canceled": 1, "no_show": 1,
        })

        rows = {row["worker_name"]: row for row in response.data["by_worker"]}
        ana = rows["Ana Soto"]
        self.assertEqual(ana["bookings"]["completed"], 1)
        self.assertEqual(ana["bookings"]["canceled"], 1)
        self.assertEqual(ana["sales"], 1)
        self.assertEqual(ana["total"], "19000.00")
        self.assertEqual(ana["profit"], "17000.00")
        self.assertEqual(rows["Beto Rojas"]["bookings"]["no_show"], 1)
        self.assertEqual(rows["Beto Rojas"]["sales"], 0)
        self.assertEqual(rows["Carla Muñoz"]["bookings"]["total"], 0)
        self.assertEqual(rows["Sin trabajador"]["sales"], 1)
        self.assertIsNone(rows["Sin trabajador"]["worker"])

    def test_worker_filter_limits_bookings_and_sales(self):
        response = self.report(extra=f"&worker={self.worker_a.id}")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["range"]["worker"], str(self.worker_a.id))
        self.assertEqual(response.data["totals"]["sales"], 1)
        self.assertEqual(response.data["totals"]["bookings"]["total"], 2)
        self.assertEqual(len(response.data["by_worker"]), 1)
        self.assertEqual(response.data["by_worker"][0]["worker_name"], "Ana Soto")

    def test_worker_must_belong_to_active_company(self):
        foreign = self.foreign_objects()
        foreign_worker = WorkerProfile.objects.create(
            company=foreign["company"], first_name="Externo",
        )
        response = self.report(extra=f"&worker={foreign_worker.id}")
        self.assertEqual(response.status_code, 400)
        self.assertIn("worker", response.data)

        response = self.report(extra="&worker=no-es-uuid")
        self.assertEqual(response.status_code, 400)
        self.assertIn("worker", response.data)

    def test_export_includes_worker_data(self):
        response = self.client.get(
            f"/api/v1/reports/export/?fmt=excel"
            f"&date_from={self.today}&date_to={self.today}&worker={self.worker_a.id}"
        )
        self.assertEqual(response.status_code, 200)
        workbook = openpyxl.load_workbook(BytesIO(response.content))
        sheet = workbook["Por trabajador"]
        names = [cell.value for cell in sheet[1]]
        self.assertEqual(names, [
            "Trabajador", "Citas", "Completadas", "Canceladas", "No asistió",
            "Ventas", "Total vendido", "Ganancia",
        ])
        self.assertEqual(sheet["A2"].value, "Ana Soto")
