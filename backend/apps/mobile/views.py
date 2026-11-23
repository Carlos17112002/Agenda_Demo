from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.billing.gating import current_subscription
from apps.billing.models import PlanFeature, Subscription
from apps.billing.serializers import SubscriptionSerializer
from apps.identity.models import Membership
from apps.tenancy.branding import branding_payload
from apps.tenancy.models import Branch, Company
from apps.tenancy.permissions import (
    HasTenantContext, HasTenantPermission, PERMISSION_CATALOG,
    effective_permissions, role_defaults_payload,
)
from apps.tenancy.serializers import BranchSerializer
from apps.workforce.models import WorkerProfile

from .models import DeviceInstallation, PushMessage
from .operations import process_operations
from .resources import available_resources
from .serializers import (
    DeviceInstallationSerializer, DeviceRegistrationSerializer,
    OperationBatchSerializer, PushMessageSerializer,
)
from .sync import SYNC_REGISTRY


def billing_overview(company):
    subscription = current_subscription(company)
    codes = list(PlanFeature.Code.values)
    if subscription is None:
        has_history = Subscription.objects.filter(company=company).exists()
        state = "inactive" if has_history else "legacy"
        return state, None, {code: not has_history for code in codes}
    usable = subscription.is_usable()
    features = {
        code: subscription.has_feature(code) if usable else False
        for code in codes
    }
    return ("usable" if usable else "inactive"), subscription, features


class MobileBootstrapView(APIView):
    permission_classes = [IsAuthenticated, HasTenantContext]

    def get(self, request):
        company = request.tenant
        membership = request.user.memberships.filter(
            company=company, active=True,
        ).select_related("default_branch").first()
        if membership is None:
            raise PermissionDenied("La empresa activa no tiene una membresía válida.")

        permissions = effective_permissions(membership)
        billing_state, subscription, features = billing_overview(company)
        branches = Branch.objects.filter(company=company).order_by("name")
        worker = (WorkerProfile.objects.filter(
            company=company, membership=membership, active=True,
        ).first())
        modules = {
            "agenda": features.get("bookings", False) and any(
                permission in permissions
                for permission in ("bookings.read", "bookings.own.read")
            ),
            "inventory": features.get("inventory", False) and "inventory.read" in permissions,
            "customers": features.get("customers", False) and "customers.read" in permissions,
            "subscription": "subscription.read" in permissions,
        }
        companies = (
            request.user.memberships
            .filter(active=True, company__status__in=[
                Company.Status.TRIAL, Company.Status.ACTIVE,
            ])
            .select_related("company")
            .order_by("company__name")
        )
        return Response({
            "api_version": "v1",
            "server_time": timezone.now().isoformat(),
            "user": {
                "id": str(request.user.id),
                "email": request.user.email,
                "first_name": request.user.first_name,
                "last_name": request.user.last_name,
                "is_saas_admin": request.user.is_saas_admin,
                "must_change_password": request.user.must_change_password,
            },
            "company": {
                "id": str(company.id),
                "name": company.name,
                "slug": company.slug,
                "status": company.status,
                "legal_name": company.legal_name,
                "tax_identifier": company.tax_identifier,
                **branding_payload(company, request),
            },
            "membership": {
                "id": str(membership.id),
                "role": membership.role,
                "role_display": membership.get_role_display(),
                "default_branch": (
                    {"id": str(membership.default_branch_id), "name": membership.default_branch.name}
                    if membership.default_branch_id else None
                ),
            },
            "worker": (
                {"id": str(worker.id), "name": str(worker)} if worker else None
            ),
            "companies": [
                {
                    "id": str(row.company_id),
                    "name": row.company.name,
                    "slug": row.company.slug,
                    "status": row.company.status,
                    "role": row.role,
                    **branding_payload(row.company, request),
                }
                for row in companies
            ],
            "permissions": permissions,
            "features": features,
            "modules": modules,
            "billing_state": billing_state,
            "subscription": (
                SubscriptionSerializer(subscription).data if subscription else None
            ),
            "branches": BranchSerializer(branches, many=True).data,
            "sync_resources": available_resources(permissions, features),
            "permission_catalog": sorted(PERMISSION_CATALOG),
            "role_defaults": role_defaults_payload(),
        })


