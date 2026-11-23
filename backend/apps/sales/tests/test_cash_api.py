from decimal import Decimal

from django.test import TestCase

from apps.identity.models import Membership
from apps.sales.models import CashSession, Expense

from .utils import SalesScenarioMixin


class CashAndExpenseApiTests(SalesScenarioMixin, TestCase):
    def setUp(self):
        self.build_scenario()

    def test_open_cash_session_and_single_open_per_branch(self):
        response = self.open_cash(opening="5000")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["status"], "open")
        self.assertEqual(response.data["expected_cash"], "5000.00")
        again = self.open_cash(opening="1000")
        self.assertEqual(again.status_code, 409, again.data)
        self.assertEqual(CashSession.objects.filter(
            company=self.company, branch=self.branch, status=CashSession.Status.OPEN).count(), 1)

    def test_cash_sale_and_expense_reconcile_on_close(self):
        cash = self.open_cash(opening="5000").data
        sale = self.create_sale().data
        self.assertEqual(self.complete_cash(sale["id"], "19000", cash["id"]).status_code, 200)

        expense = self.client.post("/api/v1/expenses/", {
            "branch": str(self.branch.id), "cash_session": cash["id"],
            "category": "Insumos", "description": "Shampoo de prueba",
            "amount": "1000", "method": "cash",
        }, format="json")
        self.assertEqual(expense.status_code, 201, expense.data)

        detail = self.client.get(f"/api/v1/cash-sessions/{cash['id']}/")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.data["cash_sales_total"], "19000.00")
        self.assertEqual(detail.data["cash_expenses_total"], "1000.00")
        self.assertEqual(detail.data["expected_cash"], "23000.00")

        closed = self.client.post(f"/api/v1/cash-sessions/{cash['id']}/close/",
                                  {"closing_amount": "23000", "closing_notes": "Cuadra"},
                                  format="json")
        self.assertEqual(closed.status_code, 200, closed.data)
        self.assertEqual(closed.data["status"], "closed")
        self.assertEqual(closed.data["expected_amount"], "23000.00")
        self.assertEqual(closed.data["difference"], "0.00")

        again = self.client.post(f"/api/v1/cash-sessions/{cash['id']}/close/",
                                 {"closing_amount": "1"}, format="json")
        self.assertEqual(again.status_code, 200)
        self.assertEqual(CashSession.objects.get(pk=cash["id"]).closing_amount,
                         Decimal("23000"))

    def test_cash_expense_requires_open_session(self):
        response = self.client.post("/api/v1/expenses/", {
            "branch": str(self.branch.id), "category": "Insumos",
            "amount": "1000", "method": "cash",
        }, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("cash_session", response.data)

    def test_non_cash_expense_without_session_can_be_canceled(self):
        response = self.client.post("/api/v1/expenses/", {
            "branch": str(self.branch.id), "category": "Servicios",
            "amount": "2500", "method": "transfer", "reference": "TRX-9",
        }, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        canceled = self.client.post(f"/api/v1/expenses/{response.data['id']}/cancel/",
                                    {"reason": "Duplicado"}, format="json")
        self.assertEqual(canceled.status_code, 200, canceled.data)
        self.assertEqual(canceled.data["status"], "canceled")

    def test_closed_cash_session_rejects_payments_and_expenses(self):
        cash = self.open_cash(opening="5000").data
        self.client.post(f"/api/v1/cash-sessions/{cash['id']}/close/",
                         {"closing_amount": "5000"}, format="json")
        sale = self.create_sale().data
        payment = self.complete_cash(sale["id"], "19000", cash["id"])
        self.assertEqual(payment.status_code, 409, payment.data)
        expense = self.client.post("/api/v1/expenses/", {
            "branch": str(self.branch.id), "cash_session": cash["id"],
            "category": "Insumos", "amount": "1000", "method": "cash",
        }, format="json")
        self.assertEqual(expense.status_code, 409, expense.data)

    def test_expense_from_closed_cash_session_cannot_be_canceled(self):
        cash = self.open_cash(opening="5000").data
        expense = self.client.post("/api/v1/expenses/", {
            "branch": str(self.branch.id), "cash_session": cash["id"],
            "category": "Insumos", "amount": "1000", "method": "cash",
        }, format="json").data
        self.client.post(f"/api/v1/cash-sessions/{cash['id']}/close/",
                         {"closing_amount": "4000"}, format="json")
        response = self.client.post(f"/api/v1/expenses/{expense['id']}/cancel/", {}, format="json")
        self.assertEqual(response.status_code, 409, response.data)
        self.assertEqual(Expense.objects.get(pk=expense["id"]).status, Expense.Status.ACTIVE)

    def test_cash_and_expenses_are_isolated_by_tenant(self):
        foreign = self.foreign_objects()
        foreign_session = CashSession.objects.create(
            company=foreign["company"], branch=foreign["branch"],
        )
        foreign_expense = Expense.objects.create(
            company=foreign["company"], branch=foreign["branch"], category="B",
            amount=Decimal("10"), method=Expense.Method.TRANSFER,
        )
        self.assertEqual(self.client.get("/api/v1/cash-sessions/").data["results"], [])
        self.assertEqual(self.client.get("/api/v1/expenses/").data["results"], [])
        self.assertEqual(self.client.get(
            f"/api/v1/cash-sessions/{foreign_session.id}/").status_code, 404)
        self.assertEqual(self.client.get(
            f"/api/v1/expenses/{foreign_expense.id}/").status_code, 404)
        response = self.open_cash(branch=foreign["branch"])
        self.assertEqual(response.status_code, 403, response.data)

    def test_commercial_permissions(self):
        worker, _, _ = self.role_client(Membership.Role.WORKER, "worker-cash@example.com")
        self.assertEqual(worker.get("/api/v1/cash-sessions/").status_code, 403)
        self.assertEqual(worker.get("/api/v1/expenses/").status_code, 403)

        accounting, _, _ = self.role_client(Membership.Role.ACCOUNTING, "accounting-cash@example.com")
        self.assertEqual(accounting.get("/api/v1/cash-sessions/").status_code, 200)
        self.assertEqual(accounting.get("/api/v1/expenses/").status_code, 200)
        self.assertEqual(accounting.post("/api/v1/cash-sessions/", {
            "branch": str(self.branch.id), "opening_amount": "0",
        }, format="json").status_code, 403)
        self.assertEqual(accounting.post("/api/v1/expenses/", {
            "branch": str(self.branch.id), "category": "Contable",
            "amount": "500", "method": "transfer",
        }, format="json").status_code, 201)

        reception, membership, _ = self.role_client(Membership.Role.RECEPTION, "reception-cash@example.com")
        self.assertEqual(reception.post("/api/v1/cash-sessions/", {
            "branch": str(self.branch.id), "opening_amount": "1000",
        }, format="json").status_code, 201)

        from apps.identity.models import PermissionGrant
        PermissionGrant.objects.create(
            membership=membership, permission="cash.manage", effect="deny",
        )
        self.assertEqual(reception.post("/api/v1/cash-sessions/", {
            "branch": str(self.branch.id), "opening_amount": "2000",
        }, format="json").status_code, 403)
