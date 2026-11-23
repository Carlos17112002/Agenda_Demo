# Usuarios con local predeterminado — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permitir que cada empresa cree usuarios desde el panel web, les asigne un local predeterminado editable y les entregue una clave temporal de un solo uso, con cambio de clave obligatorio al primer ingreso; web y Flutter abren la agenda en ese local.

**Architecture:** El backend añade `Membership.default_branch` y `User.must_change_password`, un `MembershipViewSet` scoped al tenant activo (`/api/v1/members/`), un endpoint de cambio de clave que revoca tokens, y enriquece el bootstrap con `default_branch`, `must_change_password`, `permission_catalog` y `role_defaults`. El panel web agrega la sección Usuarios, el editor de permisos sobre `/api/v1/permission-grants/` y la pantalla forzada de cambio de clave. Flutter solo consume los campos nuevos del bootstrap para preseleccionar el local y mostrar la pantalla obligatoria.

**Tech Stack:** Django 6 + DRF, simplejwt, SQLite local; React 18 + Vite + TanStack Query + react-hook-form/zod + Radix + Tailwind, Vitest/MSW y Playwright; Flutter (provider) con tests de widget/estado.

**Spec:** `docs/superpowers/specs/2026-11-19-usuarios-local-predeterminado-design.md`

## Global Constraints

- **Aislamiento por empresa (regla dura):** toda lectura o escritura se filtra por `request.tenant`; ninguna empresa puede leer, modificar ni eliminar datos de otra. Los ids que llegan por URL o body se validan contra la empresa activa.
- **Solo propietario/administrador administran usuarios.** Un administrador nunca puede crear, editar, desactivar ni otorgar permisos a propietarios/administradores.
- **Desactivar una membresía = `Membership.active = False`**; nunca tocar `User.is_active`. El mismo usuario puede pertenecer a otras empresas.
- **El local debe pertenecer a la empresa activa** (`default_branch.company == request.tenant`); si no, 400 con clave `default_branch`.
- **Local predeterminado editable:** no restringe reservas a ese local; solo define la selección inicial en web y Flutter. Si está inactivo o no existe, se usa el primer local activo.
- **Clave temporal visible una sola vez:** formato `generate_temporary_password()`; nunca se guarda ni se registra en auditoría. `must_change_password=True` en el primer login.
- **Cambio de clave:** exige `current_password`, política de contraseñas, revoca tokens previos (`revoke_user_tokens`) y devuelve tokens nuevos.
- **Base de datos local (SQLite)** por ahora; no cambiar a PostgreSQL en este plan.
- **Sin commits ni push:** no ejecutar `git commit` ni `git push`; Carlos debe autorizarlo explícitamente. Los pasos de verificación son checkpoints de tests.
- **UI en español** con las cadenas exactas indicadas en cada tarea.
- **Backend tests:** `cd backend && DJANGO_TESTING=true python manage.py test <app.tests.modulo> -v 2`
- **Web:** `cd web && npm test -- <archivo>`; cierre con `npm run lint` y `npm run build`.
- **Flutter:** `cd mobile && flutter test <archivo>`; cierre con `flutter analyze`.

---

## File Structure

**Backend (crear/modificar)**
- Modify `backend/apps/identity/models.py`: campos `User.must_change_password`, `Membership.default_branch`.
- Create `backend/apps/identity/migrations/0007_members_default_branch.py` (nombre autogenerado por `makemigrations`).
- Create `backend/apps/identity/member_views.py`: serializers + `MembershipViewSet`.
- Modify `backend/apps/identity/views.py`: `PasswordChangeSerializer`, `PasswordChangeView`, flag en `LoginSerializer`.
- Modify `backend/apps/tenancy/views.py`: filtro `membership` en `PermissionGrantViewSet`.
- Modify `backend/apps/tenancy/permissions.py`: `role_defaults_payload()`.
- Modify `backend/apps/mobile/views.py`: payload de bootstrap.
- Modify `backend/config/urls.py`: registro del router de members y ruta de cambio de clave.
- Create `backend/apps/identity/tests/test_members.py`; modify `backend/apps/identity/tests/test_auth_flows.py`; modify `backend/apps/mobile/tests/test_bootstrap.py`.

**Web (crear/modificar)**
- Modify `web/src/api/types.ts`; create `web/src/api/members.ts`; modify `web/src/api/auth.ts`, `web/src/api/queryKeys.ts`, `web/src/api/runtime.ts`.
- Create `web/src/api/members.test.ts`.
- Create `web/src/features/agenda/branchSelection.ts` + test; modify `web/src/features/agenda/AgendaPage.tsx`.
- Modify `web/src/auth/AuthProvider.tsx`; modify `web/src/app/guards.tsx`, `web/src/app/router.tsx`, `web/src/lib/permissions.ts`.
- Create `web/src/features/auth/ChangePasswordPage.tsx` + test.
- Create `web/src/features/members/{MembersPage.tsx,MemberFormDialog.tsx,CredentialsDialog.tsx,PermissionsDialog.tsx,memberRoles.ts,permissionLabels.ts}` + tests.
- Modify `web/src/test/factories.ts`.
- Create `web/e2e/members.spec.ts`.

**Flutter (crear/modificar)**
- Modify `mobile/lib/data/models.dart`; create `mobile/lib/data/branch_selection.dart`.
- Modify `mobile/lib/screens/agenda_screen.dart`; modify `mobile/lib/state/app_state.dart`; modify `mobile/lib/app.dart`.
- Create `mobile/lib/screens/change_password_screen.dart`.
- Create `mobile/test/branch_selection_test.dart`, `mobile/test/bootstrap_member_test.dart`, `mobile/test/app_state_change_password_test.dart`.

---

### Task 1: Campos de modelo y migración

**Files:**
- Modify: `backend/apps/identity/models.py`
- Create: `backend/apps/identity/migrations/0007_members_default_branch.py` (autogenerado)
- Test: `backend/apps/identity/tests/test_members.py`

**Interfaces:**
- Produces: `Membership.default_branch -> tenancy.Branch | None` (`related_name="default_for_memberships"`, `SET_NULL`); `User.must_change_password -> bool` (default `False`).

- [ ] **Step 1: Write the failing test**

Create `backend/apps/identity/tests/test_members.py`:

```python
from django.test import TestCase

from apps.identity.models import Membership, User
from apps.tenancy.models import Branch
from apps.tenancy.tests.utils import make_company

PASSWORD = "Correct-Horse-Battery-983!"


class MembershipModelTests(TestCase):
    def test_membership_can_point_to_a_default_branch(self):
        company = make_company("members-model", "Modelo")
        user = User.objects.create_user(
            username="model@example.com", email="model@example.com", password=PASSWORD,
        )
        branch = Branch.objects.create(company=company, name="Centro", code="CEN")

        membership = Membership.objects.create(
            company=company, user=user, default_branch=branch,
        )

        membership.refresh_from_db()
        self.assertEqual(membership.default_branch, branch)

    def test_new_users_do_not_require_password_change(self):
        user = User.objects.create_user(
            username="flag@example.com", email="flag@example.com", password=PASSWORD,
        )
        self.assertFalse(user.must_change_password)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && DJANGO_TESTING=true python manage.py test apps.identity.tests.test_members -v 2`
Expected: FAIL with `TypeError: Membership() got unexpected keyword arguments: 'default_branch'` / missing field.

- [ ] **Step 3: Write minimal implementation**

In `backend/apps/identity/models.py`, add to `User` (next to `is_saas_admin`):

```python
    must_change_password = models.BooleanField(default=False)
```

Add to `Membership` (after `role`):

```python
    default_branch = models.ForeignKey(
        "tenancy.Branch",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="default_for_memberships",
    )
```

- [ ] **Step 4: Generate and apply migration**

Run:

```bash
cd backend && DJANGO_TESTING=true python manage.py makemigrations identity
cd backend && DJANGO_TESTING=true python manage.py migrate
```

Expected: nueva migración `identity/0007_...` con `AlterField`/`AddField`; `migrate` sin errores.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && DJANGO_TESTING=true python manage.py test apps.identity.tests.test_members -v 2`
Expected: 2 tests PASS.

---

### Task 2: Members API — listar, editar y desactivar

**Files:**
- Create: `backend/apps/identity/member_views.py`
- Modify: `backend/config/urls.py`
- Modify: `backend/apps/tenancy/views.py:208-213`
- Modify: `backend/apps/tenancy/serializers.py:274-287`
- Test: `backend/apps/identity/tests/test_members.py`

**Interfaces:**
- Produces:
  - `MemberSerializer` (fields `id, user_id, email, first_name, last_name, role, role_display, default_branch {id,name}|null, active, created_at`).
  - `MembershipViewSet` at `/api/v1/members/` con `list`, `create`, `partial_update`, `destroy`.
  - `GET /api/v1/permission-grants/?membership=<uuid>` filtra por membresía.
- Consumes: `Membership`, `User`, `Branch`, `HasTenantContext`, `generate_temporary_password`, `record_event`.

- [ ] **Step 1: Write the failing tests**

Append to `backend/apps/identity/tests/test_members.py`:

```python
from rest_framework.test import APIClient

from apps.identity.models import PermissionGrant
from apps.tenancy.tests.utils import make_context, make_membership, make_user, tenant_client


