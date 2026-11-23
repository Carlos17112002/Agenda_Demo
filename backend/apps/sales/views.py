from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.tenancy.api import TenantModelViewSet

from .models import CashSession, Expense, PaymentRecord, Sale
from .serializers import (
    CashSessionSerializer, CloseCashSessionSerializer, CompleteSaleSerializer,
    ExpenseSerializer, ExpenseWriteSerializer, OpenCashSessionSerializer, PaymentSerializer,
    ReasonSerializer, SaleSerializer, SaleWriteSerializer,
)
from .services import (
    cancel_expense, cancel_sale, close_cash_session, complete_sale, create_expense,
    create_sale, open_cash_session, update_sale,
)

SALE_READ = {"list": "sales.read", "retrieve": "sales.read"}
SALE_WRITE = {
    "create": "sales.write", "update": "sales.write", "partial_update": "sales.write",
    "complete": "sales.write", "cancel": "sales.write",
}
CASH_READ = {"list": "cash.read", "retrieve": "cash.read"}
CASH_WRITE = {
    "create": "cash.manage", "update": "cash.manage", "partial_update": "cash.manage",
    "close": "cash.manage",
}
EXPENSE_READ = {"list": "expenses.read", "retrieve": "expenses.read"}
EXPENSE_WRITE = {
    "create": "expenses.write", "update": "expenses.write",
    "partial_update": "expenses.write", "cancel": "expenses.write",
}


def _reason(request):
    serializer = ReasonSerializer(data=request.data or {})
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data.get("reason", "")


