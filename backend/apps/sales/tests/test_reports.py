from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.identity.models import Membership, PermissionGrant
from apps.sales.models import CashSession, Sale

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
