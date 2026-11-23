from django.db import IntegrityError, transaction
from django.db.models import Q
from rest_framework import permissions, serializers, status, viewsets
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from apps.audit.services import record_event
from apps.tenancy.models import Branch
from apps.tenancy.permissions import HasTenantContext
from apps.tenancy.serializers import generate_temporary_password
from apps.workforce.models import WorkerProfile

from .models import Membership, User

ACTOR_ROLES = {Membership.Role.OWNER, Membership.Role.ADMIN}
PROTECTED_ROLES = {Membership.Role.OWNER, Membership.Role.ADMIN}
ORDERING_FIELDS = {
    "last_name": "user__last_name",
    "first_name": "user__first_name",
    "email": "user__email",
    "created_at": "created_at",
}


class MemberPagination(PageNumberPagination):
    page_size = 50


class BranchRefSerializer(serializers.ModelSerializer):
    class Meta:
        model = Branch
        fields = ["id", "name"]


class MemberSerializer(serializers.ModelSerializer):
    user_id = serializers.UUIDField(source="user.id", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    first_name = serializers.CharField(source="user.first_name", read_only=True)
    last_name = serializers.CharField(source="user.last_name", read_only=True)
    role_display = serializers.CharField(source="get_role_display", read_only=True)
    default_branch = BranchRefSerializer(read_only=True)

    class Meta:
        model = Membership
        fields = [
            "id", "user_id", "email", "first_name", "last_name", "role",
            "role_display", "default_branch", "active", "created_at",
        ]


class MemberCreateSerializer(serializers.Serializer):
    email = serializers.EmailField()
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True, default="")
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True, default="")
    role = serializers.ChoiceField(choices=Membership.Role.choices)
    default_branch = serializers.UUIDField(required=False, allow_null=True)
    create_worker_profile = serializers.BooleanField(default=False)

    def validate_email(self, value):
        value = value.strip().lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("Ya existe una cuenta con este correo.")
        return value

    def validate_default_branch(self, value):
        if value is None:
            return None
        branch = Branch.objects.filter(id=value, company=self.context["company"]).first()
        if branch is None:
            raise serializers.ValidationError("La sucursal no pertenece a la empresa activa.")
        return branch

    def validate_role(self, value):
        if self.context["actor_role"] != Membership.Role.OWNER and value in PROTECTED_ROLES:
            raise serializers.ValidationError(
                "Solo el propietario puede asignar roles de propietario o administrador."
            )
        return value

    def validate(self, attrs):
        if attrs.get("create_worker_profile") and attrs["role"] != Membership.Role.WORKER:
            raise serializers.ValidationError(
                {"create_worker_profile": "Solo los trabajadores pueden tener perfil de trabajador."}
            )
        if attrs.get("create_worker_profile") and WorkerProfile.objects.filter(
            company=self.context["company"], email__iexact=attrs["email"],
        ).exists():
            raise serializers.ValidationError(
                {"email": "Ya existe un perfil de trabajador con este correo."}
            )
        return attrs


class MemberUpdateSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    role = serializers.ChoiceField(choices=Membership.Role.choices, required=False)
    default_branch = serializers.UUIDField(required=False, allow_null=True)
    active = serializers.BooleanField(required=False)

    def validate_default_branch(self, value):
        if value is None:
            return None
        branch = Branch.objects.filter(id=value, company=self.context["company"]).first()
        if branch is None:
            raise serializers.ValidationError("La sucursal no pertenece a la empresa activa.")
        return branch

    def validate_role(self, value):
        if self.context["actor_role"] != Membership.Role.OWNER:
            target = self.context["membership"]
            if value in PROTECTED_ROLES or target.role in PROTECTED_ROLES:
                raise serializers.ValidationError(
                    "Solo el propietario puede administrar propietarios o administradores."
                )
        return value

    def validate(self, attrs):
        membership = self.context["membership"]
        new_role = attrs.get("role", membership.role)
        if membership.role == Membership.Role.OWNER and new_role != Membership.Role.OWNER:
            remaining = Membership.objects.filter(
                company=membership.company, role=Membership.Role.OWNER, active=True,
            ).exclude(pk=membership.pk)
            if not remaining.exists():
                raise serializers.ValidationError(
                    {"role": "Debe quedar al menos un propietario activo."}
                )
        return attrs

    def validate_active(self, value):
        membership = self.context["membership"]
        actor = self.context["actor_membership"]
        if value is False:
            if membership.role == Membership.Role.OWNER and not Membership.objects.filter(
                company=membership.company, role=Membership.Role.OWNER, active=True,
            ).exclude(pk=membership.pk).exists():
                raise serializers.ValidationError(
                    "No puedes desactivar al último propietario activo."
                )
            if membership.user_id == actor.user_id:
                raise serializers.ValidationError("No puedes desactivar tu propia membresía.")
        return value


