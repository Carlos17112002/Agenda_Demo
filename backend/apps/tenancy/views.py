from uuid import UUID

from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from apps.audit.services import record_event
from apps.identity.models import PermissionGrant
from .api import TenantModelViewSet
from .branding import branding_payload
from .models import Branch, TenantContext
from .permissions import (
    HasTenantContext, HasTenantPermission, IsTenantOwner, has_tenant_permission,
)
from .serializers import (
    BranchSerializer, CompanyBrandingSerializer, CompanyLogoSerializer,
    CompanyRegistrationSerializer, CompanySerializer, PermissionGrantSerializer,
    ResendVerificationSerializer, TenantContextSerializer, VerifyEmailSerializer,
)


class MyCompaniesView(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def list(self, request):
        memberships = request.user.memberships.filter(active=True).select_related("company")
        if request.query_params.get("include") != "all":
            memberships = memberships.filter(company__status__in=["trial", "active"])
        companies = [membership.company for membership in memberships]
        return Response(CompanySerializer(
            companies, many=True, context={"request": request},
        ).data)


def branding_membership(request):
    membership = request.user.memberships.filter(
        company=request.tenant, active=True,
    ).first()
    if membership is None:
        raise PermissionDenied("No tienes acceso a esta empresa.")
    return membership


def require_branding_manager(request):
    membership = branding_membership(request)
    if not has_tenant_permission(membership, "company.manage"):
        raise PermissionDenied("Solo el propietario o administrador puede editar la marca.")
    return membership


def branding_response(company, request, *, can_manage):
    payload = branding_payload(company, request)
    payload.update({
        "name": company.name,
        "slug": company.slug,
        "can_manage": can_manage,
    })
    return Response(payload)


class CompanyBrandingView(APIView):
    permission_classes = [permissions.IsAuthenticated, HasTenantContext]

    def get(self, request):
        membership = branding_membership(request)
        return branding_response(
            request.tenant, request,
            can_manage=has_tenant_permission(membership, "company.manage"),
        )

    def patch(self, request):
        require_branding_manager(request)
        company = request.tenant
        previous_slug = company.slug
        serializer = CompanyBrandingSerializer(company, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        company = serializer.save()
        record_event(
            company=company, actor=request.user, action="company.branding_updated",
            instance=company, metadata={"previous_slug": previous_slug, "slug": company.slug},
        )
        return branding_response(company, request, can_manage=True)


class CompanyLogoView(APIView):
    permission_classes = [permissions.IsAuthenticated, HasTenantContext]

    def post(self, request):
        require_branding_manager(request)
        serializer = CompanyLogoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        company = request.tenant
        if company.logo:
            company.logo.delete(save=False)
        company.logo = serializer.validated_data["logo"]
        company.save(update_fields=["logo", "updated_at"])
        record_event(
            company=company, actor=request.user, action="company.branding_updated",
            instance=company, metadata={"logo": company.logo.name},
        )
        return branding_response(company, request, can_manage=True)

    def delete(self, request):
        require_branding_manager(request)
        company = request.tenant
        if company.logo:
            company.logo.delete(save=False)
            company.logo = None
            company.save(update_fields=["logo", "updated_at"])
            record_event(
                company=company, actor=request.user, action="company.branding_updated",
                instance=company, metadata={"logo": ""},
            )
        return branding_response(company, request, can_manage=True)


class RegistrationRateThrottle(AnonRateThrottle):
    scope = "registration"


class CompanyRegistrationView(viewsets.ViewSet):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    throttle_classes = [RegistrationRateThrottle]

    def create(self, request):
        serializer = CompanyRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        company, user = serializer.save()
        return Response({
            "company_id": str(company.id), "company_name": company.name,
            "email": user.email,
            "detail": "Revisa tu correo para activar tu cuenta.",
        }, status=status.HTTP_201_CREATED)


class EmailVerificationRateThrottle(AnonRateThrottle):
    scope = "email_verification"


class ResendVerificationRateThrottle(AnonRateThrottle):
    scope = "resend_verification"


class VerifyEmailView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    throttle_classes = [EmailVerificationRateThrottle]

    def post(self, request):
        from rest_framework_simplejwt.tokens import RefreshToken
        from apps.identity.views import user_payload
        serializer = VerifyEmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user, _, _ = serializer.save()
        refresh = RefreshToken.for_user(user)
        return Response({
            "access": str(refresh.access_token), "refresh": str(refresh),
            "user": user_payload(user),
        })


class ResendVerificationView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    throttle_classes = [ResendVerificationRateThrottle]

    def post(self, request):
        serializer = ResendVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({
            "detail": "Si el correo tiene un registro pendiente, enviamos un nuevo enlace.",
        })


class TenantContextViewSet(viewsets.GenericViewSet):
    serializer_class = TenantContextSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer(self, *args, **kwargs):
        kwargs.setdefault("context", {"request": self.request, "view": self})
        return self.serializer_class(*args, **kwargs)

    def create(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        context = serializer.save()
        return Response(TenantContextSerializer(context).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["get"])
    def current(self, request):
        context = getattr(request._request, "tenant_context", None)
        if context is None:
            from .authentication import resolve_tenant
            resolve_tenant(request._request, request.user)
            context = getattr(request._request, "tenant_context", None)
        if not context:
            return Response({"detail": "No hay una empresa seleccionada."}, status=404)
        return Response(TenantContextSerializer(context).data)


class BranchViewSet(TenantModelViewSet):
    serializer_class = BranchSerializer
    # Solo el propietario crea o modifica sucursales; lectura para cualquier rol con branches.read.
    permission_classes = [
        permissions.IsAuthenticated, HasTenantContext, HasTenantPermission, IsTenantOwner,
    ]
    audit_name = "branch"
    soft_delete = True
    plan_limit_feature = "branches"
    permission_map = {
        "list": "branches.read", "retrieve": "branches.read",
        "create": "branches.manage", "update": "branches.manage",
        "partial_update": "branches.manage", "destroy": "branches.manage",
    }
    search_fields = ["name", "code", "address"]
    ordering_fields = ["name", "created_at"]

    def queryset_for_tenant(self, tenant):
        queryset = Branch.objects.filter(company=tenant)
        active = self.request.query_params.get("active")
        if active in {"true", "false"}:
            queryset = queryset.filter(active=active == "true")
        return queryset

    def get_limit_count(self, tenant):
        return Branch.objects.filter(company=tenant, active=True).count()


class PermissionGrantViewSet(viewsets.ModelViewSet):
    serializer_class = PermissionGrantSerializer
    permission_classes = [permissions.IsAuthenticated, HasTenantContext]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_serializer_context(self):
        return {"request": self.request, "view": self}

    def _actor(self):
        tenant = getattr(self.request, "tenant", None)
        if not tenant:
            from .authentication import resolve_tenant
            tenant = resolve_tenant(self.request, self.request.user)
        if not tenant:
            raise PermissionDenied("Selecciona una empresa.")
        membership = self.request.user.memberships.filter(company=tenant, active=True).first()
        if not membership or membership.role not in ["owner", "admin"]:
            raise PermissionDenied("Se requiere rol propietario o administrador.")
        return membership

    def get_queryset(self):
        actor = self._actor()
        queryset = PermissionGrant.objects.filter(membership__company=actor.company).select_related("membership", "branch")
        membership_id = self.request.query_params.get("membership")
        if membership_id:
            try:
                membership_uuid = UUID(membership_id)
            except (ValueError, TypeError):
                return queryset.none()
            queryset = queryset.filter(membership_id=membership_uuid)
        if actor.role != "owner":
            queryset = queryset.exclude(membership__role__in=["owner", "admin"])
        return queryset

    def perform_create(self, serializer):
        self._actor()
        serializer.save()
