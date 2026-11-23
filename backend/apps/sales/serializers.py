from decimal import Decimal

from rest_framework import serializers

from apps.customers.models import Customer
from apps.catalog.models import Service
from apps.inventory.models import Product, Warehouse
from apps.tenancy.models import Branch

from .models import CashSession, Expense, PaymentRecord, Sale, SaleLine


class RejectCompanyMixin:
    def to_internal_value(self, data):
        if "company" in data:
            raise serializers.ValidationError({"company": "La empresa se asigna desde el contexto autenticado."})
        return super().to_internal_value(data)


class PaymentSerializer(serializers.ModelSerializer):
    company = serializers.UUIDField(source="company_id", read_only=True)
    sale_number = serializers.CharField(source="sale.number", read_only=True)
    method_display = serializers.CharField(source="get_method_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    cash_session_number = serializers.CharField(
        source="cash_session.number", read_only=True, allow_null=True,
    )
    created_by_email = serializers.EmailField(source="created_by.email", read_only=True, allow_null=True)

    class Meta:
        model = PaymentRecord
        fields = ["id", "company", "sale", "sale_number", "cash_session",
                  "cash_session_number", "method", "method_display", "amount", "reference",
                  "status", "status_display", "refunded_at", "created_by_email", "created_at"]
        read_only_fields = fields


class SaleLineSerializer(serializers.ModelSerializer):
    product_name = serializers.SerializerMethodField()
    service_name = serializers.SerializerMethodField()
    kind_display = serializers.CharField(source="get_kind_display", read_only=True)
    line_total = serializers.DecimalField(max_digits=18, decimal_places=2, read_only=True)

    class Meta:
        model = SaleLine
        fields = ["id", "kind", "kind_display", "product", "product_name", "service",
                  "service_name", "description", "sku", "quantity", "unit_price",
                  "unit_cost", "line_total"]
        read_only_fields = fields

    def get_product_name(self, obj):
        return obj.product.name if obj.product_id else None

    def get_service_name(self, obj):
        return obj.service.name if obj.service_id else None


class SaleSerializer(serializers.ModelSerializer):
    company = serializers.UUIDField(source="company_id", read_only=True)
    branch_name = serializers.CharField(source="branch.name", read_only=True)
    customer_name = serializers.SerializerMethodField()
    warehouse_name = serializers.CharField(source="warehouse.name", read_only=True, allow_null=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    subtotal = serializers.DecimalField(max_digits=18, decimal_places=2, read_only=True)
    total = serializers.DecimalField(max_digits=18, decimal_places=2, read_only=True)
    paid_total = serializers.DecimalField(max_digits=18, decimal_places=2, read_only=True)
    balance = serializers.DecimalField(max_digits=18, decimal_places=2, read_only=True)
    created_by_email = serializers.EmailField(source="created_by.email", read_only=True, allow_null=True)
    lines = SaleLineSerializer(many=True, read_only=True)
    payments = PaymentSerializer(many=True, read_only=True)

    class Meta:
        model = Sale
        fields = ["id", "company", "number", "branch", "branch_name", "customer", "customer_name",
                  "warehouse", "warehouse_name", "status", "status_display", "subtotal", "discount",
                  "total", "paid_total", "balance", "notes", "completed_at", "canceled_at",
                  "canceled_reason", "created_by_email", "lines", "payments", "created_at",
                  "updated_at"]
        read_only_fields = fields

    def get_customer_name(self, obj):
        return str(obj.customer) if obj.customer_id else None


class SaleLineInputSerializer(RejectCompanyMixin, serializers.Serializer):
    product = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(), required=False, allow_null=True,
    )
    service = serializers.PrimaryKeyRelatedField(
        queryset=Service.objects.all(), required=False, allow_null=True,
    )
    quantity = serializers.DecimalField(max_digits=14, decimal_places=3, min_value=Decimal("0.001"))
    unit_price = serializers.DecimalField(
        max_digits=14, decimal_places=2, min_value=Decimal("0"),
        required=False, allow_null=True,
    )

    def validate(self, attrs):
        if (attrs.get("product") is None) == (attrs.get("service") is None):
            raise serializers.ValidationError(
                "Cada línea debe indicar un producto o un servicio, no ambos."
            )
        return attrs


