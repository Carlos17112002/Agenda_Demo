from django.utils import timezone
from PIL import Image
from rest_framework import serializers
from apps.identity.models import Membership, PermissionGrant
from .branding import booking_url
from .models import Branch, Company, TenantContext
from .validators import (
    RESERVED_COMPANY_SLUGS, validate_company_slug, validate_hex_color,
    validate_timezone,
)

MAX_LOGO_BYTES = 2 * 1024 * 1024
MAX_LOGO_DIMENSION = 4000
LOGO_FORMATS = {"PNG", "JPEG", "WEBP"}


def request_tenant(request):
    from .authentication import resolve_tenant
    return getattr(request, "tenant", None) or resolve_tenant(request, request.user)

class CompanySerializer(serializers.ModelSerializer):
    display_name = serializers.SerializerMethodField()
    logo_url = serializers.SerializerMethodField()
    booking_url = serializers.SerializerMethodField()

    class Meta:
        model = Company
        fields = [
            "id", "name", "display_name", "slug", "logo_url", "primary_color",
            "secondary_color", "theme_mode", "booking_url", "legal_name",
            "tax_identifier", "status", "created_at",
        ]
        read_only_fields = fields

    def get_display_name(self, company):
        return company.display_name or company.name

    def get_logo_url(self, company):
        if not company.logo:
            return ""
        request = self.context.get("request")
        return request.build_absolute_uri(company.logo.url) if request else company.logo.url

    def get_booking_url(self, company):
        return booking_url(company)


class CompanyBrandingSerializer(serializers.ModelSerializer):
    display_name = serializers.CharField(max_length=180, required=False, allow_blank=True)
    primary_color = serializers.CharField(
        max_length=7, required=False, validators=[validate_hex_color],
    )
    secondary_color = serializers.CharField(
        max_length=7, required=False, validators=[validate_hex_color],
    )
    slug = serializers.SlugField(
        max_length=100, required=False, validators=[validate_company_slug],
    )

    class Meta:
        model = Company
        fields = [
            "display_name", "primary_color", "secondary_color", "theme_mode", "slug",
        ]

    def validate_slug(self, slug):
        slug = slug.lower()
        if slug in RESERVED_COMPANY_SLUGS:
            raise serializers.ValidationError("Este identificador está reservado por la plataforma.")
        taken = Company.objects.filter(slug__iexact=slug).exclude(pk=self.instance.pk)
        if taken.exists():
            raise serializers.ValidationError("Este identificador de empresa ya está ocupado.")
        return slug

    def validate_display_name(self, display_name):
        return display_name.strip()


class CompanyLogoSerializer(serializers.Serializer):
    logo = serializers.ImageField()

    def validate_logo(self, logo):
        if logo.size > MAX_LOGO_BYTES:
            raise serializers.ValidationError("El logo no puede superar 2 MB.")
        try:
            image = Image.open(logo)
            image_format = image.format
            width, height = image.size
            image.verify()
        except Exception:
            raise serializers.ValidationError(
                "El logo debe ser una imagen PNG, JPEG o WebP válida."
            )
        finally:
            logo.seek(0)
        if image_format not in LOGO_FORMATS:
            raise serializers.ValidationError("El logo debe ser PNG, JPEG o WebP.")
        if width > MAX_LOGO_DIMENSION or height > MAX_LOGO_DIMENSION:
            raise serializers.ValidationError("El logo no puede superar 4000 × 4000 px.")
        return logo

class TenantContextSerializer(serializers.ModelSerializer):
    company = serializers.PrimaryKeyRelatedField(queryset=Company.objects.all())
    company_name = serializers.CharField(source="company.name", read_only=True)
    class Meta:
        model = TenantContext
        fields = ["id", "company", "company_name", "expires_at"]
        read_only_fields = ["id", "company_name", "expires_at"]

    def validate_company(self, company):
        user = self.context["request"].user
        if not user.memberships.filter(company=company, active=True).exists():
            raise serializers.ValidationError("No tienes una membresía activa en esta empresa.")
        if company.status not in [Company.Status.ACTIVE, Company.Status.TRIAL]:
            raise serializers.ValidationError("La empresa no está habilitada.")
        return company

    def validate(self, attrs):
        user = self.context["request"].user
        if TenantContext.objects.filter(user=user, expires_at__gt=timezone.now()).count() >= 20:
            raise serializers.ValidationError("Se alcanzó el máximo de contextos activos.")
        return attrs

    def create(self, validated_data):
        from datetime import timedelta
        return TenantContext.objects.create(user=self.context["request"].user,
            expires_at=timezone.now() + timedelta(hours=8), **validated_data)

def validate_new_company_email(email):
    from apps.identity.models import User
    if User.objects.filter(email__iexact=email).exists():
        raise serializers.ValidationError("Ya existe una cuenta con este correo.")
    return email


def validate_new_company_slug(slug):
    if Company.objects.filter(slug=slug).exists():
        raise serializers.ValidationError("Este identificador de empresa ya está ocupado.")
    return slug


def generate_temporary_password():
    from django.utils.crypto import get_random_string
    return f"{get_random_string(12)}-Aa1!"


