import os

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.static import serve
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView
from apps.identity.member_views import MembershipViewSet
from apps.identity.views import (
    LoginView, LogoutView, PasswordChangeView, PasswordResetConfirmView,
    PasswordResetRequestView,
)
from apps.bookings.public import (
    PublicAvailabilityView, PublicBookingCancelView, PublicBookingCreateView,
    PublicBookingDetailView, PublicCompanyView,
)
from apps.bookings.public_page import PublicBookingPageView
from apps.billing.views import (
    PublicPlanViewSet, SaasCompanyViewSet, SaasInvoiceViewSet, SaasPaymentViewSet,
    SaasPlanViewSet, SaasSubscriptionViewSet, SaasSummaryView, SubscriptionInvoiceViewSet,
    SubscriptionPaymentViewSet, SubscriptionViewSet,
)
from apps.bookings.views import BookingViewSet
from apps.catalog.views import ServiceViewSet
from apps.customers.views import CustomerViewSet
from apps.inventory.views import (
    CategoryViewSet, DocumentViewSet, InventoryMovementViewSet, ProductViewSet,
    PurchaseOrderViewSet, StockBalanceViewSet, StocktakeViewSet, SupplierViewSet,
    TransferViewSet, WarehouseViewSet,
)
from apps.reports.views import CashSummaryView, SalesSummaryView
from apps.mobile.views import (
    MobileBootstrapView, MobileDeviceDetailView, MobileDeviceView,
    MobileNotificationReadAllView, MobileNotificationReadView,
    MobileNotificationView, MobileOperationView, MobileSyncView,
)
from apps.sales.views import (
    CashSessionViewSet, ExpenseViewSet, PaymentRecordViewSet, SaleViewSet,
)
from apps.tenancy.views import (
    BranchViewSet, CompanyBrandingView, CompanyLogoView, CompanyRegistrationView,
    MyCompaniesView, PermissionGrantViewSet, TenantContextViewSet,
)
from apps.workforce.views import (
    BlockedSlotViewSet, BreakViewSet, TimeOffViewSet, WorkerProfileViewSet, WorkingHoursViewSet,
)

router = DefaultRouter()
router.register("tenant-contexts", TenantContextViewSet, basename="tenant-context")
router.register("companies/mine", MyCompaniesView, basename="my-companies")
router.register("branches", BranchViewSet, basename="branch")
router.register("members", MembershipViewSet, basename="member")
router.register("permission-grants", PermissionGrantViewSet, basename="permission-grant")
router.register("customers", CustomerViewSet, basename="customer")
router.register("services", ServiceViewSet, basename="service")
router.register("workers", WorkerProfileViewSet, basename="worker")
router.register("working-hours", WorkingHoursViewSet, basename="working-hours")
router.register("time-off", TimeOffViewSet, basename="time-off")
router.register("breaks", BreakViewSet, basename="break")
router.register("blocked-slots", BlockedSlotViewSet, basename="blocked-slot")
router.register("bookings", BookingViewSet, basename="booking")
router.register("purchases", PurchaseOrderViewSet, basename="purchase-order")
router.register("sales", SaleViewSet, basename="sale")
router.register("cash-sessions", CashSessionViewSet, basename="cash-session")
router.register("expenses", ExpenseViewSet, basename="expense")
router.register("payments", PaymentRecordViewSet, basename="payment")
router.register("plans", PublicPlanViewSet, basename="public-plan")
router.register("subscription", SubscriptionViewSet, basename="subscription")
router.register("subscription/payments", SubscriptionPaymentViewSet, basename="subscription-payment")
router.register("subscription/invoices", SubscriptionInvoiceViewSet, basename="subscription-invoice")

saas_router = DefaultRouter()
saas_router.register("plans", SaasPlanViewSet, basename="saas-plan")
saas_router.register("subscriptions", SaasSubscriptionViewSet, basename="saas-subscription")
saas_router.register("payments", SaasPaymentViewSet, basename="saas-payment")
saas_router.register("invoices", SaasInvoiceViewSet, basename="saas-invoice")
saas_router.register("companies", SaasCompanyViewSet, basename="saas-company")

