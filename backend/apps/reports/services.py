from datetime import date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db.models import Count, DecimalField, ExpressionWrapper, F, Sum
from django.db.models.functions import Round, TruncDate
from rest_framework.exceptions import ValidationError

from apps.sales.models import CashSession, Expense, PaymentRecord, Sale, SaleLine

MONEY_FIELD = DecimalField(max_digits=18, decimal_places=4)


def parse_report_date(value, field):
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise ValidationError({field: "Usa el formato de fecha YYYY-MM-DD."}) from error


def _timezone_for(branch):
    return ZoneInfo(branch.timezone if branch is not None else settings.TIME_ZONE)


def _bounds(date_from, date_to, tzinfo):
    start = datetime.combine(date_from, time.min, tzinfo=tzinfo) if date_from else None
    end = datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=tzinfo) if date_to else None
    return start, end


def _money(value):
    return str((value or Decimal("0")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _quantity(value):
    return str((value or Decimal("0")).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP))


def _percent(value):
    return str((value or Decimal("0")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _line_gross():
    return ExpressionWrapper(
        Round(F("quantity") * F("unit_price"), precision=2), output_field=MONEY_FIELD,
    )


def _line_cost():
    return ExpressionWrapper(
        Round(F("quantity") * F("unit_cost"), precision=2), output_field=MONEY_FIELD,
    )


def sales_summary(*, company, date_from=None, date_to=None, branch=None):
    tzinfo = _timezone_for(branch)
    start, end = _bounds(date_from, date_to, tzinfo)

    sales = Sale.objects.filter(company=company, status=Sale.Status.COMPLETED)
    if branch is not None:
        sales = sales.filter(branch=branch)
    if start is not None:
        sales = sales.filter(completed_at__gte=start)
    if end is not None:
        sales = sales.filter(completed_at__lt=end)

    lines = SaleLine.objects.filter(sale__in=sales)
    sales_stats = sales.aggregate(count=Count("id"), discounts=Sum("discount"))
    line_stats = lines.aggregate(subtotal=Sum(_line_gross()), cost=Sum(_line_cost()))
    count = sales_stats["count"] or 0
    subtotal = line_stats["subtotal"] or Decimal("0")
    discounts = sales_stats["discounts"] or Decimal("0")
    cost = line_stats["cost"] or Decimal("0")
    total = subtotal - discounts
    profit = total - cost

    payments = PaymentRecord.objects.filter(
        sale__in=sales, status=PaymentRecord.Status.COMPLETED,
    )
    paid = payments.aggregate(total=Sum("amount"))["total"] or Decimal("0")

    method_labels = dict(PaymentRecord.Method.choices)
    by_method = [
        {
            "method": row["method"],
            "method_display": method_labels.get(row["method"], row["method"]),
            "count": row["count"],
            "amount": _money(row["total"]),
        }
        for row in payments.values("method").annotate(
            count=Count("id"), total=Sum("amount"),
        ).order_by("method")
    ]

    discount_by_day = {
        row["day"]: row["discount"] or Decimal("0")
        for row in sales.annotate(day=TruncDate("completed_at", tzinfo=tzinfo))
        .values("day").annotate(discount=Sum("discount"))
    }
    daily = {}
    for row in (lines.annotate(day=TruncDate("sale__completed_at", tzinfo=tzinfo))
                .values("day").annotate(
                    gross=Sum(_line_gross()), cost=Sum(_line_cost()),
                    count=Count("sale", distinct=True),
                ).order_by("day")):
        discount = discount_by_day.get(row["day"], Decimal("0"))
        daily[row["day"]] = {
            "date": row["day"].isoformat(),
            "sales": row["count"],
            "subtotal": _money(row["gross"]),
            "discounts": _money(discount),
            "total": _money((row["gross"] or Decimal("0")) - discount),
            "cost": _money(row["cost"]),
            "profit": _money((row["gross"] or Decimal("0")) - discount - (row["cost"] or Decimal("0"))),
        }

    branch_gross = {
        row["sale__branch_id"]: row
        for row in lines.values("sale__branch_id").annotate(
            gross=Sum(_line_gross()), cost=Sum(_line_cost()), count=Count("sale", distinct=True),
        )
    }
    by_branch = []
    for row in (sales.values("branch_id", "branch__name")
                .annotate(discounts=Sum("discount"), count=Count("id")).order_by("branch__name")):
        gross_row = branch_gross.get(row["branch_id"], {})
        gross = gross_row.get("gross") or Decimal("0")
        discount = row["discounts"] or Decimal("0")
        by_branch.append({
            "branch": str(row["branch_id"]),
            "branch_name": row["branch__name"],
            "sales": row["count"],
            "subtotal": _money(gross),
            "discounts": _money(discount),
            "total": _money(gross - discount),
            "cost": _money(gross_row.get("cost")),
        })

    def _top(kind):
        rows = (lines.filter(kind=kind)
                .values("product_id", "service_id", "description", "sku")
                .annotate(units=Sum("quantity"), gross=Sum(_line_gross()), cost=Sum(_line_cost()))
                .order_by("-gross")[:10])
        return [
            {
                "product" if kind == SaleLine.Kind.PRODUCT else "service":
                    str(row["product_id"] or row["service_id"]),
                "description": row["description"],
                "sku": row["sku"],
                "quantity": _quantity(row["units"]),
                "total": _money(row["gross"]),
                "cost": _money(row["cost"]),
                "profit": _money((row["gross"] or Decimal("0")) - (row["cost"] or Decimal("0"))),
            }
            for row in rows
        ]

    return {
        "range": {
            "date_from": date_from.isoformat() if date_from else None,
            "date_to": date_to.isoformat() if date_to else None,
            "timezone": tzinfo.key,
            "branch": str(branch.id) if branch is not None else None,
        },
        "totals": {
            "sales": count,
            "subtotal": _money(subtotal),
            "discounts": _money(discounts),
            "total": _money(total),
            "paid": _money(paid),
            "cost": _money(cost),
            "profit": _money(profit),
            "margin_percent": _percent((profit / total * 100) if total else Decimal("0")),
            "average_ticket": _money((total / count) if count else Decimal("0")),
        },
        "by_payment_method": by_method,
        "by_day": list(daily.values()),
        "by_branch": by_branch,
        "top_products": _top(SaleLine.Kind.PRODUCT),
        "top_services": _top(SaleLine.Kind.SERVICE),
    }


def cash_summary(*, company, date_from=None, date_to=None, branch=None):
    tzinfo = _timezone_for(branch)
    start, end = _bounds(date_from, date_to, tzinfo)

    sessions = (CashSession.objects.filter(company=company)
               .select_related("branch").prefetch_related("payments", "expenses"))
    if branch is not None:
        sessions = sessions.filter(branch=branch)
    if start is not None:
        sessions = sessions.filter(opened_at__gte=start)
    if end is not None:
        sessions = sessions.filter(opened_at__lt=end)

    rows = []
    totals = {
        "sessions": 0, "open": 0, "closed": 0,
        "opening": Decimal("0"), "cash_sales": Decimal("0"),
        "cash_expenses": Decimal("0"), "expected": Decimal("0"),
        "closing": Decimal("0"), "difference": Decimal("0"),
    }
    for cash_session in sessions.order_by("-opened_at"):
        cash_sales = sum(
            (payment.amount for payment in cash_session.payments.all()
             if payment.method == PaymentRecord.Method.CASH
             and payment.status == PaymentRecord.Status.COMPLETED),
            Decimal("0"),
        )
        cash_expenses = sum(
            (expense.amount for expense in cash_session.expenses.all()
             if expense.method == Expense.Method.CASH
             and expense.status == Expense.Status.ACTIVE),
            Decimal("0"),
        )
        expected = (cash_session.expected_amount
                    if cash_session.status == CashSession.Status.CLOSED
                    and cash_session.expected_amount is not None
                    else cash_session.opening_amount + cash_sales - cash_expenses)
        difference = cash_session.difference or Decimal("0")

        totals["sessions"] += 1
        totals["open" if cash_session.status == CashSession.Status.OPEN else "closed"] += 1
        totals["opening"] += cash_session.opening_amount
        totals["cash_sales"] += cash_sales
        totals["cash_expenses"] += cash_expenses
        totals["expected"] += expected
        totals["closing"] += cash_session.closing_amount or Decimal("0")
        totals["difference"] += difference

        rows.append({
            "id": str(cash_session.id),
            "number": cash_session.number,
            "branch": str(cash_session.branch_id),
            "branch_name": cash_session.branch.name,
            "status": cash_session.status,
            "opened_at": cash_session.opened_at,
            "closed_at": cash_session.closed_at,
            "opening_amount": _money(cash_session.opening_amount),
            "cash_sales": _money(cash_sales),
            "cash_expenses": _money(cash_expenses),
            "expected": _money(expected),
            "closing_amount": _money(cash_session.closing_amount),
            "difference": _money(difference) if cash_session.status == CashSession.Status.CLOSED else None,
        })

    expenses = Expense.objects.filter(company=company, status=Expense.Status.ACTIVE)
    if branch is not None:
        expenses = expenses.filter(branch=branch)
    if start is not None:
        expenses = expenses.filter(incurred_at__gte=start)
    if end is not None:
        expenses = expenses.filter(incurred_at__lt=end)
    expense_total = expenses.aggregate(total=Sum("amount"))["total"] or Decimal("0")
    by_category = [
        {"category": row["category"], "total": _money(row["total"])}
        for row in expenses.values("category").annotate(total=Sum("amount")).order_by("-total")
    ]
    method_labels = dict(Expense.Method.choices)
    by_method = [
        {
            "method": row["method"],
            "method_display": method_labels.get(row["method"], row["method"]),
            "total": _money(row["total"]),
        }
        for row in expenses.values("method").annotate(total=Sum("amount")).order_by("method")
    ]

    return {
        "range": {
            "date_from": date_from.isoformat() if date_from else None,
            "date_to": date_to.isoformat() if date_to else None,
            "timezone": tzinfo.key,
            "branch": str(branch.id) if branch is not None else None,
        },
        "totals": {
            "sessions": totals["sessions"],
            "open": totals["open"],
            "closed": totals["closed"],
            "opening": _money(totals["opening"]),
            "cash_sales": _money(totals["cash_sales"]),
            "cash_expenses": _money(totals["cash_expenses"]),
            "expected": _money(totals["expected"]),
            "closing": _money(totals["closing"]),
            "difference": _money(totals["difference"]),
            "expenses": _money(expense_total),
        },
        "sessions": rows,
        "expenses_by_category": by_category,
        "expenses_by_method": by_method,
    }