class MembershipViewSet(viewsets.GenericViewSet):
    permission_classes = [permissions.IsAuthenticated, HasTenantContext]
    pagination_class = MemberPagination
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def _actor(self):
        membership = self.request.user.memberships.filter(
            company=self.request.tenant, active=True,
        ).first()
        if membership is None or membership.role not in ACTOR_ROLES:
            raise PermissionDenied("Se requiere rol propietario o administrador.")
        return membership

    def _target(self):
        target = Membership.objects.select_related("user", "default_branch").filter(
            company=self.request.tenant, pk=self.kwargs["pk"],
        ).first()
        if target is None:
            raise NotFound("Miembro no encontrado.")
        return target

    def list(self, request):
        self._actor()
        queryset = Membership.objects.filter(company=request.tenant).select_related(
            "user", "default_branch",
        )
        search = request.query_params.get("search", "").strip()
        if search:
            queryset = queryset.filter(
                Q(user__email__icontains=search)
                | Q(user__first_name__icontains=search)
                | Q(user__last_name__icontains=search)
            )
        ordering = ORDERING_FIELDS.get(request.query_params.get("ordering", ""), "user__last_name")
        queryset = queryset.order_by(ordering, "id")
        page = self.paginate_queryset(queryset)
        serializer = MemberSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    @transaction.atomic
    def create(self, request):
        actor = self._actor()
        data = MemberCreateSerializer(
            data=request.data,
            context={"company": request.tenant, "actor_role": actor.role},
        )
        data.is_valid(raise_exception=True)
        values = data.validated_data
        temporary_password = generate_temporary_password()
        try:
            user = User.objects.create_user(
                username=values["email"],
                email=values["email"],
                password=temporary_password,
                first_name=values["first_name"],
                last_name=values["last_name"],
                must_change_password=True,
            )
        except IntegrityError as error:
            raise ValidationError({"email": ["Ya existe una cuenta con este correo."]}) from error
        membership = Membership.objects.create(
            company=request.tenant,
            user=user,
            role=values["role"],
            default_branch=values.get("default_branch"),
        )
        worker = None
        if values.get("create_worker_profile"):
            worker = WorkerProfile.objects.create(
                company=request.tenant,
                membership=membership,
                first_name=values["first_name"] or values["email"].split("@")[0],
                last_name=values["last_name"],
                email=values["email"],
            )
            if membership.default_branch_id:
                worker.branches.set([membership.default_branch])
        record_event(
            company=request.tenant,
            actor=request.user,
            action="member.created",
            instance=membership,
            metadata={
                "role": membership.role,
                "default_branch": str(membership.default_branch_id) if membership.default_branch_id else None,
                "worker_profile": str(worker.id) if worker else None,
            },
        )
        return Response(
            {
                "member": MemberSerializer(membership).data,
                "temporary_password": temporary_password,
                "worker_profile": {"id": str(worker.id)} if worker else None,
            },
            status=status.HTTP_201_CREATED,
        )

    def partial_update(self, request, pk=None):
        actor = self._actor()
        target = self._target()
        if actor.role != Membership.Role.OWNER and target.role in PROTECTED_ROLES:
            raise PermissionDenied("Solo el propietario puede administrar propietarios o administradores.")
        serializer = MemberUpdateSerializer(
            data=request.data,
            context={
                "company": request.tenant,
                "actor_role": actor.role,
                "membership": target,
                "actor_membership": actor,
            },
        )
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        user_fields = [field for field in ("first_name", "last_name") if field in values]
        if user_fields:
            for field in user_fields:
                setattr(target.user, field, values[field])
            target.user.save(update_fields=user_fields)
        membership_fields = [field for field in ("role", "default_branch", "active") if field in values]
        if membership_fields:
            for field in membership_fields:
                setattr(target, field, values[field])
            target.save(update_fields=membership_fields)
            record_event(
                company=request.tenant,
                actor=request.user,
                action="member.updated",
                instance=target,
                metadata={"fields": sorted(user_fields + membership_fields)},
            )
        return Response(MemberSerializer(target).data)

    def destroy(self, request, pk=None):
        actor = self._actor()
        target = self._target()
        if actor.role != Membership.Role.OWNER and target.role in PROTECTED_ROLES:
            raise PermissionDenied("Solo el propietario puede administrar propietarios o administradores.")
        check = MemberUpdateSerializer(
            data={"active": False},
            context={
                "company": request.tenant,
                "actor_role": actor.role,
                "membership": target,
                "actor_membership": actor,
            },
        )
        check.is_valid(raise_exception=True)
        if target.active:
            target.active = False
            target.save(update_fields=["active"])
            record_event(
                company=request.tenant,
                actor=request.user,
                action="member.deactivated",
                instance=target,
                metadata={"role": target.role},
            )
        return Response(status=status.HTTP_204_NO_CONTENT)
