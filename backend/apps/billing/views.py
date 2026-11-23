from django.db.models import Prefetch
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.services import record_event
from apps.tenancy.authentication import resolve_tenant
from apps.tenancy.branding import booking_url
from apps.tenancy.models import Company
from apps.tenancy.permissions import HasTenantContext, HasTenantPermission
from apps.tenancy.serializers import SaasCompanyCreateSerializer

from .gating import current_subscription
from .models import Invoice, Payment, Plan, Subscription
from .permissions import IsSaasAdmin
from .serializers import (
    CancelSubscriptionSerializer, ChangePlanSerializer, CompanyStatusSerializer,
    InvoiceSerializer, PaymentSerializer, PlanSerializer, PlanWriteSerializer,
    PublicPlanSerializer, RecordPaymentSerializer, SaasCompanySerializer,
    SubscriptionCreateSerializer, SubscriptionSerializer,
)
from .services import (
    cancel_subscription, change_plan, expire_subscription, record_payment,
    resume_subscription, saas_summary, start_subscription,
)


def tenant_of(request):
    tenant = getattr(request, "tenant", None)
    if tenant is None:
        tenant = resolve_tenant(request, request.user)
    if tenant is None:
        raise PermissionDenied("Selecciona una empresa.")
    return tenant


def subscription_payload(subscription):
    subscription = (Subscription.objects.select_related("plan")
                    .prefetch_related("plan__features").get(pk=subscription.pk))
    return SubscriptionSerializer(subscription).data


class PublicPlanViewSet(viewsets.ReadOnlyModelViewSet):
    authentication_classes = []
    permission_classes = [AllowAny]
    serializer_class = PublicPlanSerializer
    queryset = Plan.objects.filter(active=True).prefetch_related("features")

    def get_queryset(self):
        return super().get_queryset().order_by("sort_order", "price", "name")


class SubscriptionViewSet(viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated, HasTenantContext, HasTenantPermission]
    permission_map = {
        "list": "subscription.read",
        "change_plan": "subscription.manage",
        "cancel": "subscription.manage",
        "resume": "subscription.manage",
    }
    serializer_class = SubscriptionSerializer

    def get_required_tenant_permission(self):
        return self.permission_map.get(self.action)

    def get_subscription(self):
        company = tenant_of(self.request)
        subscription = current_subscription(company)
        if subscription is None:
            subscription = (company.subscriptions.select_related("plan")
                            .prefetch_related("plan__features").first())
        if subscription is None:
            raise NotFound("La empresa no tiene una suscripción registrada.")
        return subscription

    def list(self, request):
        return Response(SubscriptionSerializer(self.get_subscription()).data)

    @action(detail=False, methods=["post"], url_path="change-plan")
    def change_plan(self, request):
        serializer = ChangePlanSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        subscription = change_plan(
            self.get_subscription(), serializer.validated_data["plan"], actor=request.user,
        )
        return Response(subscription_payload(subscription))

    @action(detail=False, methods=["post"])
    def cancel(self, request):
        serializer = CancelSubscriptionSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)
        subscription = cancel_subscription(
            self.get_subscription(),
            immediate=serializer.validated_data["immediate"],
            actor=request.user,
        )
        return Response(subscription_payload(subscription))

    @action(detail=False, methods=["post"])
    def resume(self, request):
        subscription = resume_subscription(self.get_subscription(), actor=request.user)
        return Response(subscription_payload(subscription))


class SubscriptionPaymentViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated, HasTenantContext, HasTenantPermission]
    required_tenant_permission = "subscription.read"
    serializer_class = PaymentSerializer
    ordering_fields = ["paid_at", "amount"]

    def get_queryset(self):
        return (Payment.objects.filter(company=tenant_of(self.request))
                .select_related("subscription", "created_by")
                .prefetch_related("invoices"))


class SubscriptionInvoiceViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated, HasTenantContext, HasTenantPermission]
    required_tenant_permission = "subscription.read"
    serializer_class = InvoiceSerializer
    ordering_fields = ["issued_at", "total"]

    def get_queryset(self):
        return Invoice.objects.filter(company=tenant_of(self.request)).select_related("subscription")


class SaasPlanViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, IsSaasAdmin]
    http_method_names = ["get", "post", "patch", "head", "options"]
    queryset = Plan.objects.prefetch_related("features")
    serializer_class = PlanWriteSerializer
    search_fields = ["name", "code"]
    ordering_fields = ["sort_order", "price", "created_at"]

    def get_serializer_class(self):
        if self.action in {"list", "retrieve"}:
            return PlanSerializer
        return PlanWriteSerializer

    def perform_create(self, serializer):
        plan = serializer.save()
        record_event(company=None, actor=self.request.user, action="plan.created",
                     instance=plan, metadata={"code": plan.code})

    def perform_update(self, serializer):
        plan = serializer.save()
        record_event(company=None, actor=self.request.user, action="plan.updated",
                     instance=plan, metadata={"code": plan.code})


class SaasSubscriptionViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin,
                              mixins.CreateModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated, IsSaasAdmin]
    queryset = (Subscription.objects.select_related("company", "plan")
                .prefetch_related("plan__features"))
    serializer_class = SubscriptionSerializer
    search_fields = ["company__name", "company__slug", "plan__name"]
    ordering_fields = ["started_at", "status", "current_period_end"]

    def get_serializer_class(self):
        if self.action == "create":
            return SubscriptionCreateSerializer
        return SubscriptionSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params
        if params.get("company"):
            queryset = queryset.filter(company_id=params["company"])
        if params.get("plan"):
            queryset = queryset.filter(plan_id=params["plan"])
        if params.get("status"):
            queryset = queryset.filter(status=params["status"])
        return queryset

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        subscription = start_subscription(
            data["company"], data["plan"], trial_days=data.get("trial_days"),
            actor=request.user,
        )
        return Response(subscription_payload(subscription), status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="record-payment")
    def record_payment(self, request, pk=None):
        serializer = RecordPaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payment = record_payment(
            self.get_object(), actor=request.user, **serializer.validated_data,
        )
        payment = Payment.objects.prefetch_related("invoices").get(pk=payment.pk)
        return Response({
            "subscription": subscription_payload(payment.subscription),
            "payment": PaymentSerializer(payment).data,
            "invoices": InvoiceSerializer(payment.invoices.all(), many=True).data,
        }, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="change-plan")
    def change_plan(self, request, pk=None):
        serializer = ChangePlanSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        subscription = change_plan(
            self.get_object(), serializer.validated_data["plan"], actor=request.user,
        )
        return Response(subscription_payload(subscription))

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        serializer = CancelSubscriptionSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)
        subscription = cancel_subscription(
            self.get_object(),
            immediate=serializer.validated_data["immediate"],
            actor=request.user,
        )
        return Response(subscription_payload(subscription))

    @action(detail=True, methods=["post"])
    def resume(self, request, pk=None):
        subscription = resume_subscription(self.get_object(), actor=request.user)
        return Response(subscription_payload(subscription))

    @action(detail=True, methods=["post"])
    def expire(self, request, pk=None):
        subscription = expire_subscription(self.get_object(), actor=request.user)
        return Response(subscription_payload(subscription))


class SaasPaymentViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated, IsSaasAdmin]
    serializer_class = PaymentSerializer
    queryset = (Payment.objects.select_related("company", "subscription", "created_by")
                .prefetch_related("invoices"))
    ordering_fields = ["paid_at", "amount"]

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params
        if params.get("company"):
            queryset = queryset.filter(company_id=params["company"])
        if params.get("subscription"):
            queryset = queryset.filter(subscription_id=params["subscription"])
        if params.get("status"):
            queryset = queryset.filter(status=params["status"])
        return queryset


class SaasInvoiceViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated, IsSaasAdmin]
    serializer_class = InvoiceSerializer
    queryset = Invoice.objects.select_related("company", "subscription")
    ordering_fields = ["issued_at", "total"]

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params
        if params.get("company"):
            queryset = queryset.filter(company_id=params["company"])
        if params.get("subscription"):
            queryset = queryset.filter(subscription_id=params["subscription"])
        if params.get("status"):
            queryset = queryset.filter(status=params["status"])
        return queryset


class SaasCompanyViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated, IsSaasAdmin]
    serializer_class = SaasCompanySerializer
    search_fields = ["name", "slug", "tax_identifier"]
    ordering_fields = ["name", "created_at", "status"]

    def get_serializer_class(self):
        if self.action == "create":
            return SaasCompanyCreateSerializer
        return SaasCompanySerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = serializer.save()
        company = result["company"]
        owner = result["user"]
        subscription = result["subscription"]
        return Response({
            "company_id": str(company.id),
            "company_name": company.name,
            "slug": company.slug,
            "owner_id": str(owner.id),
            "owner_email": owner.email,
            "owner_name": owner.first_name,
            "temporary_password": result["password"],
            "booking_url": booking_url(company),
            "subscription": subscription_payload(subscription) if subscription else None,
            "detail": "Empresa creada. Comparte estas credenciales con el cliente.",
        }, status=status.HTTP_201_CREATED)

    def get_queryset(self):
        queryset = Company.objects.order_by("name").prefetch_related(Prefetch(
            "subscriptions",
            queryset=Subscription.objects.filter(ended_at__isnull=True).select_related("plan"),
            to_attr="open_subscriptions",
        ))
        status_value = self.request.query_params.get("status")
        if status_value:
            queryset = queryset.filter(status=status_value)
        return queryset

    @action(detail=True, methods=["post"], url_path="change-status")
    def change_status(self, request, pk=None):
        serializer = CompanyStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        company = self.get_object()
        previous = company.status
        company.status = serializer.validated_data["status"]
        company.save(update_fields=["status", "updated_at"])
        record_event(company=company, actor=request.user, action="company.status_changed",
                     instance=company, metadata={"previous": previous, "current": company.status})
        return Response(SaasCompanySerializer(company).data)


class SaasSummaryView(APIView):
    permission_classes = [IsAuthenticated, IsSaasAdmin]

    def get(self, request):
        return Response(saas_summary(), status=status.HTTP_200_OK)
