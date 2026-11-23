from django.contrib import admin

from apps.identity.admin_access import has_saas_access

from .models import Invoice, Payment, Plan, PlanFeature, Subscription


def saas_admin(user):
    return has_saas_access(user)


class PlanFeatureInline(admin.TabularInline):
    model = PlanFeature
    extra = 0


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "price", "currency", "billing_period",
                    "trial_days", "active", "is_default", "sort_order")
    list_filter = ("active", "is_default", "billing_period", "currency")
    search_fields = ("name", "code")
    readonly_fields = ("id", "created_at", "updated_at")
    inlines = [PlanFeatureInline]

    def has_module_permission(self, request):
        return saas_admin(request.user)

    def has_view_permission(self, request, obj=None):
        return saas_admin(request.user)

    def has_add_permission(self, request):
        return saas_admin(request.user)

    def has_change_permission(self, request, obj=None):
        return saas_admin(request.user)

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ("company", "plan", "status", "trial_ends_at", "current_period_end",
                    "cancel_at_period_end", "ended_at")
    list_filter = ("status", "cancel_at_period_end", "plan")
    search_fields = ("company__name", "company__slug", "plan__name")
    date_hierarchy = "started_at"
    readonly_fields = [field.name for field in Subscription._meta.fields]

    def get_queryset(self, request):
        queryset = super().get_queryset(request).select_related("company", "plan")
        if saas_admin(request.user):
            return queryset
        return queryset.filter(
            company__memberships__user=request.user,
            company__memberships__active=True,
            company__memberships__role__in=["owner", "admin"],
        ).distinct()

    def has_view_permission(self, request, obj=None):
        if saas_admin(request.user):
            return True
        target = obj.company if obj is not None else None
        queryset = request.user.memberships.filter(active=True, role__in=["owner", "admin"])
        if target is None:
            return queryset.exists()
        return queryset.filter(company=target).exists()

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("paid_at", "company", "subscription", "amount", "currency",
                    "method", "status", "reference")
    list_filter = ("status", "method", "currency")
    search_fields = ("company__name", "reference")
    date_hierarchy = "paid_at"
    readonly_fields = [field.name for field in Payment._meta.fields]

    def get_queryset(self, request):
        queryset = super().get_queryset(request).select_related("company", "subscription")
        if saas_admin(request.user):
            return queryset
        return queryset.filter(
            company__memberships__user=request.user,
            company__memberships__active=True,
            company__memberships__role__in=["owner", "admin", "accounting"],
        ).distinct()

    def has_view_permission(self, request, obj=None):
        if saas_admin(request.user):
            return True
        queryset = request.user.memberships.filter(
            active=True, role__in=["owner", "admin", "accounting"],
        )
        if obj is None:
            return queryset.exists()
        return queryset.filter(company=obj.company).exists()

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("number", "issued_at", "company", "subscription", "total",
                    "currency", "status", "paid_at")
    list_filter = ("status", "currency")
    search_fields = ("number", "company__name", "description")
    date_hierarchy = "issued_at"
    readonly_fields = [field.name for field in Invoice._meta.fields]

    def get_queryset(self, request):
        queryset = super().get_queryset(request).select_related("company", "subscription")
        if saas_admin(request.user):
            return queryset
        return queryset.filter(
            company__memberships__user=request.user,
            company__memberships__active=True,
            company__memberships__role__in=["owner", "admin", "accounting"],
        ).distinct()

    def has_view_permission(self, request, obj=None):
        if saas_admin(request.user):
            return True
        queryset = request.user.memberships.filter(
            active=True, role__in=["owner", "admin", "accounting"],
        )
        if obj is None:
            return queryset.exists()
        return queryset.filter(company=obj.company).exists()

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