def provision_company(*, company_name, slug, email, password, first_name="",
                      source, request=None, actor=None, plan=None, trial_days=None):
    from django.db import transaction
    from apps.identity.models import User
    from apps.audit.models import AuditEvent
    with transaction.atomic():
        company = Company.objects.create(name=company_name, slug=slug)
        user = User.objects.create_user(username=email, email=email, password=password,
                                        first_name=first_name)
        Membership.objects.create(user=user, company=company, role=Membership.Role.OWNER)
        from apps.billing.services import default_plan, start_subscription
        plan = plan or default_plan()
        subscription = None
        if plan:
            subscription = start_subscription(
                company, plan, trial_days=trial_days, actor=actor or user,
            )
        AuditEvent.objects.create(company=company, actor=actor or user,
            action="company.registered", entity_type="Company", entity_id=str(company.id),
            metadata={
                "source": source,
                "remote_addr": request.META.get("REMOTE_ADDR") if request else None,
                "user_agent": (request.META.get("HTTP_USER_AGENT", "")[:240] if request else ""),
            })
    return company, user, subscription


class CompanyRegistrationSerializer(serializers.Serializer):
    company_name = serializers.CharField(max_length=180)
    slug = serializers.SlugField(max_length=100)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=12, max_length=128)
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    def validate_email(self, email):
        return validate_new_company_email(email)
    def validate_slug(self, slug):
        return validate_new_company_slug(slug)
    def validate_password(self, password):
        from django.contrib.auth.password_validation import validate_password
        validate_password(password)
        return password
    def create(self, validated_data):
        return provision_company(
            company_name=validated_data["company_name"],
            slug=validated_data["slug"],
            email=validated_data.pop("email"),
            password=validated_data.pop("password"),
            first_name=validated_data.pop("first_name", ""),
            source="public_registration",
            request=self.context.get("request"),
        )


class SaasCompanyCreateSerializer(serializers.Serializer):
    company_name = serializers.CharField(max_length=180)
    slug = serializers.SlugField(max_length=100)
    email = serializers.EmailField()
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    password = serializers.CharField(
        write_only=True, min_length=12, max_length=128, required=False,
    )
    plan = serializers.CharField(required=False)
    trial_days = serializers.IntegerField(required=False, allow_null=True, min_value=0, max_value=365)

    def validate_email(self, email):
        return validate_new_company_email(email)

    def validate_slug(self, slug):
        return validate_new_company_slug(slug)

    def validate_password(self, password):
        from django.contrib.auth.password_validation import validate_password
        validate_password(password)
        return password

    def validate_plan(self, code):
        from apps.billing.models import Plan
        plan = Plan.objects.filter(code=code, active=True).first()
        if plan is None:
            raise serializers.ValidationError("El plan no está disponible.")
        return plan

    def create(self, validated_data):
        request = self.context.get("request")
        password = validated_data.pop("password", None) or generate_temporary_password()
        company, user, subscription = provision_company(
            company_name=validated_data["company_name"],
            slug=validated_data["slug"],
            email=validated_data["email"],
            password=password,
            first_name=validated_data.get("first_name", ""),
            source="saas_console",
            request=request,
            actor=request.user,
            plan=validated_data.get("plan"),
            trial_days=validated_data.get("trial_days"),
        )
        return {
            "company": company, "user": user, "password": password,
            "subscription": subscription,
        }

class TenantOwnedSerializer(serializers.ModelSerializer):
    """Tenant-owned records: company is always derived from the server context."""

    company = serializers.UUIDField(source="company_id", read_only=True)

    def to_internal_value(self, data):
        if "company" in data:
            raise serializers.ValidationError({"company": "La empresa se asigna desde el contexto autenticado."})
        return super().to_internal_value(data)

class BranchSerializer(TenantOwnedSerializer):
    timezone = serializers.CharField(max_length=64, required=False, validators=[validate_timezone])

    class Meta:
        model = Branch
        fields = ["id", "company", "name", "code", "address", "timezone", "active",
                  "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate(self, attrs):
        attrs = super().validate(attrs)
        tenant = getattr(self.context.get("request"), "tenant", None)
        code = attrs.get("code", getattr(self.instance, "code", None))
        if tenant and code:
            duplicates = Branch.objects.filter(company=tenant, code=code)
            if self.instance:
                duplicates = duplicates.exclude(pk=self.instance.pk)
            if duplicates.exists():
                raise serializers.ValidationError(
                    {"code": "Ya existe una sucursal con ese código en la empresa."}
                )
        return attrs

class PermissionGrantSerializer(serializers.ModelSerializer):
    class Meta:
        model = PermissionGrant
        fields = ["id", "membership", "permission", "effect", "branch", "created_at"]
        read_only_fields = ["id", "created_at"]

    def validate(self, attrs):
        request = self.context["request"]
        membership = attrs.get("membership", getattr(self.instance, "membership", None))
        branch = attrs.get("branch", getattr(self.instance, "branch", None))
        if branch and membership and branch.company_id != membership.company_id:
            raise serializers.ValidationError("La sucursal y la membresía deben pertenecer a la misma empresa.")
        from .permissions import PERMISSION_CATALOG

        tenant = getattr(request, "tenant", None)
        if tenant and membership and membership.company_id != tenant.id:
            raise serializers.ValidationError(
                {"membership": "La membresía no pertenece a la empresa activa."}
            )
        permission = attrs.get("permission", getattr(self.instance, "permission", None))
        if permission and permission not in PERMISSION_CATALOG:
            raise serializers.ValidationError({"permission": "Permiso desconocido."})
        if request.user.is_superuser:
            return attrs
        actor = request.user.memberships.filter(company=membership.company, active=True).first() if membership else None
        if not actor or actor.role not in ["owner", "admin"]:
            raise serializers.ValidationError("Solo el propietario o administrador puede gestionar permisos.")
        if membership.role in ["owner", "admin"] and actor.role != "owner":
            raise serializers.ValidationError("Solo el propietario puede modificar permisos de administración.")
        return attrs