class SaleViewSet(TenantModelViewSet):
    serializer_class = SaleSerializer
    audit_name = "sale"
    http_method_names = ["get", "post", "patch", "head", "options"]
    permission_map = {**SALE_READ, **SALE_WRITE}
    search_fields = ["number", "customer__first_name", "customer__last_name", "notes"]
    ordering_fields = ["created_at", "completed_at", "total", "number", "status"]

    def get_serializer_class(self):
        if self.action in {"create", "partial_update"}:
            return SaleWriteSerializer
        return SaleSerializer

    def queryset_for_tenant(self, tenant):
        queryset = (Sale.objects.filter(company=tenant)
                    .select_related("branch", "customer", "warehouse", "created_by")
                    .prefetch_related("lines__product", "lines__service", "payments__cash_session"))
        params = self.request.query_params
        if params.get("branch"):
            queryset = queryset.filter(branch_id=params["branch"])
        if params.get("customer"):
            queryset = queryset.filter(customer_id=params["customer"])
        if params.get("warehouse"):
            queryset = queryset.filter(warehouse_id=params["warehouse"])
        if params.get("status") in Sale.Status.values:
            queryset = queryset.filter(status=params["status"])
        if params.get("date_from"):
            queryset = queryset.filter(created_at__date__gte=params["date_from"])
        if params.get("date_to"):
            queryset = queryset.filter(created_at__date__lte=params["date_to"])
        return queryset

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        sale = create_sale(
            company=self.get_tenant(), actor=request.user, **serializer.validated_data,
        )
        return Response(
            SaleSerializer(sale, context=self.get_serializer_context()).data,
            status=status.HTTP_201_CREATED,
        )

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        sale = update_sale(sale=instance, actor=request.user, **serializer.validated_data)
        return Response(SaleSerializer(sale, context=self.get_serializer_context()).data)

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        sale = self.get_object()
        serializer = CompleteSaleSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)
        sale = complete_sale(
            sale=sale, actor=request.user, payments=serializer.validated_data["payments"],
        )
        return Response(SaleSerializer(sale, context=self.get_serializer_context()).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        sale = cancel_sale(
            sale=self.get_object(), actor=request.user, reason=_reason(request),
        )
        return Response(SaleSerializer(sale, context=self.get_serializer_context()).data)


class CashSessionViewSet(TenantModelViewSet):
    serializer_class = CashSessionSerializer
    audit_name = "cash_session"
    http_method_names = ["get", "post", "head", "options"]
    permission_map = {
        **CASH_READ, **CASH_WRITE,
        "update": "cash.manage", "partial_update": "cash.manage", "destroy": "cash.manage",
    }
    search_fields = ["number", "branch__name"]
    ordering_fields = ["opened_at", "closed_at", "number", "status"]

    def queryset_for_tenant(self, tenant):
        queryset = (CashSession.objects.filter(company=tenant)
                    .select_related("branch", "opened_by", "closed_by")
                    .prefetch_related("payments", "expenses"))
        params = self.request.query_params
        if params.get("branch"):
            queryset = queryset.filter(branch_id=params["branch"])
        if params.get("status") in CashSession.Status.values:
            queryset = queryset.filter(status=params["status"])
        if params.get("date_from"):
            queryset = queryset.filter(opened_at__date__gte=params["date_from"])
        if params.get("date_to"):
            queryset = queryset.filter(opened_at__date__lte=params["date_to"])
        return queryset

    def create(self, request, *args, **kwargs):
        serializer = OpenCashSessionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        cash_session = open_cash_session(
            company=self.get_tenant(), actor=request.user, **serializer.validated_data,
        )
        return Response(
            CashSessionSerializer(cash_session, context=self.get_serializer_context()).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"])
    def close(self, request, pk=None):
        cash_session = self.get_object()
        serializer = CloseCashSessionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        cash_session = close_cash_session(
            cash_session=cash_session, actor=request.user, **serializer.validated_data,
        )
        return Response(CashSessionSerializer(cash_session, context=self.get_serializer_context()).data)


class ExpenseViewSet(TenantModelViewSet):
    serializer_class = ExpenseSerializer
    audit_name = "expense"
    http_method_names = ["get", "post", "head", "options"]
    permission_map = {
        **EXPENSE_READ, **EXPENSE_WRITE,
        "update": "expenses.write", "partial_update": "expenses.write", "destroy": "expenses.write",
    }
    search_fields = ["number", "category", "description", "reference", "branch__name"]
    ordering_fields = ["incurred_at", "amount", "number", "created_at"]

    def get_serializer_class(self):
        if self.action == "create":
            return ExpenseWriteSerializer
        return ExpenseSerializer

    def queryset_for_tenant(self, tenant):
        queryset = (Expense.objects.filter(company=tenant)
                    .select_related("branch", "cash_session", "created_by"))
        params = self.request.query_params
        if params.get("branch"):
            queryset = queryset.filter(branch_id=params["branch"])
        if params.get("cash_session"):
            queryset = queryset.filter(cash_session_id=params["cash_session"])
        if params.get("status") in Expense.Status.values:
            queryset = queryset.filter(status=params["status"])
        if params.get("method") in Expense.Method.values:
            queryset = queryset.filter(method=params["method"])
        if params.get("category"):
            queryset = queryset.filter(category__iexact=params["category"])
        if params.get("date_from"):
            queryset = queryset.filter(incurred_at__date__gte=params["date_from"])
        if params.get("date_to"):
            queryset = queryset.filter(incurred_at__date__lte=params["date_to"])
        return queryset

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        expense = create_expense(
            company=self.get_tenant(), actor=request.user, **serializer.validated_data,
        )
        return Response(
            ExpenseSerializer(expense, context=self.get_serializer_context()).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        expense = cancel_expense(
            expense=self.get_object(), actor=request.user, reason=_reason(request),
        )
        return Response(ExpenseSerializer(expense, context=self.get_serializer_context()).data)


class PaymentRecordViewSet(TenantModelViewSet):
    serializer_class = PaymentSerializer
    http_method_names = ["get", "head", "options"]
    permission_map = {"list": "payments.read", "retrieve": "payments.read"}
    search_fields = ["reference", "sale__number"]
    ordering_fields = ["created_at", "amount", "method"]

    def queryset_for_tenant(self, tenant):
        queryset = (PaymentRecord.objects.filter(company=tenant)
                    .select_related("sale", "cash_session", "created_by"))
        params = self.request.query_params
        if params.get("sale"):
            queryset = queryset.filter(sale_id=params["sale"])
        if params.get("cash_session"):
            queryset = queryset.filter(cash_session_id=params["cash_session"])
        if params.get("method") in PaymentRecord.Method.values:
            queryset = queryset.filter(method=params["method"])
        if params.get("status") in PaymentRecord.Status.values:
            queryset = queryset.filter(status=params["status"])
        if params.get("date_from"):
            queryset = queryset.filter(created_at__date__gte=params["date_from"])
        if params.get("date_to"):
            queryset = queryset.filter(created_at__date__lte=params["date_to"])
        return queryset