class SaleWriteSerializer(RejectCompanyMixin, serializers.Serializer):
    branch = serializers.PrimaryKeyRelatedField(queryset=Branch.objects.all())
    customer = serializers.PrimaryKeyRelatedField(
        queryset=Customer.objects.all(), required=False, allow_null=True,
    )
    warehouse = serializers.PrimaryKeyRelatedField(
        queryset=Warehouse.objects.all(), required=False, allow_null=True,
    )
    discount = serializers.DecimalField(
        max_digits=18, decimal_places=2, min_value=Decimal("0"), required=False, default=Decimal("0"),
    )
    notes = serializers.CharField(required=False, allow_blank=True, max_length=2000)
    lines = SaleLineInputSerializer(many=True, allow_empty=False)

    def validate(self, attrs):
        if self.instance is not None and "lines" in self.initial_data:
            raise serializers.ValidationError(
                {"lines": "Anula la venta y crea una nueva para cambiar las líneas."}
            )
        if (self.instance is not None and "branch" in attrs
                and attrs["branch"] != self.instance.branch):
            raise serializers.ValidationError(
                {"branch": "La sucursal de una venta no se puede cambiar."}
            )
        return attrs


class PaymentInputSerializer(RejectCompanyMixin, serializers.Serializer):
    method = serializers.ChoiceField(choices=PaymentRecord.Method.choices)
    amount = serializers.DecimalField(max_digits=18, decimal_places=2, min_value=Decimal("0.01"))
    reference = serializers.CharField(required=False, allow_blank=True, max_length=120)
    cash_session = serializers.PrimaryKeyRelatedField(
        queryset=CashSession.objects.all(), required=False, allow_null=True,
    )


class CompleteSaleSerializer(RejectCompanyMixin, serializers.Serializer):
    payments = PaymentInputSerializer(many=True, required=False, default=list)


class ReasonSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, max_length=240)


class CashSessionSerializer(serializers.ModelSerializer):
    company = serializers.UUIDField(source="company_id", read_only=True)
    branch_name = serializers.CharField(source="branch.name", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    cash_sales_total = serializers.DecimalField(max_digits=18, decimal_places=2, read_only=True)
    cash_expenses_total = serializers.DecimalField(max_digits=18, decimal_places=2, read_only=True)
    expected_cash = serializers.DecimalField(max_digits=18, decimal_places=2, read_only=True)
    opened_by_email = serializers.EmailField(source="opened_by.email", read_only=True, allow_null=True)
    closed_by_email = serializers.EmailField(source="closed_by.email", read_only=True, allow_null=True)

    class Meta:
        model = CashSession
        fields = ["id", "company", "number", "branch", "branch_name", "status", "status_display",
                  "opening_amount", "cash_sales_total", "cash_expenses_total", "expected_cash",
                  "closing_amount", "expected_amount", "difference", "opened_at", "closed_at",
                  "notes", "closing_notes", "opened_by_email", "closed_by_email", "created_at"]
        read_only_fields = fields


class OpenCashSessionSerializer(RejectCompanyMixin, serializers.Serializer):
    branch = serializers.PrimaryKeyRelatedField(queryset=Branch.objects.all())
    opening_amount = serializers.DecimalField(
        max_digits=18, decimal_places=2, min_value=Decimal("0"), required=False, default=Decimal("0"),
    )
    notes = serializers.CharField(required=False, allow_blank=True, max_length=2000)


class CloseCashSessionSerializer(RejectCompanyMixin, serializers.Serializer):
    closing_amount = serializers.DecimalField(max_digits=18, decimal_places=2, min_value=Decimal("0"))
    closing_notes = serializers.CharField(required=False, allow_blank=True, max_length=2000)


class ExpenseSerializer(serializers.ModelSerializer):
    company = serializers.UUIDField(source="company_id", read_only=True)
    branch_name = serializers.CharField(source="branch.name", read_only=True)
    cash_session_number = serializers.CharField(
        source="cash_session.number", read_only=True, allow_null=True,
    )
    method_display = serializers.CharField(source="get_method_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    created_by_email = serializers.EmailField(source="created_by.email", read_only=True, allow_null=True)

    class Meta:
        model = Expense
        fields = ["id", "company", "number", "branch", "branch_name", "cash_session",
                  "cash_session_number", "category", "description", "amount", "method",
                  "method_display", "reference", "incurred_at", "status", "status_display",
                  "canceled_at", "canceled_reason", "created_by_email", "created_at", "updated_at"]
        read_only_fields = fields


class ExpenseWriteSerializer(RejectCompanyMixin, serializers.Serializer):
    branch = serializers.PrimaryKeyRelatedField(queryset=Branch.objects.all())
    cash_session = serializers.PrimaryKeyRelatedField(
        queryset=CashSession.objects.all(), required=False, allow_null=True,
    )
    category = serializers.CharField(max_length=120)
    description = serializers.CharField(required=False, allow_blank=True, max_length=2000)
    amount = serializers.DecimalField(max_digits=18, decimal_places=2, min_value=Decimal("0.01"))
    method = serializers.ChoiceField(choices=Expense.Method.choices)
    reference = serializers.CharField(required=False, allow_blank=True, max_length=120)
    incurred_at = serializers.DateTimeField(required=False, allow_null=True)