class MobileSyncView(APIView):
    permission_classes = [IsAuthenticated, HasTenantContext, HasTenantPermission]

    def get_required_tenant_permission(self):
        resource = self.kwargs.get("resource")
        config = SYNC_REGISTRY.get(resource)
        if config is None:
            return "branches.read"
        membership = self._membership()
        if (resource == "bookings" and membership
                and membership.role == Membership.Role.WORKER):
            return "bookings.own.read"
        return config.permissions[0]

    def _membership(self):
        return self.request.user.memberships.filter(
            company=self.request.tenant, active=True,
        ).first()

    def get(self, request, resource):
        config = SYNC_REGISTRY.get(resource)
        if config is None:
            raise NotFound("Recurso de sincronización desconocido.")

        since = self._parse_since(request.query_params.get("since"))
        queryset = config.model.objects.filter(company=request.tenant)
        if config.select_related:
            queryset = queryset.select_related(*config.select_related)
        if config.prefetch_related:
            queryset = queryset.prefetch_related(*config.prefetch_related)
        membership = self._membership()
        if (resource == "bookings" and membership
                and membership.role == Membership.Role.WORKER):
            queryset = queryset.filter(worker__membership=membership)
        if since is not None:
            queryset = queryset.filter(**{f"{config.cursor_field}__gt": since})
        queryset = queryset.order_by(config.cursor_field, "id")

        paginator = PageNumberPagination()
        page = paginator.paginate_queryset(queryset, request, view=self)
        data = config.serializer(page, many=True, context={"request": request}).data
        server_time = timezone.now()
        cursor_values = [getattr(obj, config.cursor_field) for obj in page]
        next_since = (
            max(cursor_values) if cursor_values
            else (since or server_time)
        )
        return Response({
            "resource": resource,
            "server_time": server_time.isoformat(),
            "since": since.isoformat() if since else None,
            "next_since": next_since.isoformat(),
            "count": paginator.page.paginator.count,
            "next": paginator.get_next_link(),
            "previous": paginator.get_previous_link(),
            "results": data,
        })

    @staticmethod
    def _parse_since(raw):
        if not raw:
            return None
        value = parse_datetime(raw)
        if value is None:
            raise ValidationError({"since": "Usa una fecha ISO 8601 válida."})
        if timezone.is_naive(value):
            value = timezone.make_aware(value, timezone.get_current_timezone())
        return value


class MobileOperationView(APIView):
    permission_classes = [IsAuthenticated, HasTenantContext]

    def post(self, request):
        serializer = OperationBatchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        company = request.tenant
        membership = request.user.memberships.filter(company=company, active=True).first()
        if membership is None:
            raise PermissionDenied("La empresa activa no tiene una membresía válida.")
        results = process_operations(
            company=company, membership=membership, user=request.user,
            operations=serializer.validated_data["operations"], request=request,
        )
        return Response({"results": results})


class MobileDeviceView(APIView):
    permission_classes = [IsAuthenticated, HasTenantContext]

    def get(self, request):
        installations = DeviceInstallation.objects.filter(
            company=request.tenant, user=request.user, active=True,
        )
        return Response(DeviceInstallationSerializer(installations, many=True).data)

    def post(self, request):
        serializer = DeviceRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        installation, _ = DeviceInstallation.objects.update_or_create(
            company=request.tenant, user=request.user,
            installation_id=data["installation_id"],
            defaults={
                "platform": data.get("platform", DeviceInstallation.Platform.OTHER),
                "push_token": data.get("push_token", ""),
                "app_version": data.get("app_version", ""),
                "locale": data.get("locale", ""),
                "active": True,
                "last_seen_at": timezone.now(),
            },
        )
        return Response(DeviceInstallationSerializer(installation).data)


class MobileDeviceDetailView(APIView):
    permission_classes = [IsAuthenticated, HasTenantContext]

    def delete(self, request, installation_id):
        now = timezone.now()
        updated = DeviceInstallation.objects.filter(
            company=request.tenant, user=request.user,
            installation_id=installation_id,
        ).update(active=False, last_seen_at=now, updated_at=now)
        if not updated:
            raise NotFound("La instalación no existe en la empresa activa.")
        return Response(status=204)


class MobileNotificationView(APIView):
    permission_classes = [IsAuthenticated, HasTenantContext]

    def get(self, request):
        queryset = PushMessage.objects.filter(
            company=request.tenant, user=request.user,
        )
        unread_count = queryset.filter(read_at__isnull=True).count()
        if request.query_params.get("unread") == "true":
            queryset = queryset.filter(read_at__isnull=True)
        queryset = queryset.order_by("-created_at", "id")

        paginator = PageNumberPagination()
        page = paginator.paginate_queryset(queryset, request, view=self)
        return Response({
            "unread_count": unread_count,
            "count": paginator.page.paginator.count,
            "next": paginator.get_next_link(),
            "previous": paginator.get_previous_link(),
            "results": PushMessageSerializer(page, many=True).data,
        })


class MobileNotificationReadView(APIView):
    permission_classes = [IsAuthenticated, HasTenantContext]

    def post(self, request, pk):
        message = PushMessage.objects.filter(
            company=request.tenant, user=request.user, pk=pk,
        ).first()
        if message is None:
            raise NotFound("La notificación no existe en la empresa activa.")
        if message.read_at is None:
            message.read_at = timezone.now()
            message.save(update_fields=["read_at", "updated_at"])
        return Response(PushMessageSerializer(message).data)


class MobileNotificationReadAllView(APIView):
    permission_classes = [IsAuthenticated, HasTenantContext]

    def post(self, request):
        updated = PushMessage.objects.filter(
            company=request.tenant, user=request.user, read_at__isnull=True,
        ).update(read_at=timezone.now())
        return Response({"updated": updated})