class MembersApiTests(TestCase):
    def setUp(self):
        self.company = make_company("members-api", "Miembros API")
        self.owner = make_user("owner-members@example.com")
        self.owner_membership = make_membership(self.owner, self.company, Membership.Role.OWNER)
        self.client = tenant_client(self.owner, make_context(self.owner, self.company))
        self.branch = Branch.objects.create(company=self.company, name="Centro", code="CEN")
        self.other_company = make_company("members-foreign", "Ajena")
        self.foreign_branch = Branch.objects.create(
            company=self.other_company, name="Ajena", code="AJN",
        )

    def _admin_client(self):
        user = make_user("admin-members@example.com")
        make_membership(user, self.company, Membership.Role.ADMIN)
        return tenant_client(user, make_context(user, self.company))

    def _create_member(self, **overrides):
        payload = {
            "email": "nuevo@example.com",
            "first_name": "Nueva",
            "last_name": "Persona",
            "role": "reception",
            "default_branch": str(self.branch.id),
        }
        payload.update(overrides)
        return self.client.post("/api/v1/members/", payload, format="json")

    def test_lists_only_members_of_the_active_company(self):
        foreign_user = make_user("foreign@example.com")
        make_membership(foreign_user, self.other_company)

        response = self.client.get("/api/v1/members/")

        self.assertEqual(response.status_code, 200)
        emails = [row["email"] for row in response.data["results"]]
        self.assertEqual(emails, [self.owner.email])

    def test_owner_updates_role_and_default_branch(self):
        target = make_user("target@example.com")
        membership = make_membership(target, self.company, Membership.Role.RECEPTION)
        other_branch = Branch.objects.create(company=self.company, name="Norte", code="NOR")

        response = self.client.patch(
            f"/api/v1/members/{membership.id}/",
            {"role": "manager", "default_branch": str(other_branch.id)},
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        membership.refresh_from_db()
        self.assertEqual(membership.role, Membership.Role.MANAGER)
        self.assertEqual(membership.default_branch, other_branch)

    def test_foreign_branch_is_rejected_on_update(self):
        target = make_user("target-foreign@example.com")
        membership = make_membership(target, self.company, Membership.Role.RECEPTION)

        response = self.client.patch(
            f"/api/v1/members/{membership.id}/",
            {"default_branch": str(self.foreign_branch.id)},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("default_branch", response.data)

    def test_admin_cannot_modify_an_owner(self):
        response = self._admin_client().patch(
            f"/api/v1/members/{self.owner_membership.id}/",
            {"first_name": "Hack"},
            format="json",
        )

        self.assertEqual(response.status_code, 403)

    def test_deactivation_is_soft_and_keeps_the_user_active(self):
        target = make_user("soft@example.com")
        membership = make_membership(target, self.company, Membership.Role.RECEPTION)

        response = self.client.delete(f"/api/v1/members/{membership.id}/")

        self.assertEqual(response.status_code, 204)
        membership.refresh_from_db()
        target.refresh_from_db()
        self.assertFalse(membership.active)
        self.assertTrue(target.is_active)

    def test_owner_cannot_deactivate_self_when_another_owner_exists(self):
        second = make_user("owner-two@example.com")
        make_membership(second, self.company, Membership.Role.OWNER)

        response = self.client.delete(f"/api/v1/members/{self.owner_membership.id}/")

        self.assertEqual(response.status_code, 400)
        self.assertIn("active", response.data)

    def test_last_owner_cannot_be_deactivated(self):
        response = self.client.delete(f"/api/v1/members/{self.owner_membership.id}/")

        self.assertEqual(response.status_code, 400)
        self.assertIn("active", response.data)
        self.owner_membership.refresh_from_db()
        self.assertTrue(self.owner_membership.active)

    def test_last_owner_cannot_be_demoted(self):
        response = self.client.patch(
            f"/api/v1/members/{self.owner_membership.id}/",
            {"role": "admin"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("role", response.data)
        self.owner_membership.refresh_from_db()
        self.assertEqual(self.owner_membership.role, Membership.Role.OWNER)

    def test_permission_grants_can_be_filtered_by_membership(self):
        target = make_user("target-grants@example.com")
        target_membership = make_membership(target, self.company, Membership.Role.RECEPTION)
        PermissionGrant.objects.create(
            membership=target_membership, permission="bookings.write", effect="deny",
        )
        PermissionGrant.objects.create(
            membership=self.owner_membership, permission="bookings.read", effect="allow",
        )

        response = self.client.get(
            "/api/v1/permission-grants/", {"membership": str(target_membership.id)},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["permission"], "bookings.write")

    def test_grants_reject_memberships_from_another_tenant(self):
        make_membership(self.owner, self.other_company, Membership.Role.OWNER)
        foreign_user = make_user("foreign-grant@example.com")
        foreign_membership = make_membership(foreign_user, self.other_company)

        response = self.client.post("/api/v1/permission-grants/", {
            "membership": str(foreign_membership.id),
            "permission": "bookings.read",
            "effect": "allow",
        }, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertIn("membership", response.data)

    def test_grants_reject_unknown_permissions(self):
        target = make_user("unknown-perm@example.com")
        membership = make_membership(target, self.company, Membership.Role.RECEPTION)

        response = self.client.post("/api/v1/permission-grants/", {
            "membership": str(membership.id),
            "permission": "nope.nope",
            "effect": "allow",
        }, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertIn("permission", response.data)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && DJANGO_TESTING=true python manage.py test apps.identity.tests.test_members -v 2`
Expected: FAIL con 404 en `/api/v1/members/` y lista de permisos sin filtrar.

- [ ] **Step 3: Create `backend/apps/identity/member_views.py`**

```python
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
```

In `backend/apps/tenancy/views.py`:

1. Add `from uuid import UUID` at the top.
2. Replace `PermissionGrantViewSet.get_queryset` with:

```python
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
```

3. Delete the `get_permissions` override so every action (including `list`/`retrieve`) passes through `_actor()` and requires owner/admin. No client read grants today, so nothing else depends on member-level listing.

4. In `backend/apps/tenancy/serializers.py`, inside `PermissionGrantSerializer.validate`, after the branch/company check add:

```python
        from .permissions import PERMISSION_CATALOG

        tenant = getattr(request, "tenant", None)
        if tenant and membership and membership.company_id != tenant.id:
            raise serializers.ValidationError(
                {"membership": "La membresía no pertenece a la empresa activa."}
            )
        permission = attrs.get("permission", getattr(self.instance, "permission", None))
        if permission and permission not in PERMISSION_CATALOG:
            raise serializers.ValidationError({"permission": "Permiso desconocido."})
```

- [ ] **Step 4: Register the route**

In `backend/config/urls.py`, import and register:

```python
from apps.identity.member_views import MembershipViewSet
...
router.register("members", MembershipViewSet, basename="member")
```

Run: `cd backend && DJANGO_TESTING=true python manage.py check`

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && DJANGO_TESTING=true python manage.py test apps.identity.tests.test_members -v 2`
Expected: todos los tests de modelo y API PASS.

---

### Task 3: Members API — crear usuario con clave temporal y perfil opcional

**Files:**
- Modify: `backend/apps/identity/member_views.py` (ya contiene el `create`)
- Test: `backend/apps/identity/tests/test_members.py`

**Interfaces:**
- Consumes: `MemberCreateSerializer`, `generate_temporary_password()`, `WorkerProfile`.
- Produces: `POST /api/v1/members/` → `201 {member, temporary_password, worker_profile|null}`.

- [ ] **Step 1: Write the failing tests**

Append to `MembersApiTests`:

```python
    def test_owner_creates_member_with_branch_and_temporary_password(self):
        response = self._create_member(email="creada@example.com")

        self.assertEqual(response.status_code, 201, response.data)
        self.assertTrue(response.data["temporary_password"])
        user = User.objects.get(email="creada@example.com")
        self.assertTrue(user.must_change_password)
        self.assertTrue(user.check_password(response.data["temporary_password"]))
        self.assertEqual(response.data["member"]["default_branch"]["id"], str(self.branch.id))

    def test_duplicate_email_is_rejected(self):
        self._create_member(email="repetida@example.com")

        response = self._create_member(email="repetida@example.com")

        self.assertEqual(response.status_code, 400)
        self.assertIn("email", response.data)

    def test_foreign_branch_is_rejected_on_create(self):
        response = self._create_member(default_branch=str(self.foreign_branch.id))

        self.assertEqual(response.status_code, 400)
        self.assertIn("default_branch", response.data)

    def test_admin_cannot_assign_owner_role(self):
        response = self._admin_client().post(
            "/api/v1/members/",
            {"email": "owner2@example.com", "role": "owner"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("role", response.data)

    def test_worker_profile_is_created_with_the_default_branch(self):
        response = self._create_member(
            email="worker-new@example.com", role="worker", create_worker_profile=True,
            first_name="Wanda",
        )

        self.assertEqual(response.status_code, 201, response.data)
        self.assertIsNotNone(response.data["worker_profile"])
        worker = WorkerProfile.objects.get(membership__user__email="worker-new@example.com")
        self.assertEqual(worker.company, self.company)
        self.assertEqual(list(worker.branches.all()), [self.branch])

    def test_worker_profile_requires_worker_role(self):
        response = self._create_member(
            email="reception-worker@example.com", role="reception", create_worker_profile=True,
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("create_worker_profile", response.data)
```

Add the import at the top: `from apps.workforce.models import WorkerProfile`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && DJANGO_TESTING=true python manage.py test apps.identity.tests.test_members -v 2`
Expected: FAIL si `create` aún no existe o no valida.

- [ ] **Step 3: Implement the missing pieces (if not already present)**

The `create` method and validations from Task 2 are the implementation; if a test fails, fix only the failing rule (duplicate email → 400 con `email`, foreign branch → `default_branch`, admin/owner role → `role`, worker profile only for `worker`).

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && DJANGO_TESTING=true python manage.py test apps.identity.tests.test_members -v 2`
Expected: todos PASS.

---

### Task 4: Cambio de clave autenticado y flag en el login

**Files:**
- Modify: `backend/apps/identity/views.py`
- Modify: `backend/config/urls.py`
- Test: `backend/apps/identity/tests/test_auth_flows.py`

**Interfaces:**
- Produces: `POST /api/v1/auth/password/change/` body `{current_password,new_password}` → `200 {access, refresh, must_change_password:false}`; login user dict incluye `must_change_password`.
- Consumes: `revoke_user_tokens(user)`, `RefreshToken.for_user(user)`, `validate_password`.

- [ ] **Step 1: Write the failing tests**

Append to `backend/apps/identity/tests/test_auth_flows.py`:

```python
class PasswordChangeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="change@example.com", email="change@example.com",
            password="Correct-Horse-Battery-983!", must_change_password=True,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_login_reports_must_change_password(self):
        response = APIClient().post("/api/v1/auth/token/", {
            "email": self.user.email, "password": "Correct-Horse-Battery-983!",
        }, format="json")

        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(response.data["user"]["must_change_password"])

    def test_change_requires_the_current_password(self):
        response = self.client.post("/api/v1/auth/password/change/", {
            "current_password": "Incorrecta-123!",
            "new_password": "Another-Strong-Horse-284!",
        }, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertIn("current_password", response.data)

    def test_change_rejects_the_same_password(self):
        response = self.client.post("/api/v1/auth/password/change/", {
            "current_password": "Correct-Horse-Battery-983!",
            "new_password": "Correct-Horse-Battery-983!",
        }, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertIn("new_password", response.data)

    def test_change_issues_new_tokens_and_revokes_the_old_ones(self):
        old_refresh = RefreshToken.for_user(self.user)
        old_access = str(old_refresh.access_token)

        response = self.client.post("/api/v1/auth/password/change/", {
            "current_password": "Correct-Horse-Battery-983!",
            "new_password": "Another-Strong-Horse-284!",
        }, format="json")

        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(response.data["must_change_password"])
        self.user.refresh_from_db()
        self.assertFalse(self.user.must_change_password)
        self.assertTrue(self.user.check_password("Another-Strong-Horse-284!"))

        old_client = APIClient()
        old_client.credentials(HTTP_AUTHORIZATION=f"Bearer {old_access}")
        self.assertEqual(old_client.get("/api/v1/companies/mine/").status_code, 401)
        self.assertEqual(
            APIClient().post("/api/v1/auth/token/refresh/", {"refresh": str(old_refresh)}, format="json").status_code,
            401,
        )

        new_client = APIClient()
        new_client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
        self.assertEqual(new_client.get("/api/v1/companies/mine/").status_code, 200)
        self.assertEqual(
            APIClient().post("/api/v1/auth/token/refresh/", {"refresh": response.data["refresh"]}, format="json").status_code,
            200,
        )

    def test_change_enforces_the_password_policy(self):
        response = self.client.post("/api/v1/auth/password/change/", {
            "current_password": "Correct-Horse-Battery-983!",
            "new_password": "corta",
        }, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertIn("new_password", response.data)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && DJANGO_TESTING=true python manage.py test apps.identity.tests.test_auth_flows -v 2`
Expected: FAIL con 404 en `/api/v1/auth/password/change/` y `KeyError: 'must_change_password'`.

- [ ] **Step 3: Implement**

In `backend/apps/identity/views.py`:

1. In `LoginSerializer.validate`, add to the returned user dict:

```python
                "must_change_password": self.user.must_change_password,
```

2. Imports: `validate_password` and `revoke_user_tokens` ya están importados en el archivo; agrega `from django.core.exceptions import ValidationError as DjangoValidationError` y cambia la línea de permissions a `from rest_framework.permissions import AllowAny, IsAuthenticated` (`RefreshToken` ya está importado).

3. Add at the end of the auth views:

```python
class PasswordChangeSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=12, max_length=128)

    def validate(self, attrs):
        user = self.context["request"].user
        if not user.check_password(attrs["current_password"]):
            raise serializers.ValidationError(
                {"current_password": "La contraseña actual no es correcta."}
            )
        if attrs["current_password"] == attrs["new_password"]:
            raise serializers.ValidationError(
                {"new_password": "La nueva contraseña debe ser distinta a la actual."}
            )
        try:
            validate_password(attrs["new_password"], user=user)
        except DjangoValidationError as error:
            raise serializers.ValidationError({"new_password": list(error.messages)}) from error
        return attrs


class PasswordChangeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = PasswordChangeSerializer(
            data=request.data, context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        user = request.user
        user.set_password(serializer.validated_data["new_password"])
        user.must_change_password = False
        user.save(update_fields=["password", "must_change_password"])
        revoke_user_tokens(user)
        refresh = RefreshToken.for_user(user)
        return Response({
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "must_change_password": False,
        })
```

`IsAuthenticated` viene del import del paso 3; no agregues `permissions`.

In `backend/config/urls.py`, add next to the other auth paths:

```python
    path("api/v1/auth/password/change/", PasswordChangeView.as_view(), name="password-change"),
```

(import `PasswordChangeView` from `apps.identity.views`).

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && DJANGO_TESTING=true python manage.py test apps.identity.tests.test_auth_flows -v 2`
Expected: todos PASS (incluidos los tests previos de reset/revocación).

---

### Task 5: Bootstrap con local predeterminado, flag y catálogo de permisos

**Files:**
- Modify: `backend/apps/tenancy/permissions.py`
- Modify: `backend/apps/mobile/views.py`
- Test: `backend/apps/mobile/tests/test_bootstrap.py`

**Interfaces:**
- Produces: `role_defaults_payload()`; bootstrap agrega `user.must_change_password`, `membership.default_branch`, `permission_catalog`, `role_defaults`.
- Consumes: `PERMISSION_CATALOG`, `ROLE_DEFAULTS`.

- [ ] **Step 1: Write the failing test**

Add to `MobileBootstrapTests`:

```python
    def test_bootstrap_exposes_member_management_context(self):
        membership = self.owner.memberships.get(company=self.company)
        membership.default_branch = self.branch
        membership.save(update_fields=["default_branch"])
        self.owner.must_change_password = True
        self.owner.save(update_fields=["must_change_password"])

        response = self.client.get("/api/v1/mobile/bootstrap/")

        self.assertEqual(response.status_code, 200, getattr(response, "data", None))
        self.assertTrue(response.data["user"]["must_change_password"])
        self.assertEqual(response.data["membership"]["default_branch"]["id"], str(self.branch.id))
        self.assertEqual(response.data["membership"]["default_branch"]["name"], "Centro")
        self.assertIn("company.manage", response.data["permission_catalog"])
        self.assertIn("bookings.read", response.data["role_defaults"]["reception"])
        self.assertNotIn("inventory.write", response.data["role_defaults"]["reception"])
        self.assertIn("company.manage", response.data["role_defaults"]["owner"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && DJANGO_TESTING=true python manage.py test apps.mobile.tests.test_bootstrap -v 2`
Expected: FAIL con `KeyError: 'permission_catalog'`.

- [ ] **Step 3: Implement**

In `backend/apps/tenancy/permissions.py`, add:

```python
def role_defaults_payload():
    catalog = set(PERMISSION_CATALOG)
    return {
        role: sorted(catalog if "*" in permissions else permissions)
        for role, permissions in ROLE_DEFAULTS.items()
    }
```

In `backend/apps/mobile/views.py`:

1. Import `PERMISSION_CATALOG, role_defaults_payload` from `apps.tenancy.permissions`.
2. In the bootstrap view, the membership is resolved at `backend/apps/mobile/views.py:49` with `request.user.memberships.filter(company=company, active=True).first()`; add `.select_related("default_branch")` to that queryset.
3. Add to the `user` dict: `"must_change_password": user.must_change_password`.
4. Add to the `membership` dict:

```python
"default_branch": (
    {"id": str(membership.default_branch_id), "name": membership.default_branch.name}
    if membership.default_branch_id else None
),
```

5. Add to the top-level payload:

```python
"permission_catalog": sorted(PERMISSION_CATALOG),
"role_defaults": role_defaults_payload(),
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && DJANGO_TESTING=true python manage.py test apps.mobile.tests.test_bootstrap -v 2`
Expected: tests nuevos y existentes PASS.

- [ ] **Step 5: Backend checkpoint**

Run:

```bash
cd backend && DJANGO_TESTING=true python manage.py test apps.identity apps.mobile apps.tenancy -v 1
```

Expected: toda la suite de esas apps PASS. No commit.

---

### Task 6: Capa API web de usuarios y permisos

**Files:**
- Modify: `web/src/api/types.ts`
- Create: `web/src/api/members.ts`
- Modify: `web/src/api/queryKeys.ts`, `web/src/api/runtime.ts`, `web/src/test/factories.ts`
- Test: `web/src/api/members.test.ts`

**Interfaces:**
- Produces: `Member`, `MemberRole`, `MemberInput`, `MemberUpdateInput`, `MemberCreateResult`, `PermissionGrant`, `PermissionGrantInput`, `createMembersApi(client)`, `MembersApi`.
- Consumes: `ApiClient.get/post/patch/delete`, `Paginated<T>`, `UUID`, `ISODateTime`.

- [ ] **Step 1: Write the failing test**

Create `web/src/api/members.test.ts`:

```ts
import { http, HttpResponse } from 'msw';
import { describe, expect, test } from 'vitest';

import { server } from '../test/server';
import { ApiClient } from './client';
import { createMembersApi } from './members';

const memberFixture = {
  id: 'membership-2',
  user_id: 'user-2',
  email: 'nueva@example.com',
  first_name: 'Nueva',
  last_name: 'Persona',
  role: 'reception',
  role_display: 'Recepción',
  default_branch: { id: 'branch-1', name: 'Providencia' },
  active: true,
  created_at: '2026-11-19T12:00:00Z',
};

function makeApi() {
  return createMembersApi(
    new ApiClient({
      baseUrl: 'http://api.test',
      getAccessToken: () => 'access-1',
      getTenantContextId: () => 'ctx-1',
    }),
  );
}

describe('membersApi', () => {
  test('crea el usuario con local y devuelve la clave temporal', async () => {
    let body: unknown = null;
    server.use(
      http.post('http://api.test/api/v1/members/', async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(
          { member: memberFixture, temporary_password: 'Temp-Phrase-123!', worker_profile: null },
          { status: 201 },
        );
      }),
    );

    const result = await makeApi().create({
      email: 'nueva@example.com',
      first_name: 'Nueva',
      role: 'reception',
      default_branch: 'branch-1',
    });

    expect(body).toMatchObject({
      email: 'nueva@example.com',
      role: 'reception',
      default_branch: 'branch-1',
    });
    expect(result.temporary_password).toBe('Temp-Phrase-123!');
  });

  test('filtra los permisos por membresía', async () => {
    let url = '';
    server.use(
      http.get('http://api.test/api/v1/permission-grants/', ({ request }) => {
        url = request.url;
        return HttpResponse.json({ count: 0, next: null, previous: null, results: [] });
      }),
    );

    await makeApi().grants.list({ membership: 'membership-2' });

    expect(url).toContain('membership=membership-2');
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && npm test -- src/api/members.test.ts`
Expected: FAIL con `Cannot find module './members'`.

- [ ] **Step 3: Create `web/src/api/members.ts`**

```ts
import type { ApiClient } from './client';
import type { Paginated, UUID } from './types';

export type MemberRole =
  | 'owner'
  | 'admin'
  | 'manager'
  | 'reception'
  | 'worker'
  | 'inventory'
  | 'accounting';

export type Member = {
  id: UUID;
  user_id: UUID;
  email: string;
  first_name: string;
  last_name: string;
  role: MemberRole;
  role_display: string;
  default_branch: { id: UUID; name: string } | null;
  active: boolean;
  created_at: string;
};

export type MemberInput = {
  email: string;
  first_name?: string;
  last_name?: string;
  role: MemberRole;
  default_branch?: UUID | null;
  create_worker_profile?: boolean;
};

export type MemberUpdateInput = {
  first_name?: string;
  last_name?: string;
  role?: MemberRole;
  default_branch?: UUID | null;
  active?: boolean;
};

export type MemberCreateResult = {
  member: Member;
  temporary_password: string;
  worker_profile: { id: UUID } | null;
};

export type PermissionGrant = {
  id: UUID;
  membership: UUID;
  permission: string;
  effect: 'allow' | 'deny';
  branch: UUID | null;
  created_at: string;
};

export type PermissionGrantInput = {
  membership: UUID;
  permission: string;
  effect: 'allow' | 'deny';
  branch?: UUID | null;
};

export function createMembersApi(client: ApiClient) {
  return {
    list: (params: { search?: string; page?: number } = {}) =>
      client.get<Paginated<Member>>('/api/v1/members/', { ...params }),
    create: (input: MemberInput) => client.post<MemberCreateResult>('/api/v1/members/', input),
    update: (id: UUID, input: MemberUpdateInput) =>
      client.patch<Member>(`/api/v1/members/${id}/`, input),
    remove: (id: UUID) => client.delete<void>(`/api/v1/members/${id}/`),
    grants: {
      list: (params: { membership: UUID; page?: number }) =>
        client.get<Paginated<PermissionGrant>>('/api/v1/permission-grants/', { ...params }),
      create: (input: PermissionGrantInput) =>
        client.post<PermissionGrant>('/api/v1/permission-grants/', input),
      remove: (id: UUID) => client.delete<void>(`/api/v1/permission-grants/${id}/`),
    },
  };
}

export type MembersApi = ReturnType<typeof createMembersApi>;
```

- [ ] **Step 4: Extend types, query keys, runtime and factories**

In `web/src/api/types.ts`, add `must_change_password?: boolean` to `User`, add:

```ts
export type BranchRef = { id: UUID; name: string };
```

and extend `Membership` with `default_branch: BranchRef | null;`; extend `Bootstrap` with `permission_catalog: string[];` and `role_defaults: Record<string, string[]>;`.

In `web/src/api/queryKeys.ts`:

```ts
  members: (companyId: UUID, params: object) => list('members', companyId, params),
  memberGrants: (companyId: UUID, membershipId: UUID) =>
    ['member-grants', companyId, membershipId] as const,
```

In `web/src/api/runtime.ts`:

```ts
import { createMembersApi } from './members';
...
export const membersApi = createMembersApi(apiClient);
```

In `web/src/test/factories.ts`, update `makeBootstrap` membership to:

```ts
    membership: { id: 'membership-1', role: 'owner', role_display: 'Propietario', default_branch: null },
```

and add before the spread:

```ts
    permission_catalog: [
      'bookings.read', 'bookings.write', 'customers.read', 'customers.write',
      'catalog.read', 'catalog.write', 'workforce.read', 'workforce.write',
      'reports.read', 'company.manage', 'branches.read', 'branches.manage',
      'subscription.read', 'subscription.manage',
    ],
    role_defaults: {
      owner: ['bookings.read', 'bookings.write', 'company.manage'],
      reception: ['bookings.read', 'bookings.write', 'customers.read'],
    },
```

- [ ] **Step 5: Run tests and type-check**

Run: `cd web && npm test -- src/api/members.test.ts`
Expected: 2 tests PASS.

Then run `cd web && npm run build` (TypeScript) y corrige cualquier propiedad faltante en fixtures/tests existentes.

---

### Task 7: La agenda web abre en el local predeterminado

**Files:**
- Create: `web/src/features/agenda/branchSelection.ts`
- Modify: `web/src/features/agenda/AgendaPage.tsx:44-55`
- Test: `web/src/features/agenda/branchSelection.test.ts`, `web/src/features/agenda/AgendaPage.test.tsx`

**Interfaces:**
- Produces: `pickInitialBranchId(branches: Branch[], preferred: string | null | undefined): string`.

- [ ] **Step 1: Write the failing unit test**

Create `web/src/features/agenda/branchSelection.test.ts`:

```ts
import { describe, expect, test } from 'vitest';

import type { Branch } from '../../api/types';
import { pickInitialBranchId } from './branchSelection';

function branch(id: string, active = true): Branch {
  return {
    id,
    company: 'company-a',
    name: id,
    code: id.toUpperCase(),
    address: '',
    timezone: 'America/Santiago',
    active,
  };
}

describe('pickInitialBranchId', () => {
  test('prefiere el local asignado cuando está activo', () => {
    expect(pickInitialBranchId([branch('a'), branch('b')], 'b')).toBe('b');
  });

  test('usa el primer local activo cuando el asignado está inactivo', () => {
    expect(pickInitialBranchId([branch('a'), branch('b', false)], 'b')).toBe('a');
  });

  test('usa el primer local activo cuando no hay preferencia', () => {
    expect(pickInitialBranchId([branch('a'), branch('b')], null)).toBe('a');
  });

  test('devuelve cadena vacía sin locales', () => {
    expect(pickInitialBranchId([], 'b')).toBe('');
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && npm test -- src/features/agenda/branchSelection.test.ts`
Expected: FAIL `Cannot find module './branchSelection'`.

- [ ] **Step 3: Implement**

Create `web/src/features/agenda/branchSelection.ts`:

```ts
import type { Branch } from '../../api/types';

export function pickInitialBranchId(
  branches: Branch[],
  preferred: string | null | undefined,
): string {
  const active = branches.filter((branch) => branch.active);
  if (preferred) {
    const match = active.find((branch) => branch.id === preferred);
    if (match) return match.id;
  }
  return active[0]?.id ?? '';
}
```

Modify `AgendaPage.tsx`:

```ts
import { useEffect, useMemo, useState } from 'react';
...
import { pickInitialBranchId } from './branchSelection';
```

```ts
  const preferredBranchId = bootstrap?.membership.default_branch?.id ?? null;
  const [branchId, setBranchId] = useState(() =>
    pickInitialBranchId(branches, preferredBranchId),
  );

  useEffect(() => {
    if (!branches.some((item) => item.id === branchId)) {
      setBranchId(pickInitialBranchId(branches, preferredBranchId));
    }
  }, [branches, branchId, preferredBranchId]);
```

- [ ] **Step 4: Write the AgendaPage regression test**

Add to `web/src/features/agenda/AgendaPage.test.tsx`:

```tsx
  test('abre la agenda en el local predeterminado del usuario', async () => {
    const urls: string[] = [];
    useAgendaHandlers(urls);
    const auth = makeAuthValue({
      bootstrap: makeBootstrap({
        membership: {
          id: 'membership-1',
          role: 'owner',
          role_display: 'Propietario',
          default_branch: { id: 'branch-2', name: 'Centro' },
        },
        branches: [
          {
            id: 'branch-1', company: 'company-a', name: 'Providencia', code: 'PROV',
            address: '', timezone: 'America/Santiago', active: true,
          },
          {
            id: 'branch-2', company: 'company-a', name: 'Centro', code: 'CEN',
            address: '', timezone: 'America/Santiago', active: true,
          },
        ],
      }),
    });
    renderAgenda(auth);

    await waitFor(() =>
      expect(screen.getByLabelText('Sucursal')).toHaveValue('branch-2'),
    );
    expect(urls[0]).toContain('branch=branch-2');
  });
```

Ensure `makeBootstrap` is imported in that test file (ya lo está).

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd web && npm test -- src/features/agenda/branchSelection.test.ts src/features/agenda/AgendaPage.test.tsx`
Expected: todos PASS.

---

### Task 8: Web — cambio de clave forzado

**Files:**
- Modify: `web/src/api/types.ts` (add `PasswordChangeResponse`)
- Modify: `web/src/api/auth.ts`
- Modify: `web/src/auth/AuthProvider.tsx`
- Modify: `web/src/app/guards.tsx`, `web/src/app/router.tsx`
- Create: `web/src/features/auth/ChangePasswordPage.tsx`
- Test: `web/src/features/auth/ChangePasswordPage.test.tsx`
- Modify: `web/src/test/factories.ts`

**Interfaces:**
- Produces: `AuthContextValue.changePassword(current, next): Promise<void>`; `ForcePasswordChange` guard; ruta `/cambiar-clave`.
- Consumes: `PasswordChangeResponse`, `SessionStore.writeRefresh`, `refreshBootstrap`.

- [ ] **Step 1: Write the failing test**

Create `web/src/features/auth/ChangePasswordPage.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, expect, test, vi } from 'vitest';

import { AuthContext } from '../../auth/AuthProvider';
import { makeAuthValue, makeBootstrap } from '../../test/factories';
import { ForcePasswordChange } from '../../app/guards';
import { ChangePasswordPage } from './ChangePasswordPage';

describe('cambio de clave forzado', () => {
  test('envía la clave actual y la nueva', async () => {
    const changePassword = vi.fn(async () => {});
    render(
      <MemoryRouter initialEntries={['/cambiar-clave']}>
        <AuthContext.Provider value={makeAuthValue({ changePassword })}>
          <Routes>
            <Route path="/cambiar-clave" element={<ChangePasswordPage />} />
            <Route path="/agenda" element={<div>Agenda lista</div>} />
          </Routes>
        </AuthContext.Provider>
      </MemoryRouter>,
    );

    await userEvent.type(screen.getByLabelText('Contraseña actual'), 'Vieja-Clave-123!');
    await userEvent.type(screen.getByLabelText('Nueva contraseña'), 'Nueva-Clave-456!');
    await userEvent.type(screen.getByLabelText('Repetir contraseña'), 'Nueva-Clave-456!');
    await userEvent.click(screen.getByRole('button', { name: 'Actualizar contraseña' }));

    expect(changePassword).toHaveBeenCalledWith('Vieja-Clave-123!', 'Nueva-Clave-456!');
    expect(await screen.findByText('Agenda lista')).toBeInTheDocument();
  });

  test('redirige fuera del panel cuando la clave ya fue cambiada', () => {
    render(
      <MemoryRouter initialEntries={['/']}>
        <AuthContext.Provider value={makeAuthValue()}>
          <Routes>
            <Route
              path="/"
              element={
                <ForcePasswordChange>
                  <div>Panel</div>
                </ForcePasswordChange>
              }
            />
            <Route path="/cambiar-clave" element={<div>Pantalla de cambio</div>} />
          </Routes>
        </AuthContext.Provider>
      </MemoryRouter>,
    );

    expect(screen.getByText('Panel')).toBeInTheDocument();
  });

  test('fuerza la pantalla cuando el bootstrap marca el cambio', () => {
    const bootstrap = makeBootstrap({
      user: { ...makeBootstrap().user, must_change_password: true },
    });
    render(
      <MemoryRouter initialEntries={['/']}>
        <AuthContext.Provider value={makeAuthValue({ bootstrap })}>
          <Routes>
            <Route
              path="/"
              element={
                <ForcePasswordChange>
                  <div>Panel</div>
                </ForcePasswordChange>
              }
            />
            <Route path="/cambiar-clave" element={<div>Pantalla de cambio</div>} />
          </Routes>
        </AuthContext.Provider>
      </MemoryRouter>,
    );

    expect(screen.getByText('Pantalla de cambio')).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && npm test -- src/features/auth/ChangePasswordPage.test.tsx`
Expected: FAIL `Cannot find module './ChangePasswordPage'` y `ForcePasswordChange` no exportado.

- [ ] **Step 3: Implement types, gateway and provider**

In `web/src/api/types.ts`:

```ts
export type PasswordChangeResponse = {
  access: string;
  refresh: string;
  must_change_password: boolean;
};
```

In `web/src/api/auth.ts` add import and method:

```ts
    changePassword: (current, next) =>
      client.post<PasswordChangeResponse>('/api/v1/auth/password/change/', {
        current_password: current,
        new_password: next,
      }),
```

In `web/src/auth/AuthProvider.tsx`:

```ts
import type { PasswordChangeResponse, ... } from '../api/types';
...
  changePassword(current: string, next: string): Promise<PasswordChangeResponse>;
...
  changePassword(currentPassword: string, newPassword: string): Promise<void>;
```

Add the method after `refreshBootstrap`:

```ts
  const changePassword = useCallback(
    async (currentPassword: string, newPassword: string) => {
      const data = await gateway.changePassword(currentPassword, newPassword);
      runtime.accessToken = data.access;
      store.writeRefresh(data.refresh);
      await refreshBootstrap();
    },
    [gateway, refreshBootstrap, runtime, store],
  );
```

Include `changePassword` in the memoized value and its dependency array.

- [ ] **Step 4: Add the guard, page and route**

In `web/src/app/guards.tsx`:

```tsx
export function ForcePasswordChange({ children }: { children: ReactNode }) {
  const { status, bootstrap } = useAuth();
  if (status === 'loading') return <FullPageLoading />;
  if (bootstrap?.user.must_change_password) return <Navigate to="/cambiar-clave" replace />;
  return <>{children}</>;
}
```

Create `web/src/features/auth/ChangePasswordPage.tsx`:

```tsx
import { zodResolver } from '@hookform/resolvers/zod';
import { useForm } from 'react-hook-form';
import { useNavigate } from 'react-router-dom';
import { z } from 'zod';

import { ApiError } from '../../api/client';
import { useAuth } from '../../auth/AuthProvider';
import { Button } from '../../components/ui/Button';
import { ErrorBanner } from '../../components/ui/ErrorBanner';
import { Field, Input } from '../../components/ui/Field';
import { firstAllowedPath } from '../../lib/permissions';

const schema = z
  .object({
    current_password: z.string().min(1, 'Ingresa tu contraseña actual.'),
    new_password: z.string().min(12, 'Usa al menos 12 caracteres.'),
    confirm_password: z.string().min(1, 'Repite la nueva contraseña.'),
  })
  .refine((values) => values.new_password === values.confirm_password, {
    message: 'Las contraseñas no coinciden.',
    path: ['confirm_password'],
  });

type FormValues = z.infer<typeof schema>;

export function ChangePasswordPage() {
  const { changePassword, can, hasFeature } = useAuth();
  const navigate = useNavigate();
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  const onSubmit = handleSubmit(async (values) => {
    try {
      await changePassword(values.current_password, values.new_password);
      navigate(firstAllowedPath(can, hasFeature), { replace: true });
    } catch (error) {
      const message =
        error instanceof ApiError ? error.message : 'No se pudo cambiar la contraseña.';
      setError('root', { message });
    }
  });

  return (
    <main className="mx-auto flex min-h-screen max-w-md items-center px-6">
      <section className="w-full rounded-lg border border-line bg-panel p-8">
        <h1 className="text-xl font-semibold text-ink">Cambia tu contraseña</h1>
        <p className="mt-2 text-sm text-muted">
          Usaste una clave temporal. Define una contraseña propia para continuar.
        </p>
        <form className="mt-6 space-y-4" onSubmit={onSubmit} noValidate>
          {errors.root?.message ? <ErrorBanner message={errors.root.message} /> : null}
          <Field label="Contraseña actual" htmlFor="password-current" error={errors.current_password?.message}>
            <Input
              id="password-current"
              type="password"
              autoComplete="current-password"
              {...register('current_password')}
            />
          </Field>
          <Field label="Nueva contraseña" htmlFor="password-new" error={errors.new_password?.message}>
            <Input
              id="password-new"
              type="password"
              autoComplete="new-password"
              {...register('new_password')}
            />
          </Field>
          <Field label="Repetir contraseña" htmlFor="password-confirm" error={errors.confirm_password?.message}>
            <Input
              id="password-confirm"
              type="password"
              autoComplete="new-password"
              {...register('confirm_password')}
            />
          </Field>
          <Button type="submit" loading={isSubmitting} loadingLabel="Actualizando…">
            Actualizar contraseña
          </Button>
        </form>
      </section>
    </main>
  );
}
```

In `web/src/app/router.tsx`:

- Import `ChangePasswordPage` and `ForcePasswordChange`.
- Add the route before `/`:

```tsx
  {
    path: '/cambiar-clave',
    element: (
      <RequireAuthenticated>
        <RequireReady>
          <ChangePasswordPage />
        </RequireReady>
      </RequireAuthenticated>
    ),
  },
```

- Wrap `<AppLayout />`:

```tsx
        <RequireReady>
          <ForcePasswordChange>
            <AppLayout />
          </ForcePasswordChange>
        </RequireReady>
```

In `web/src/test/factories.ts`, add to `makeGateway`:

```ts
    changePassword: vi.fn(
      overrides.changePassword ??
        (async () => ({ access: 'access-c', refresh: 'refresh-c', must_change_password: false })),
    ),
```

and to `makeAuthValue`:

```ts
    changePassword: vi.fn(async () => {}),
```

- [ ] **Step 5: Run tests and build**

Run: `cd web && npm test -- src/features/auth/ChangePasswordPage.test.tsx`
Expected: 3 tests PASS.

Run: `cd web && npm run build`
Expected: build OK (verifica que ninguna fixture de `Bootstrap` quedó sin los campos nuevos).

---

### Task 9: Web — sección Usuarios (alta, clave temporal, edición, baja)

**Files:**
- Create: `web/src/features/members/memberRoles.ts`
- Create: `web/src/features/members/CredentialsDialog.tsx`
- Create: `web/src/features/members/MemberFormDialog.tsx`
- Create: `web/src/features/members/MembersPage.tsx`
- Modify: `web/src/lib/permissions.ts:21-29`
- Modify: `web/src/app/router.tsx`
- Test: `web/src/features/members/MembersPage.test.tsx`

**Interfaces:**
- Consumes: `membersApi`, `queryKeys.members`, `MEMBER_ROLES`, `useAuth` (`bootstrap`, `user`).
- Produces: `MembersPage`; `MemberFormDialog({open, member, onOpenChange, onSaved})`; `CredentialsDialog({open, onOpenChange, email, password})`; `MEMBER_ROLES`.

- [ ] **Step 1: Write the failing test**

Create `web/src/features/members/MembersPage.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, test } from 'vitest';

import type { Member } from '../../api/members';
import { AuthContext } from '../../auth/AuthProvider';
import { makeAuthValue } from '../../test/factories';
import { server } from '../../test/server';
import { MembersPage } from './MembersPage';

const memberFixture: Member = {
  id: 'membership-2',
  user_id: 'user-2',
  email: 'nueva@example.com',
  first_name: 'Nueva',
  last_name: 'Persona',
  role: 'reception',
  role_display: 'Recepción',
  default_branch: { id: 'branch-1', name: 'Providencia' },
  active: true,
  created_at: '2026-11-19T12:00:00Z',
};

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <MemoryRouter>
      <AuthContext.Provider value={makeAuthValue()}>
        <QueryClientProvider client={queryClient}>
          <MembersPage />
        </QueryClientProvider>
      </AuthContext.Provider>
    </MemoryRouter>,
  );
}

describe('MembersPage', () => {
  test('lista usuarios y muestra el local asignado', async () => {
    server.use(
      http.get('http://api.test/api/v1/members/', () =>
        HttpResponse.json({ count: 1, next: null, previous: null, results: [memberFixture] }),
      ),
    );
    renderPage();

    expect(await screen.findByText('nueva@example.com')).toBeInTheDocument();
    expect(screen.getByText('Providencia')).toBeInTheDocument();
    expect(screen.getByText('Recepción')).toBeInTheDocument();
  });

  test('crea un usuario y muestra la clave temporal una sola vez', async () => {
    let body: unknown = null;
    server.use(
      http.get('http://api.test/api/v1/members/', () =>
        HttpResponse.json({ count: 0, next: null, previous: null, results: [] }),
      ),
      http.post('http://api.test/api/v1/members/', async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(
          { member: memberFixture, temporary_password: 'Temp-Phrase-123!', worker_profile: null },
          { status: 201 },
        );
      }),
    );
    renderPage();

    await screen.findByText('Todavía no hay usuarios.');
    await userEvent.click(screen.getByRole('button', { name: 'Nuevo usuario' }));
    await userEvent.type(screen.getByLabelText('Correo'), 'nueva@example.com');
    await userEvent.type(screen.getByLabelText('Nombre'), 'Nueva');
    await userEvent.selectOptions(screen.getByLabelText('Rol'), 'reception');
    await userEvent.selectOptions(screen.getByLabelText('Local predeterminado'), 'branch-1');
    await userEvent.click(screen.getByRole('button', { name: 'Crear usuario' }));

    await waitFor(() => expect(body).toMatchObject({
      email: 'nueva@example.com',
      role: 'reception',
      default_branch: 'branch-1',
    }));
    expect(await screen.findByText('Temp-Phrase-123!')).toBeInTheDocument();
    expect(screen.getByText('Credenciales de acceso')).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && npm test -- src/features/members/MembersPage.test.tsx`
Expected: FAIL `Cannot find module './MembersPage'`.

- [ ] **Step 3: Create roles, credentials dialog and form**

`web/src/features/members/memberRoles.ts`:

```ts
import type { MemberRole } from '../../api/members';

export const MEMBER_ROLES: { value: MemberRole; label: string }[] = [
  { value: 'owner', label: 'Propietario' },
  { value: 'admin', label: 'Administrador' },
  { value: 'manager', label: 'Supervisor' },
  { value: 'reception', label: 'Recepción' },
  { value: 'worker', label: 'Trabajador' },
  { value: 'inventory', label: 'Inventario' },
  { value: 'accounting', label: 'Contabilidad' },
];

export function roleLabel(role: string): string {
  return MEMBER_ROLES.find((item) => item.value === role)?.label ?? role;
}
```

`web/src/features/members/CredentialsDialog.tsx`:

```tsx
import { Button } from '../../components/ui/Button';
import { Dialog } from '../../components/ui/Dialog';

export function CredentialsDialog({
  open,
  onOpenChange,
  email,
  password,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  email: string;
  password: string;
}) {
  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title="Credenciales de acceso"
      description="Entrega esta clave al usuario. No se volverá a mostrar."
      footer={<Button onClick={() => onOpenChange(false)}>Entendido</Button>}
    >
      <dl className="space-y-3 text-sm">
        <div>
          <dt className="text-muted">Correo</dt>
          <dd className="mt-1 font-medium text-ink">{email}</dd>
        </div>
        <div>
          <dt className="text-muted">Clave temporal</dt>
          <dd className="mt-1">
            <code
              data-testid="temporary-password"
              className="rounded bg-surface px-2 py-1 font-mono text-ink"
            >
              {password}
            </code>
          </dd>
        </div>
      </dl>
      <p className="mt-4 text-xs text-muted">
        Al primer ingreso se pedirá cambiarla por una contraseña propia.
      </p>
    </Dialog>
  );
}
```

`web/src/features/members/MemberFormDialog.tsx`:

```tsx
import { zodResolver } from '@hookform/resolvers/zod';
import { useMutation } from '@tanstack/react-query';
import { useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';

import { ApiError } from '../../api/client';
import type { Member, MemberInput, MemberRole, MemberUpdateInput } from '../../api/members';
import { membersApi } from '../../api/runtime';
import { useAuth } from '../../auth/AuthProvider';
import { Button } from '../../components/ui/Button';
import { Dialog } from '../../components/ui/Dialog';
import { ErrorBanner } from '../../components/ui/ErrorBanner';
import { Field, FormRow, Input, Select } from '../../components/ui/Field';
import { MEMBER_ROLES } from './memberRoles';

const schema = z.object({
  email: z.string().trim().email('Ingresa un correo válido.'),
  first_name: z.string().trim().max(150, 'Máximo 150 caracteres.'),
  last_name: z.string().trim().max(150, 'Máximo 150 caracteres.'),
  role: z.string().min(1, 'Selecciona un rol.'),
  default_branch: z.string(),
  create_worker_profile: z.boolean(),
});

type FormValues = z.infer<typeof schema>;

function valuesFrom(member: Member | null): FormValues {
  return {
    email: member?.email ?? '',
    first_name: member?.first_name ?? '',
    last_name: member?.last_name ?? '',
    role: member?.role ?? 'reception',
    default_branch: member?.default_branch?.id ?? '',
    create_worker_profile: false,
  };
}

export function MemberFormDialog({
  open,
  member,
  onOpenChange,
  onSaved,
  onCreated,
}: {
  open: boolean;
  member: Member | null;
  onOpenChange: (open: boolean) => void;
  onSaved: () => void;
  onCreated: (email: string, password: string) => void;
}) {
  const { bootstrap, user } = useAuth();
  const branches = (bootstrap?.branches ?? []).filter((branch) => branch.active);
  const isOwner = bootstrap?.membership.role === 'owner';
  const roles = MEMBER_ROLES.filter(
    (item) => isOwner || (item.value !== 'owner' && item.value !== 'admin'),
  );
  const {
    register,
    handleSubmit,
    setError,
    reset,
    watch,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: valuesFrom(member),
  });
  const role = watch('role');

  useEffect(() => {
    if (open) reset(valuesFrom(member));
  }, [open, member, reset]);

  const mutation = useMutation({
    mutationFn: async (values: FormValues) => {
      if (member) {
        const input: MemberUpdateInput = {
          first_name: values.first_name,
          last_name: values.last_name,
          role: values.role as MemberRole,
          default_branch: values.default_branch || null,
        };
        return { kind: 'updated' as const, member: await membersApi.update(member.id, input) };
      }
      const input: MemberInput = {
        email: values.email,
        first_name: values.first_name,
        last_name: values.last_name,
        role: values.role as MemberRole,
        default_branch: values.default_branch || null,
        create_worker_profile: values.create_worker_profile,
      };
      return { kind: 'created' as const, result: await membersApi.create(input) };
    },
    onSuccess: (result) => {
      onSaved();
      onOpenChange(false);
      if (result.kind === 'created') {
        onCreated(result.result.member.email, result.result.temporary_password);
      }
    },
    onError: (error) => {
      if (!(error instanceof ApiError) || !error.fields) return;
      Object.entries(error.fields).forEach(([field, messages]) => {
        if (field === 'email' || field === 'default_branch' || field === 'role') {
          setError(field, { message: messages[0] });
        }
      });
    },
  });

  const onSubmit = handleSubmit((values) => {
    if (member && member.role === 'owner' && user?.id === member.user_id) {
      return;
    }
    mutation.mutate(values);
  });

  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title={member ? 'Editar usuario' : 'Nuevo usuario'}
      description="El local predeterminado se usa al abrir la agenda, pero puede cambiarse."
      wide
    >
      <form className="space-y-4" onSubmit={onSubmit} noValidate>
        {mutation.error && !(mutation.error instanceof ApiError && mutation.error.fields) ? (
          <ErrorBanner
            message={
              mutation.error instanceof ApiError
                ? mutation.error.message
                : 'No se pudo guardar el usuario.'
            }
          />
        ) : null}

        <FormRow>
          <Field label="Correo" htmlFor="member-email" error={errors.email?.message}>
            <Input
              id="member-email"
              type="email"
              autoComplete="email"
              disabled={Boolean(member)}
              {...register('email')}
            />
          </Field>
          <Field label="Rol" htmlFor="member-role" error={errors.role?.message}>
            <Select id="member-role" {...register('role')}>
              {roles.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </Select>
          </Field>
        </FormRow>

        <FormRow>
          <Field label="Nombre" htmlFor="member-first-name" error={errors.first_name?.message}>
            <Input id="member-first-name" autoComplete="given-name" {...register('first_name')} />
          </Field>
          <Field label="Apellido" htmlFor="member-last-name" error={errors.last_name?.message}>
            <Input id="member-last-name" autoComplete="family-name" {...register('last_name')} />
          </Field>
        </FormRow>

        <Field
          label="Local predeterminado"
          htmlFor="member-branch"
          hint="Si se desactiva o elimina, la agenda usará el primer local activo."
          error={errors.default_branch?.message}
        >
          <Select id="member-branch" {...register('default_branch')}>
            <option value="">Sin local predeterminado</option>
            {branches.map((branch) => (
              <option key={branch.id} value={branch.id}>
                {branch.name}
              </option>
            ))}
          </Select>
        </Field>

        {!member && role === 'worker' ? (
          <label className="flex items-center gap-2 text-sm text-ink">
            <input
              type="checkbox"
              className="h-4 w-4 accent-brand"
              {...register('create_worker_profile')}
            />
            Crear también el perfil de trabajador en el local
          </label>
        ) : null}

        <div className="flex justify-end gap-2 pt-2">
          <Button type="button" variant="secondary" onClick={() => onOpenChange(false)}>
            Cancelar
          </Button>
          <Button type="submit" loading={mutation.isPending} loadingLabel="Guardando…">
            {member ? 'Guardar cambios' : 'Crear usuario'}
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
```

- [ ] **Step 4: Create `MembersPage.tsx`**

```tsx
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import type { Member } from '../../api/members';
import { queryKeys } from '../../api/queryKeys';
import { membersApi } from '../../api/runtime';
import { useAuth } from '../../auth/AuthProvider';
import { Badge } from '../../components/ui/Badge';
import { Button } from '../../components/ui/Button';
import { ConfirmDialog } from '../../components/ui/Dialog';
import { EmptyState } from '../../components/ui/EmptyState';
import { ErrorBanner } from '../../components/ui/ErrorBanner';
import { PageHeader } from '../../components/ui/PageHeader';
import { Pagination } from '../../components/ui/Pagination';
import { Input } from '../../components/ui/Field';
import { CredentialsDialog } from './CredentialsDialog';
import { MemberFormDialog } from './MemberFormDialog';
import { roleLabel } from './memberRoles';

export function MembersPage() {
  const { company, bootstrap, user } = useAuth();
  const queryClient = useQueryClient();
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Member | null>(null);
  const [removing, setRemoving] = useState<Member | null>(null);
  const [credentials, setCredentials] = useState<{ email: string; password: string } | null>(null);

  const params = { search: search.trim() || undefined, page };
  const membersQuery = useQuery({
    queryKey: queryKeys.members(company?.id ?? '', params),
    queryFn: () => membersApi.list(params),
    enabled: Boolean(company),
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['members'] });
  };

  const deactivate = useMutation({
    mutationFn: (member: Member) => membersApi.remove(member.id),
    onSuccess: () => {
      invalidate();
      setRemoving(null);
    },
  });

  const activate = useMutation({
    mutationFn: (member: Member) => membersApi.update(member.id, { active: true }),
    onSuccess: invalidate,
  });

  const isOwner = bootstrap?.membership.role === 'owner';
  const canManage = (member: Member) =>
    isOwner || (member.role !== 'owner' && member.role !== 'admin');
  const rows = membersQuery.data?.results ?? [];

  return (
    <section>
      <PageHeader
        title="Usuarios"
        description="Crea accesos, asigna un local predeterminado y ajusta permisos."
        actions={
          <Button
            onClick={() => {
              setEditing(null);
              setFormOpen(true);
            }}
          >
            Nuevo usuario
          </Button>
        }
      />

      <div className="mb-4 max-w-sm">
        <Input
          aria-label="Buscar"
          placeholder="Buscar por correo o nombre"
          value={search}
          onChange={(event) => {
            setSearch(event.target.value);
            setPage(1);
          }}
        />
      </div>

      {membersQuery.error ? (
        <ErrorBanner message="No se pudieron cargar los usuarios." />
      ) : null}

      {!membersQuery.isLoading && rows.length === 0 ? (
        <EmptyState
          title="Todavía no hay usuarios."
          description="Crea el primero y entrega la clave temporal una sola vez."
        />
      ) : null}

      {rows.length > 0 ? (
        <div className="overflow-x-auto rounded-lg border border-line bg-panel">
          <table className="min-w-full text-sm">
            <thead className="border-b border-line text-left text-xs uppercase text-muted">
              <tr>
                <th className="px-4 py-3">Usuario</th>
                <th className="px-4 py-3">Rol</th>
                <th className="px-4 py-3">Local</th>
                <th className="px-4 py-3">Estado</th>
                <th className="px-4 py-3">Acciones</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((member) => (
                <tr key={member.id} className="border-b border-line last:border-0">
                  <td className="px-4 py-3">
                    <div className="font-medium text-ink">
                      {[member.first_name, member.last_name].filter(Boolean).join(' ') || member.email}
                    </div>
                    <div className="text-xs text-muted">{member.email}</div>
                  </td>
                  <td className="px-4 py-3">{roleLabel(member.role)}</td>
                  <td className="px-4 py-3">{member.default_branch?.name ?? '—'}</td>
                  <td className="px-4 py-3">
                    <Badge tone={member.active ? 'active' : 'inactive'}>
                      {member.active ? 'Activo' : 'Inactivo'}
                    </Badge>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-2">
                      {canManage(member) ? (
                        <>
                          <Button
                            variant="secondary"
                            onClick={() => {
                              setEditing(member);
                              setFormOpen(true);
                            }}
                          >
                            Editar
                          </Button>
                          {member.active ? (
                            <Button
                              variant="danger"
                              disabled={member.user_id === user?.id}
                              onClick={() => setRemoving(member)}
                            >
                              Desactivar
                            </Button>
                          ) : (
                            <Button variant="secondary" onClick={() => activate.mutate(member)}>
                              Reactivar
                            </Button>
                          )}
                        </>
                      ) : (
                        <span className="text-xs text-muted">Solo el propietario</span>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      <Pagination
        page={page}
        count={membersQuery.data?.count ?? 0}
        onPage={setPage}
      />

      <MemberFormDialog
        open={formOpen}
        member={editing}
        onOpenChange={(next) => {
          setFormOpen(next);
          if (!next) setEditing(null);
        }}
        onSaved={invalidate}
        onCreated={(email, password) => setCredentials({ email, password })}
      />

      <CredentialsDialog
        open={Boolean(credentials)}
        onOpenChange={(next) => {
          if (!next) setCredentials(null);
        }}
        email={credentials?.email ?? ''}
        password={credentials?.password ?? ''}
      />

      <ConfirmDialog
        open={Boolean(removing)}
        onOpenChange={(next) => {
          if (!next) setRemoving(null);
        }}
        title="Desactivar usuario"
        description="El usuario perderá acceso a esta empresa, pero conservará sus datos."
        confirmLabel="Desactivar"
        danger
        loading={deactivate.isPending}
        onConfirm={() => {
          if (removing) deactivate.mutate(removing);
        }}
      />
    </section>
  );
}
```

El botón «Permisos» y su editor se agregan en Task 10.

- [ ] **Step 4b: Run the page tests**

Run: `cd web && npm test -- src/features/members/MembersPage.test.tsx`
Expected: PASS.

- [ ] **Step 5: Register nav and route**

In `web/src/lib/permissions.ts` add to `NAV_ITEMS` before `/marca`:

```ts
  { path: '/usuarios', label: 'Usuarios', permission: 'company.manage' },
```

In `web/src/app/router.tsx`, import `MembersPage` and add:

```tsx
      {
        path: 'usuarios',
        element: (
          <RequirePermission permission="company.manage">
            <MembersPage />
          </RequirePermission>
        ),
      },
```

- [ ] **Step 6: Run tests**

Run: `cd web && npm test -- src/features/members/MembersPage.test.tsx`
Expected: 2 tests PASS.

Run: `cd web && npm run lint && npm run build`
Expected: sin errores.

---

### Task 10: Web — editor de permisos y conexión en Usuarios

**Files:**
- Create: `web/src/features/members/permissionLabels.ts`
- Create: `web/src/features/members/PermissionsDialog.tsx`
- Modify: `web/src/features/members/MembersPage.tsx`
- Test: `web/src/features/members/PermissionsDialog.test.tsx`

**Interfaces:**
- Consumes: `membersApi.grants`, `queryKeys.memberGrants`, `bootstrap.permission_catalog`, `bootstrap.role_defaults`, `bootstrap.branches`.
- Produces: `PermissionsDialog({ open, member, onOpenChange, onSaved })`.

- [ ] **Step 1: Write the failing test**

Create `web/src/features/members/PermissionsDialog.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { describe, expect, test, vi } from 'vitest';

import type { Member } from '../../api/members';
import { AuthContext } from '../../auth/AuthProvider';
import { makeAuthValue } from '../../test/factories';
import { server } from '../../test/server';
import { PermissionsDialog } from './PermissionsDialog';

const member: Member = {
  id: 'membership-2',
  user_id: 'user-2',
  email: 'reception@example.com',
  first_name: 'Rita',
  last_name: 'Recepción',
  role: 'reception',
  role_display: 'Recepción',
  default_branch: { id: 'branch-1', name: 'Providencia' },
  active: true,
  created_at: '2026-11-19T12:00:00Z',
};

describe('PermissionsDialog', () => {
  test('crea un permiso denegado en un local', async () => {
    let body: unknown = null;
    server.use(
      http.get('http://api.test/api/v1/permission-grants/', () =>
        HttpResponse.json({ count: 0, next: null, previous: null, results: [] }),
      ),
      http.post('http://api.test/api/v1/permission-grants/', async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(
          {
            id: 'grant-1',
            membership: 'membership-2',
            permission: 'bookings.write',
            effect: 'deny',
            branch: 'branch-1',
            created_at: '2026-11-19T12:00:00Z',
          },
          { status: 201 },
        );
      }),
    );
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <AuthContext.Provider value={makeAuthValue()}>
        <QueryClientProvider client={queryClient}>
          <PermissionsDialog
            open
            member={member}
            onOpenChange={vi.fn()}
            onSaved={vi.fn()}
          />
        </QueryClientProvider>
      </AuthContext.Provider>,
    );

    await screen.findByText('Gestionar reservas');
    await userEvent.selectOptions(
      screen.getByLabelText('Efecto para Gestionar reservas'),
      'deny',
    );
    await userEvent.selectOptions(
      screen.getByLabelText('Alcance para Gestionar reservas'),
      'branch-1',
    );
    await userEvent.click(screen.getByRole('button', { name: 'Guardar permisos' }));

    await waitFor(() =>
      expect(body).toEqual({
        membership: 'membership-2',
        permission: 'bookings.write',
        effect: 'deny',
        branch: 'branch-1',
      }),
    );
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && npm test -- src/features/members/PermissionsDialog.test.tsx`
Expected: FAIL con `Failed to resolve import "./PermissionsDialog"`.

- [ ] **Step 3: Create `permissionLabels.ts`**

```ts
const LABELS: Record<string, string> = {
  'bookings.read': 'Ver reservas',
  'bookings.write': 'Gestionar reservas',
  'bookings.own.read': 'Ver sus reservas',
  'bookings.own.write': 'Gestionar sus reservas',
  'customers.read': 'Ver clientes',
  'customers.write': 'Gestionar clientes',
  'customers.assigned.read': 'Ver clientes asignados',
  'catalog.read': 'Ver servicios',
  'catalog.write': 'Gestionar servicios',
  'workforce.read': 'Ver equipo',
  'workforce.write': 'Gestionar equipo',
  'inventory.read': 'Ver inventario',
  'inventory.write': 'Gestionar inventario',
  'purchases.read': 'Ver compras',
  'purchases.write': 'Gestionar compras',
  'sales.read': 'Ver ventas',
  'sales.write': 'Gestionar ventas',
  'cash.read': 'Ver caja',
  'cash.manage': 'Gestionar caja',
  'payments.read': 'Ver pagos',
  'expenses.read': 'Ver gastos',
  'expenses.write': 'Gestionar gastos',
  'reports.read': 'Ver reportes',
  'subscription.read': 'Ver suscripción',
  'subscription.manage': 'Gestionar suscripción',
  'branches.read': 'Ver locales',
  'branches.manage': 'Gestionar locales',
  'company.manage': 'Administrar empresa',
};

const GROUPS: Record<string, string> = {
  bookings: 'Reservas', customers: 'Clientes', catalog: 'Servicios',
  workforce: 'Equipo', inventory: 'Inventario', purchases: 'Compras',
  sales: 'Ventas', cash: 'Caja', payments: 'Pagos', expenses: 'Gastos',
  reports: 'Reportes', subscription: 'Suscripción', branches: 'Locales',
  company: 'Empresa',
};

export function permissionLabel(code: string): string {
  return LABELS[code] ?? code;
}

export function permissionGroup(code: string): string {
  return GROUPS[code.split('.')[0]] ?? 'Otros';
}
```

- [ ] **Step 4: Create `PermissionsDialog.tsx`**

```tsx
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import type { Member } from '../../api/members';
import { queryKeys } from '../../api/queryKeys';
import { membersApi } from '../../api/runtime';
import { useAuth } from '../../auth/AuthProvider';
import { Button } from '../../components/ui/Button';
import { Dialog } from '../../components/ui/Dialog';
import { ErrorBanner } from '../../components/ui/ErrorBanner';
import { Select } from '../../components/ui/Field';
import { permissionGroup, permissionLabel } from './permissionLabels';

type Effect = 'inherit' | 'allow' | 'deny';
type Row = { effect: Effect; branch: string };

export function PermissionsDialog({
  open,
  member,
  onOpenChange,
  onSaved,
}: {
  open: boolean;
  member: Member;
  onOpenChange: (open: boolean) => void;
  onSaved: () => void;
}) {
  const { company, bootstrap } = useAuth();
  const queryClient = useQueryClient();
  const catalog = bootstrap?.permission_catalog ?? [];
  const defaults = new Set(bootstrap?.role_defaults?.[member.role] ?? []);
  const branches = (bootstrap?.branches ?? []).filter((branch) => branch.active);

  const grantsQuery = useQuery({
    queryKey: queryKeys.memberGrants(company?.id ?? '', member.id),
    queryFn: () => membersApi.grants.list({ membership: member.id, page: 1 }),
    enabled: open,
  });

  if (grantsQuery.isLoading || !grantsQuery.data) {
    return (
      <Dialog open={open} onOpenChange={onOpenChange} title="Permisos" wide>
        <p className="text-sm text-muted">Cargando permisos…</p>
      </Dialog>
    );
  }

  return (
    <PermissionMatrix
      key={`${member.id}:${grantsQuery.data.results.map((grant) => grant.id).join(',')}`}
      open={open}
      onOpenChange={onOpenChange}
      onSaved={onSaved}
      member={member}
      catalog={catalog}
      branches={branches}
      defaults={defaults}
      grants={grantsQuery.data.results}
      onInvalidate={() =>
        queryClient.invalidateQueries({
          queryKey: queryKeys.memberGrants(company?.id ?? '', member.id),
        })
      }
    />
  );
}

function PermissionMatrix({
  open,
  onOpenChange,
  onSaved,
  member,
  catalog,
  branches,
  defaults,
  grants,
  onInvalidate,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSaved: () => void;
  member: Member;
  catalog: string[];
  branches: { id: string; name: string }[];
  defaults: Set<string>;
  grants: { id: string; permission: string; effect: 'allow' | 'deny'; branch: string | null }[];
  onInvalidate: () => void;
}) {
  const [rows, setRows] = useState<Record<string, Row>>(() => {
    const initial: Record<string, Row> = {};
    for (const permission of catalog) {
      const grant = grants.find((item) => item.permission === permission);
      initial[permission] = grant
        ? { effect: grant.effect, branch: grant.branch ?? '' }
        : { effect: 'inherit', branch: '' };
    }
    return initial;
  });

  const mutation = useMutation({
    mutationFn: async () => {
      for (const permission of catalog) {
        const row = rows[permission] ?? { effect: 'inherit' as Effect, branch: '' };
        const current = grants.filter((grant) => grant.permission === permission);
        const signature =
          current.length === 0
            ? 'inherit'
            : current.length === 1
              ? `${current[0].effect}:${current[0].branch ?? ''}`
              : 'multi';
        const desired = row.effect === 'inherit' ? 'inherit' : `${row.effect}:${row.branch}`;
        if (signature === desired) continue;
        for (const grant of current) {
          await membersApi.grants.remove(grant.id);
        }
        if (row.effect !== 'inherit') {
          await membersApi.grants.create({
            membership: member.id,
            permission,
            effect: row.effect,
            branch: row.branch || null,
          });
        }
      }
    },
    onSuccess: () => {
      onInvalidate();
      onSaved();
      onOpenChange(false);
    },
  });

  const groups = Array.from(new Set(catalog.map(permissionGroup)));

  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title={`Permisos de ${member.first_name || member.email}`}
      description="Lo heredado usa los permisos del rol. Permitir o denegar lo reemplaza en toda la empresa o en un local."
      wide
      footer={
        <>
          <Button variant="secondary" onClick={() => onOpenChange(false)}>
            Cancelar
          </Button>
          <Button
            onClick={() => mutation.mutate()}
            loading={mutation.isPending}
            loadingLabel="Guardando…"
          >
            Guardar permisos
          </Button>
        </>
      }
    >
      {mutation.error ? <ErrorBanner message="No se pudieron guardar los permisos." /> : null}
      <div className="space-y-5">
        {groups.map((group) => (
          <section key={group}>
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">
              {group}
            </h3>
            <div className="space-y-2">
              {catalog
                .filter((permission) => permissionGroup(permission) === group)
                .map((permission) => {
                  const row = rows[permission];
                  return (
                    <div
                      key={permission}
                      className="grid items-center gap-2 sm:grid-cols-[1fr_150px_170px]"
                    >
                      <div className="text-sm text-ink">
                        {permissionLabel(permission)}
                        <span className="ml-2 text-xs text-muted">
                          {defaults.has(permission) ? 'Rol: permitido' : 'Rol: sin acceso'}
                        </span>
                      </div>
                      <Select
                        aria-label={`Efecto para ${permissionLabel(permission)}`}
                        value={row.effect}
                        onChange={(event) =>
                          setRows((current) => ({
                            ...current,
                            [permission]: { ...row, effect: event.target.value as Effect },
                          }))
                        }
                      >
                        <option value="inherit">Heredado</option>
                        <option value="allow">Permitir</option>
                        <option value="deny">Denegar</option>
                      </Select>
                      <Select
                        aria-label={`Alcance para ${permissionLabel(permission)}`}
                        value={row.branch}
                        disabled={row.effect === 'inherit'}
                        onChange={(event) =>
                          setRows((current) => ({
                            ...current,
                            [permission]: { ...row, branch: event.target.value },
                          }))
                        }
                      >
                        <option value="">Toda la empresa</option>
                        {branches.map((branch) => (
                          <option key={branch.id} value={branch.id}>
                            {branch.name}
                          </option>
                        ))}
                      </Select>
                    </div>
                  );
                })}
            </div>
          </section>
        ))}
      </div>
    </Dialog>
  );
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd web && npm test -- src/features/members/PermissionsDialog.test.tsx`
Expected: PASS y body exacto.

- [ ] **Step 6: Wire the editor into `MembersPage`**

Add the import:

```tsx
import { PermissionsDialog } from './PermissionsDialog';
```

Add the state next to the other dialog states:

```tsx
  const [permissionsFor, setPermissionsFor] = useState<Member | null>(null);
```

Add the button inside the `canManage` actions, after «Editar»:

```tsx
                          <Button variant="secondary" onClick={() => setPermissionsFor(member)}>
                            Permisos
                          </Button>
```

Render the dialog next to `CredentialsDialog`:

```tsx
      {permissionsFor ? (
        <PermissionsDialog
          open={Boolean(permissionsFor)}
          member={permissionsFor}
          onOpenChange={(next) => {
            if (!next) setPermissionsFor(null);
          }}
          onSaved={invalidate}
        />
      ) : null}
```

- [ ] **Step 7: Run the web checks**

Run: `cd web && npm test -- src/features/members`
Expected: PASS.

Run: `cd web && npm run lint && npm run build`
Expected: sin errores.

---

### Task 11: E2E — alta de usuario, cambio forzado y local en agenda

**Files:**
- Create: `web/e2e/members.spec.ts`

**Interfaces:**
- Consumes: `installSession`, `readSharedSession`, `seedCompany`, `uniqueSuffix`; backend real + seed.

- [ ] **Step 1: Write the E2E spec**

```ts
import { expect, test } from '@playwright/test';

import { seedCompany, uniqueSuffix } from './support/seed';
import { installSession, readSharedSession } from './support/session';

const session = readSharedSession();

test('crea un usuario con local, fuerza el cambio de clave y abre la agenda en ese local', async ({ page }) => {
  const seed = await seedCompany(session, uniqueSuffix());
  const email = `nueva-${uniqueSuffix()}@example.com`;

  await installSession(page, session);
  await page.goto('/usuarios');
  await expect(page.getByRole('heading', { name: 'Usuarios' })).toBeVisible();

  await page.getByRole('button', { name: 'Nuevo usuario' }).click();
  const dialog = page.getByRole('dialog');
  await dialog.getByLabel('Correo').fill(email);
  await dialog.getByLabel('Nombre').fill('Nueva');
  await dialog.getByLabel('Apellido').fill('Persona');
  await dialog.getByLabel('Rol').selectOption('reception');
  await dialog.getByLabel('Local predeterminado').selectOption({ label: seed.branch.name });
  await dialog.getByRole('button', { name: 'Crear usuario' }).click();

  const credentials = page.getByRole('dialog', { name: 'Credenciales de acceso' });
  await expect(credentials).toBeVisible();
  const password = await credentials.getByTestId('temporary-password').innerText();
  await credentials.getByRole('button', { name: 'Entendido' }).click();

  await page.getByRole('button', { name: 'Salir' }).click();
  await expect(page.getByRole('heading', { name: 'Panel del operador' })).toBeVisible();
  await page.getByLabel('Correo').fill(email);
  await page.getByLabel('Contraseña').fill(password);
  await page.getByRole('button', { name: 'Entrar' }).click();

  await expect(page.getByRole('heading', { name: 'Cambia tu contraseña' })).toBeVisible();
  await page.getByLabel('Contraseña actual').fill(password);
  await page.getByLabel('Nueva contraseña').fill('Clave-Nueva-2026!');
  await page.getByLabel('Repetir contraseña').fill('Clave-Nueva-2026!');
  await page.getByRole('button', { name: 'Actualizar contraseña' }).click();

  await expect(page.getByRole('heading', { name: 'Agenda' })).toBeVisible();
  await expect(page.getByLabel('Sucursal')).toHaveValue(seed.branch.id);
});
```

- [ ] **Step 2: Run only when the E2E environment is available**

Run (backend + seed activos, `web/.env.e2e` configurado):

```bash
cd web && npm run e2e -- members.spec.ts
```

Expected: PASS. Si el backend local no está levantado, registra el bloqueo y no lo marques como completado.

---

### Task 12: Flutter — local predeterminado en la reserva

**Files:**
- Modify: `mobile/lib/data/models.dart`
- Create: `mobile/lib/data/branch_selection.dart`
- Modify: `mobile/lib/screens/agenda_screen.dart:593-594`
- Test: `mobile/test/branch_selection_test.dart`, `mobile/test/bootstrap_member_test.dart`

**Interfaces:**
- Produces: `Bootstrap.mustChangePassword`, `Bootstrap.defaultBranch`, `Bootstrap.defaultBranchId`; `initialBranchId(branches, preferred)`.
- Consumes: JSON del bootstrap (`user.must_change_password`, `membership.default_branch`).

- [ ] **Step 1: Write the failing tests**

Create `mobile/test/branch_selection_test.dart`:

```dart
import 'package:agenda_mobile/data/branch_selection.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  final branches = [
    {'id': 'a', 'name': 'Centro', 'active': true},
    {'id': 'b', 'name': 'Norte', 'active': false},
  ];

  test('prefiere el local asignado cuando está activo', () {
    expect(initialBranchId(branches, 'a'), 'a');
  });

  test('ignora el local asignado si está inactivo', () {
    expect(initialBranchId(branches, 'b'), 'a');
  });

  test('usa el primer local activo sin preferencia', () {
    expect(initialBranchId(branches, null), 'a');
  });

  test('devuelve null sin locales', () {
    expect(initialBranchId(const [], 'a'), isNull);
  });
}
```

Create `mobile/test/bootstrap_member_test.dart`:

```dart
import 'package:agenda_mobile/data/models.dart';
import 'package:flutter_test/flutter_test.dart';

Map<String, dynamic> _payload({bool mustChange = true}) => {
  'user': {'email': 'persona@example.com', 'must_change_password': mustChange},
  'company': {'id': 'c1', 'name': 'Demo'},
  'membership': {
    'role': 'reception',
    'default_branch': {'id': 'branch-2', 'name': 'Centro'},
  },
  'permissions': <String>[],
  'features': <String, dynamic>{},
  'modules': <String, dynamic>{},
  'billing_state': 'legacy',
  'subscription': null,
  'branches': <dynamic>[],
  'sync_resources': <dynamic>[],
  'server_time': '',
  'companies': <dynamic>[],
};

void main() {
  test('expone el flag de cambio de clave', () {
    final bootstrap = Bootstrap.fromJson(_payload());
    expect(bootstrap.mustChangePassword, isTrue);
  });

  test('expone el local predeterminado', () {
    final bootstrap = Bootstrap.fromJson(_payload());
    expect(bootstrap.defaultBranchId, 'branch-2');
    expect(bootstrap.defaultBranch?['name'], 'Centro');
  });

  test('sin local predeterminado devuelve null', () {
    final payload = _payload();
    payload['membership'] = {'role': 'owner'};
    expect(Bootstrap.fromJson(payload).defaultBranchId, isNull);
  });
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd mobile && flutter test test/branch_selection_test.dart test/bootstrap_member_test.dart`
Expected: FAIL por archivo/gets inexistentes.

- [ ] **Step 3: Implement**

Create `mobile/lib/data/branch_selection.dart`:

```dart
String? initialBranchId(
  List<Map<String, dynamic>> branches,
  String? preferred,
) {
  final active = branches.where((branch) => branch['active'] != false).toList();
  if (preferred != null && preferred.isNotEmpty) {
    for (final branch in active) {
      if ('${branch['id']}' == preferred) return preferred;
    }
  }
  return active.isEmpty ? null : '${active.first['id']}';
}
```

In `mobile/lib/data/models.dart`, inside `Bootstrap`:

```dart
  bool get mustChangePassword => user['must_change_password'] == true;

  Map<String, dynamic>? get defaultBranch {
    final value = membership['default_branch'];
    return value is Map
        ? value.map((key, item) => MapEntry('$key', item))
        : null;
  }

  String? get defaultBranchId => defaultBranch?['id']?.toString();
```

In `mobile/lib/screens/agenda_screen.dart`, import:

```dart
import '../data/branch_selection.dart';
```

and replace the initialization:

```dart
    final branches = app.bootstrap?.branches ?? const [];
    _branchId = initialBranchId(branches, app.bootstrap?.defaultBranchId);
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd mobile && flutter test test/branch_selection_test.dart test/bootstrap_member_test.dart`
Expected: todos PASS.

---

### Task 13: Flutter — cambio de clave obligatorio

**Files:**
- Modify: `mobile/lib/state/app_state.dart`
- Modify: `mobile/lib/app.dart`
- Create: `mobile/lib/screens/change_password_screen.dart`
- Test: `mobile/test/app_state_change_password_test.dart`

**Interfaces:**
- Produces: `AppState.changePassword({required String currentPassword, required String newPassword}) -> Future<bool>`; pantalla obligatoria cuando `bootstrap.mustChangePassword`.
- Consumes: `POST /api/v1/auth/password/change/`, `SessionSnapshot`.

- [ ] **Step 1: Write the failing test**

Create `mobile/test/app_state_change_password_test.dart`:

```dart
import 'package:agenda_mobile/data/api_client.dart';
import 'package:agenda_mobile/data/local_store.dart';
import 'package:agenda_mobile/data/session_store.dart';
import 'package:agenda_mobile/state/app_state.dart';
import 'package:flutter_test/flutter_test.dart';

Map<String, dynamic> _bootstrap({bool mustChange = false}) => {
  'user': {'email': 'persona@example.com', 'must_change_password': mustChange},
  'company': {'id': 'c1', 'name': 'Demo'},
  'membership': {'role': 'owner'},
  'permissions': <String>[],
  'features': <String, dynamic>{},
  'modules': <String, dynamic>{},
  'billing_state': 'legacy',
  'subscription': null,
  'branches': <dynamic>[],
  'sync_resources': <dynamic>[],
  'server_time': '',
  'companies': <dynamic>[],
};

class _PasswordApi extends ApiClient {
  _PasswordApi() : super(baseUrl: 'http://fake');

  final List<Map<String, dynamic>> posted = [];

  @override
  Future<Map<String, dynamic>> getMap(String path, {Map<String, String>? query}) async {
    return _bootstrap();
  }

  @override
  Future<Map<String, dynamic>> postMap(
    String path, {
    Object? body,
    bool authenticated = true,
  }) async {
    posted.add({'path': path, 'body': body});
    return {
      'access': 'new-access',
      'refresh': 'new-refresh',
      'must_change_password': false,
    };
  }
}

class _MemorySessions extends SessionStore {
  SessionSnapshot? snapshot;

  @override
  Future<SessionSnapshot?> load() async => snapshot;

  @override
  Future<void> save(SessionSnapshot value) async => snapshot = value;

  @override
  Future<void> clear() async => snapshot = null;
}

void main() {
  test('cambia la clave, guarda los tokens y limpia el flag', () async {
    final api = _PasswordApi();
    final sessions = _MemorySessions();
    final state = AppState(
      api: api,
      store: await LocalStore.memory(),
      sessions: sessions,
    );

    final ok = await state.changePassword(
      currentPassword: 'Vieja-Clave-123!',
      newPassword: 'Nueva-Clave-456!',
    );

    expect(ok, isTrue);
    expect(api.posted.single['path'], '/api/v1/auth/password/change/');
    expect(
      (api.posted.single['body'] as Map)['new_password'],
      'Nueva-Clave-456!',
    );
    expect(api.accessToken, 'new-access');
    expect(sessions.snapshot?.refreshToken, 'new-refresh');
    expect(state.bootstrap?.mustChangePassword, isFalse);
  });
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd mobile && flutter test test/app_state_change_password_test.dart`
Expected: FAIL `The method 'changePassword' isn't defined`.

- [ ] **Step 3: Implement `AppState.changePassword`**

Add to `mobile/lib/state/app_state.dart` (after `updateBranding`):

```dart
  Future<bool> changePassword({
    required String currentPassword,
    required String newPassword,
  }) async {
    _startBusy();
    try {
      final data = await api.postMap(
        '/api/v1/auth/password/change/',
        body: {
          'current_password': currentPassword,
          'new_password': newPassword,
        },
      );
      final access = data['access']?.toString();
      final refresh = data['refresh']?.toString();
      if (access == null || refresh == null) {
        throw ApiException(500, 'El servidor no devolvió las credenciales nuevas.');
      }
      api
        ..accessToken = access
        ..refreshToken = refresh;
      await sessions.save(
        SessionSnapshot(
          baseUrl: api.baseUrl,
          accessToken: access,
          refreshToken: refresh,
          contextId: api.tenantContextId,
          companyId: activeCompanyId,
          companyName: bootstrap?.companyName,
          isSaasAdmin: isSaasAdmin,
        ),
      );
      await _loadBootstrap();
      return true;
    } on ApiException catch (error) {
      errorMessage = error.message;
      return false;
    } finally {
      _stopBusy();
    }
  }
```

- [ ] **Step 4: Create the screen and wire the gate**

Create `mobile/lib/screens/change_password_screen.dart`:

```dart
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/theme.dart';
import '../state/app_state.dart';
import '../widgets/common.dart';

class ChangePasswordScreen extends StatefulWidget {
  const ChangePasswordScreen({super.key});

  @override
  State<ChangePasswordScreen> createState() => _ChangePasswordScreenState();
}

class _ChangePasswordScreenState extends State<ChangePasswordScreen> {
  final _formKey = GlobalKey<FormState>();
  final _current = TextEditingController();
  final _next = TextEditingController();
  final _confirm = TextEditingController();

  @override
  void dispose() {
    _current.dispose();
    _next.dispose();
    _confirm.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    await context.read<AppState>().changePassword(
      currentPassword: _current.text,
      newPassword: _next.text,
    );
  }

  @override
  Widget build(BuildContext context) {
    final app = context.watch<AppState>();
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 440),
              child: Form(
                key: _formKey,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    const AppLogo(),
                    const SizedBox(height: 28),
                    const Text(
                      'CAMBIA TU CONTRASEÑA',
                      style: TextStyle(
                        fontSize: 26,
                        fontWeight: FontWeight.w900,
                        letterSpacing: -0.8,
                      ),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      'Usaste una clave temporal. Define una contraseña propia para continuar.',
                      style: TextStyle(
                        color: context.palette.muted,
                        fontSize: 13,
                        height: 1.45,
                      ),
                    ),
                    const SizedBox(height: 24),
                    if (app.errorMessage != null) ...[
                      ErrorNote(app.errorMessage!),
                      const SizedBox(height: 16),
                    ],
                    TextFormField(
                      controller: _current,
                      obscureText: true,
                      decoration: const InputDecoration(
                        labelText: 'Contraseña actual',
                        prefixIcon: Icon(Icons.lock_outline, size: 20),
                      ),
                      validator: (value) => (value == null || value.isEmpty)
                          ? 'Ingresa tu contraseña actual'
                          : null,
                    ),
                    const SizedBox(height: 14),
                    TextFormField(
                      controller: _next,
                      obscureText: true,
                      decoration: const InputDecoration(
                        labelText: 'Nueva contraseña',
                        prefixIcon: Icon(Icons.lock_reset, size: 20),
                      ),
                      validator: (value) => (value == null || value.length < 12)
                          ? 'Usa al menos 12 caracteres'
                          : null,
                    ),
                    const SizedBox(height: 14),
                    TextFormField(
                      controller: _confirm,
                      obscureText: true,
                      decoration: const InputDecoration(
                        labelText: 'Repetir contraseña',
                        prefixIcon: Icon(Icons.lock_reset, size: 20),
                      ),
                      validator: (value) => value != _next.text
                          ? 'Las contraseñas no coinciden'
                          : null,
                    ),
                    const SizedBox(height: 22),
                    FilledButton(
                      onPressed: app.busy ? null : _submit,
                      child: app.busy
                          ? const SizedBox(
                              width: 20,
                              height: 20,
                              child: CircularProgressIndicator(strokeWidth: 2),
                            )
                          : const Text('ACTUALIZAR CONTRASEÑA'),
                    ),
                    const SizedBox(height: 12),
                    TextButton(
                      onPressed: app.busy ? null : () => app.logout(),
                      child: const Text('Cerrar sesión'),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
```

In `mobile/lib/app.dart`:

```dart
import 'screens/change_password_screen.dart';
...
      AppStatus.ready => app.bootstrap?.mustChangePassword == true
          ? const ChangePasswordScreen()
          : const HomeShell(),
```

- [ ] **Step 5: Run tests and analyze**

Run: `cd mobile && flutter test test/app_state_change_password_test.dart`
Expected: PASS.

Run: `cd mobile && flutter analyze`
Expected: sin errores.

- [ ] **Step 6: Full checkpoint**

Run:

```bash
cd mobile && flutter test
cd web && npm test && npm run lint && npm run build
cd backend && DJANGO_TESTING=true python manage.py test apps.identity apps.mobile apps.tenancy -v 1
```

Expected: suites verdes. No commit.

---

## Self-Review Notes

- **Cobertura del spec:** modelo y migración (T1), API de usuarios con reglas de rol/local/clave temporal/perfil (T2–T3), cambio de clave y flag (T4), bootstrap enriquecido (T5), capa API web (T6), local predeterminado en agenda web (T7), cambio forzado web (T8), sección Usuarios (T9), editor de permisos (T10), E2E (T11), Flutter local + cambio forzado (T12–T13). Aislamiento tenant verificado en T2; no se toca `User.is_active`; el último propietario activo no se puede desactivar ni degradar; `permission-grants` exige owner/admin también para listar.
- **Consistencia de tipos:** `default_branch` es `{id,name}|null` en backend, web y Flutter; `Member` usa `role` tipo `MemberRole`; `PermissionGrant` campos `membership/permission/effect/branch`.
- **Sin commits:** todos los cierres son checkpoints de tests; la autorización de git queda en manos de Carlos.