inventory_router = DefaultRouter()
inventory_router.register("categories", CategoryViewSet, basename="inventory-category")
inventory_router.register("products", ProductViewSet, basename="inventory-product")
inventory_router.register("warehouses", WarehouseViewSet, basename="inventory-warehouse")
inventory_router.register("suppliers", SupplierViewSet, basename="inventory-supplier")
inventory_router.register("stock", StockBalanceViewSet, basename="inventory-stock")
inventory_router.register("movements", InventoryMovementViewSet, basename="inventory-movement")
inventory_router.register("transfers", TransferViewSet, basename="inventory-transfer")
inventory_router.register("stocktakes", StocktakeViewSet, basename="inventory-stocktake")
inventory_router.register("documents", DocumentViewSet, basename="inventory-document")

urlpatterns = [
    path(f"{settings.ADMIN_PATH}/", admin.site.urls),
    path("api/v1/auth/token/", LoginView.as_view(), name="token_obtain_pair"),
    path("api/v1/auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/v1/auth/logout/", LogoutView.as_view(), name="logout"),
    path("api/v1/auth/password-reset/", PasswordResetRequestView.as_view(), name="password-reset"),
    path("api/v1/auth/password-reset/confirm/", PasswordResetConfirmView.as_view(), name="password-reset-confirm"),
    path("api/v1/auth/password/change/", PasswordChangeView.as_view(), name="password-change"),
    path("api/v1/auth/register-company/", CompanyRegistrationView.as_view({"post": "create"}), name="register-company"),
    path("api/v1/company/branding/", CompanyBrandingView.as_view(), name="company-branding"),
    path("api/v1/company/branding/logo/", CompanyLogoView.as_view(), name="company-branding-logo"),
    path("api/v1/public/<slug:slug>/", PublicCompanyView.as_view(), name="public-company"),
    path("api/v1/public/<slug:slug>/availability/", PublicAvailabilityView.as_view(), name="public-availability"),
    path("api/v1/public/<slug:slug>/bookings/", PublicBookingCreateView.as_view(), name="public-booking-create"),
    path("api/v1/public/<slug:slug>/bookings/<str:code>/", PublicBookingDetailView.as_view(), name="public-booking-detail"),
    path("api/v1/public/<slug:slug>/bookings/<str:code>/cancel/", PublicBookingCancelView.as_view(), name="public-booking-cancel"),
    path("b/<slug:slug>/", PublicBookingPageView.as_view(), name="public-booking-page"),
    path(
        "b/<slug:slug>/reserva/<str:code>/",
        PublicBookingPageView.as_view(), name="public-booking-page-reservation",
    ),
    path("api/v1/inventory/", include(inventory_router.urls)),
    path("api/v1/reports/sales-summary/", SalesSummaryView.as_view(), name="sales-summary"),
    path("api/v1/reports/cash-summary/", CashSummaryView.as_view(), name="cash-summary"),
    path("api/v1/saas/summary/", SaasSummaryView.as_view(), name="saas-summary"),
    path("api/v1/saas/", include(saas_router.urls)),
    path("api/v1/mobile/bootstrap/", MobileBootstrapView.as_view(), name="mobile-bootstrap"),
    path("api/v1/mobile/sync/<str:resource>/", MobileSyncView.as_view(), name="mobile-sync"),
    path("api/v1/mobile/operations/", MobileOperationView.as_view(), name="mobile-operations"),
    path("api/v1/mobile/devices/", MobileDeviceView.as_view(), name="mobile-devices"),
    path(
        "api/v1/mobile/devices/<str:installation_id>/",
        MobileDeviceDetailView.as_view(), name="mobile-device-detail",
    ),
    path(
        "api/v1/mobile/notifications/",
        MobileNotificationView.as_view(), name="mobile-notifications",
    ),
    path(
        "api/v1/mobile/notifications/read-all/",
        MobileNotificationReadAllView.as_view(), name="mobile-notifications-read-all",
    ),
    path(
        "api/v1/mobile/notifications/<uuid:pk>/read/",
        MobileNotificationReadView.as_view(), name="mobile-notification-read",
    ),
    path("api/v1/", include(router.urls)),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
elif os.getenv("AGENDA_SERVE_MEDIA") == "true":
    urlpatterns += [path("media/<path:path>", serve, {"document_root": settings.MEDIA_ROOT})]
