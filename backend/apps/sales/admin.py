from django.contrib import admin

from apps.tenancy.admin import TenantScopedAdmin

from .models import CashSession, Expense, PaymentRecord, Sale, SaleLine


class SaleLineInline(admin.TabularInline):
    model = SaleLine
    extra = 0
    readonly_fields = ("kind", "product", "service", "description", "sku", "quantity",
                       "unit_price", "unit_cost", "created_at", "updated_at")
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


class PaymentInline(admin.TabularInline):
    model = PaymentRecord
    extra = 0
    readonly_fields = ("method", "amount", "reference", "cash_session", "status",
                       "refunded_at", "created_by", "created_at")
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Sale)
class SaleAdmin(TenantScopedAdmin):
    list_display = ("number", "branch", "customer", "status", "total", "completed_at", "company")
    list_filter = ("status", "company", "branch")
    search_fields = ("number", "customer__first_name", "customer__last_name", "notes")
    date_hierarchy = "created_at"
    readonly_fields = [field.name for field in Sale._meta.fields]
    inlines = [SaleLineInline, PaymentInline]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(PaymentRecord)
class PaymentRecordAdmin(TenantScopedAdmin):
    list_display = ("created_at", "sale", "method", "amount", "status", "cash_session", "company")
    list_filter = ("method", "status", "company")
    search_fields = ("sale__number", "reference")
    date_hierarchy = "created_at"
    readonly_fields = [field.name for field in PaymentRecord._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class CashExpenseInline(admin.TabularInline):
    model = Expense
    extra = 0
    fk_name = "cash_session"
    readonly_fields = ("number", "branch", "category", "amount", "method", "status",
                       "incurred_at", "created_at")
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(CashSession)
class CashSessionAdmin(TenantScopedAdmin):
    list_display = ("number", "branch", "status", "opening_amount", "closing_amount",
                    "difference", "opened_at", "closed_at", "company")
    list_filter = ("status", "company", "branch")
    search_fields = ("number", "branch__name")
    date_hierarchy = "opened_at"
    readonly_fields = [field.name for field in CashSession._meta.fields]
    inlines = [PaymentInline, CashExpenseInline]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Expense)
class ExpenseAdmin(TenantScopedAdmin):
    list_display = ("number", "incurred_at", "branch", "category", "amount", "method", "status", "company")
    list_filter = ("status", "method", "company", "branch")
    search_fields = ("number", "category", "description", "reference")
    date_hierarchy = "incurred_at"
    readonly_fields = [field.name for field in Expense._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
