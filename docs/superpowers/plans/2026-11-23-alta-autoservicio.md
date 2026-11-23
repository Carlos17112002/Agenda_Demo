# Alta autoservicio con verificación de correo — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Un visitante ve los planes en `/precios`, contrata con su correo y contraseña, verifica su correo desde el enlace enviado y entra al panel sin intervención del superadmin.

**Architecture:** Se reutiliza `provision_company` (empresa + propietario + membresía) pero el usuario se crea inactivo y la suscripción se difiere hasta la verificación. El token de verificación es un `signing.dumps` con `uid` y código de plan (48 h, un solo uso). Al verificar se activa el usuario, se inicia la suscripción con el plan elegido (o el predeterminado) y se devuelven tokens JWT; el panel web guarda el refresh y recarga en `/`, donde el `AuthProvider` restaura la sesión completa.

**Tech Stack:** Django 6 + DRF + simplejwt + `django.core.mail`, React 18 + Vite + react-router 7 + react-query 5 + zod 4 + react-hook-form, Vitest + msw.

**Spec:** `docs/superpowers/specs/2026-11-23-alta-autoservicio-design.md`

## Global Constraints

- Aislamiento por empresa: ninguna empresa puede leer, modificar ni eliminar datos de otra. Todo lo nuevo sigue el patrón existente (el registro público crea su propia empresa dentro de `transaction.atomic()`).
- Base de datos local (SQLite) por ahora; el plan no introduce migraciones.
- El operador/superadmin nunca queda como miembro de la empresa creada.
- Español en toda la UI y los mensajes de error.
- Sin commits ni push sin autorización explícita de Carlos. Cada tarea termina con verificación, **no** con commit; los pasos "Commit" del formato original se sustituyen por "Deja los cambios sin commitear".
- Ejecución inline en `master` con puntos de control por fase (preferencia de Carlos).
- Backend tests: desde `backend/`, `DJANGO_TESTING=true python manage.py test <módulo>`. Web: `npm test -- --run --maxWorkers=4`, `npm run build`, `npm run lint`.
- UI por defecto en tema claro; verificar también tema oscuro en la revisión final.
- El flujo de creación desde la consola SaaS (`SaasCompanyCreateSerializer`) no cambia: usuario activo, contraseña temporal o elegida, suscripción inmediata.

---

## Estructura de archivos

**Backend**
- Modificar `backend/config/settings.py` — `EMAIL_VERIFICATION_TIMEOUT`, `AGENDA_WEB_BASE_URL`, throttles de verificación.
- Modificar `backend/config/urls.py` — rutas `verify-email` y `resend-verification`.
- Crear `backend/apps/tenancy/verification.py` — token, enlace y envío del correo.
- Modificar `backend/apps/tenancy/serializers.py` — slug opcional/autogenerado, `plan`, `verified=False` en `provision_company`, serializers de verificación/reenvío.
- Modificar `backend/apps/tenancy/views.py` — throttles y vistas `VerifyEmailView`, `ResendVerificationView`; respuesta del registro.
- Crear `backend/apps/tenancy/management/__init__.py`, `management/commands/__init__.py`, `management/commands/purge_unverified_companies.py`.
- Crear `backend/apps/tenancy/tests/test_public_registration.py`, `backend/apps/tenancy/tests/test_purge_unverified.py`.
- Modificar `backend/apps/billing/tests/test_billing_api.py` (el registro ya no crea suscripción de inmediato).
- Modificar `backend/.env.example` — Gmail SMTP y `AGENDA_WEB_BASE_URL`.

**Frontend**
- Crear `web/src/features/saas/planFormat.ts` + `planFormat.test.ts`; mover `formatAmount`/`featureSummary` desde `SaasPlansPage.tsx`.
- Crear `web/src/api/publicAccounts.ts`; modificar `web/src/api/runtime.ts`, `web/src/api/types.ts`, `web/src/api/queryKeys.ts`.
- Crear `web/src/lib/hardNavigate.ts`.
- Crear `web/src/features/public/PublicPricingPage.tsx`, `SignupDialog.tsx`, `VerifyEmailPage.tsx` + sus tests.
- Modificar `web/src/app/router.tsx` (rutas `/precios`, `/verificar`).
- Modificar `web/src/features/auth/LoginPage.tsx` (enlace "Ver planes").

---

## Fase 1 — Backend

### Task 1: Registro público con slug automático, plan elegido y usuario inactivo

**Files:**
- Modify: `backend/apps/tenancy/serializers.py` (líneas 129-197)
- Modify: `backend/apps/tenancy/views.py` (líneas 123-135)
- Test: `backend/apps/tenancy/tests/test_public_registration.py` (crear)

**Interfaces:**
- Consumes: `Membership` (`apps/identity/models.py:23`), `start_subscription`, `default_plan` (`apps/billing/services.py`), `record_event` (`apps/audit/services.py`).
- Produces: `suggest_company_slug(name: str) -> str`; `provision_company(..., verified: bool = True)`; `CompanyRegistrationSerializer` con campos `company_name, slug?, email, password, first_name?, plan?`; respuesta 201 `{company_id, company_name, email, detail}`.

- [x] **Step 1: Escribir los tests que fallan**

Crear `backend/apps/tenancy/tests/test_public_registration.py`:

```python
from datetime import timedelta
from decimal import Decimal

from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.audit.models import AuditEvent
from apps.billing.models import Plan, Subscription
from apps.identity.models import Membership, User
from apps.tenancy.models import Company


def make_plan(code="pro", **overrides):
    defaults = {
        "name": code.title(), "price": Decimal("19990.00"), "currency": "CLP",
        "billing_period": "monthly", "trial_days": 14, "active": True,
    }
    defaults.update(overrides)
    return Plan.objects.create(code=code, **defaults)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class PublicRegistrationTests(TestCase):
    def setUp(self):
        mail.outbox.clear()
        self.client = APIClient()

    def register(self, **overrides):
        payload = {
            "company_name": "Barbería Central", "email": "dueno@example.com",
            "password": "Strong-Horse-Battery-483!", "first_name": "Dueña",
        }
        payload.update(overrides)
        return self.client.post("/api/v1/auth/register-company/", payload, format="json")

    def test_registration_creates_inactive_owner_without_slug(self):
        response = self.register()
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["email"], "dueno@example.com")
        company = Company.objects.get(slug="barberia-central")
        user = User.objects.get(email="dueno@example.com")
        self.assertFalse(user.is_active)
        self.assertEqual(Membership.objects.get(company=company).role, Membership.Role.OWNER)
        self.assertFalse(Subscription.objects.filter(company=company).exists())
        self.assertEqual(company.status, "trial")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, "Activa tu cuenta de AGENDA")
        self.assertIn("/verificar?token=", mail.outbox[0].body)
        self.assertTrue(AuditEvent.objects.filter(company=company,
            action="company.registered").exists())

    def test_duplicate_name_gets_numeric_slug_suffix(self):
        self.register()
        self.register(email="otro@example.com")
        self.assertTrue(Company.objects.filter(slug="barberia-central-2").exists())

    def test_inactive_user_cannot_login_before_verification(self):
        self.register()
        response = self.client.post("/api/v1/auth/token/", {
            "email": "dueno@example.com", "password": "Strong-Horse-Battery-483!",
        }, format="json")
        self.assertEqual(response.status_code, 401)

    def test_existing_active_email_is_rejected_with_login_hint(self):
        User.objects.create_user(username="ana@example.com", email="ana@example.com",
                                 password="Correct-horse-123")
        response = self.register(email="ana@example.com")
        self.assertEqual(response.status_code, 400)
        self.assertIn("Ya existe una cuenta con este correo", str(response.data))

    def test_pending_email_is_rejected_with_resend_hint(self):
        self.register()
        response = self.register(email="dueno@example.com")
        self.assertEqual(response.status_code, 400)
        self.assertIn("registro pendiente", str(response.data))

    def test_chosen_plan_is_stored_in_audit_metadata(self):
        plan = make_plan()
        response = self.register(plan=plan.code)
        self.assertEqual(response.status_code, 201)
        company = Company.objects.get(slug="barberia-central")
        event = AuditEvent.objects.get(company=company, action="company.registered")
        self.assertEqual(event.metadata["plan"], plan.code)

    def test_inactive_plan_code_is_rejected(self):
        make_plan(code="viejo", active=False)
        response = self.register(plan="viejo")
        self.assertEqual(response.status_code, 400)
        self.assertIn("plan", response.data)
```

- [x] **Step 2: Ejecutar y ver que fallan**

Run: `cd backend && DJANGO_TESTING=true python manage.py test apps.tenancy.tests.test_public_registration -v 2`
Expected: FAIL (la respuesta exige `slug`; los usuarios se crean activos; no se envía correo).

- [x] **Step 3: Implementar slug automático y `verified` en serializers**

En `backend/apps/tenancy/serializers.py`, reemplazar `validate_new_company_email`:

```python
def validate_new_company_email(email):
    from apps.identity.models import User
    user = User.objects.filter(email__iexact=email).first()
    if user is not None:
        if user.is_active:
            raise serializers.ValidationError(
                "Ya existe una cuenta con este correo. Inicia sesión."
            )
        raise serializers.ValidationError(
            "Ya existe un registro pendiente con este correo. "
            "Revisa tu correo o solicita un reenvío."
        )
    return email


def suggest_company_slug(name):
    from django.utils.text import slugify
    base = slugify(name)[:90] or "empresa"
    candidate, suffix = base, 2
    while (Company.objects.filter(slug=candidate).exists()
           or candidate in RESERVED_COMPANY_SLUGS):
        candidate = f"{base}-{suffix}"
        suffix += 1
    return candidate
```

En `provision_company`, añadir el parámetro `verified=True`, crear el usuario con `is_active=verified` y condicionar la suscripción:

```python
def provision_company(*, company_name, slug, email, password, first_name="",
                      source, request=None, actor=None, plan=None, trial_days=None,
                      verified=True):
    from django.db import transaction
    from apps.identity.models import User
    from apps.audit.models import AuditEvent
    with transaction.atomic():
        company = Company.objects.create(name=company_name, slug=slug)
        user = User.objects.create_user(username=email, email=email, password=password,
                                        first_name=first_name, is_active=verified)
        Membership.objects.create(user=user, company=company, role=Membership.Role.OWNER)
        from apps.billing.services import default_plan, start_subscription
        subscription = None
        if verified:
            plan = plan or default_plan()
            if plan:
                subscription = start_subscription(
                    company, plan, trial_days=trial_days, actor=actor or user,
                )
        AuditEvent.objects.create(company=company, actor=actor or user,
            action="company.registered", entity_type="Company", entity_id=str(company.id),
            metadata={
                "source": source,
                "plan": plan.code if plan else None,
                "remote_addr": request.META.get("REMOTE_ADDR") if request else None,
                "user_agent": (request.META.get("HTTP_USER_AGENT", "")[:240] if request else ""),
            })
    return company, user, subscription
```

Sustituir `CompanyRegistrationSerializer` (dejando intacto `SaasCompanyCreateSerializer`):

```python
class CompanyRegistrationSerializer(serializers.Serializer):
    company_name = serializers.CharField(max_length=180)
    slug = serializers.SlugField(max_length=100, required=False, allow_blank=True)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=12, max_length=128)
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    plan = serializers.CharField(required=False, allow_blank=True)

    def validate_email(self, email):
        return validate_new_company_email(email)

    def validate_slug(self, slug):
        return validate_new_company_slug(slug) if slug else ""

    def validate_plan(self, code):
        if not code:
            return None
        from apps.billing.models import Plan
        plan = Plan.objects.filter(code=code, active=True).first()
        if plan is None:
            raise serializers.ValidationError("El plan no está disponible.")
        return plan

    def validate_password(self, password):
        from django.contrib.auth.password_validation import validate_password
        validate_password(password)
        return password

    def create(self, validated_data):
        from .verification import send_verification_email
        company_name = validated_data["company_name"]
        plan = validated_data.get("plan")
        company, user, _ = provision_company(
            company_name=company_name,
            slug=validated_data.get("slug") or suggest_company_slug(company_name),
            email=validated_data.pop("email"),
            password=validated_data.pop("password"),
            first_name=validated_data.pop("first_name", ""),
            source="public_registration",
            request=self.context.get("request"),
            plan=plan,
            verified=False,
        )
        send_verification_email(user, plan=plan)
        return company, user
```

- [x] **Step 4: Ajustar la vista de registro**

En `backend/apps/tenancy/views.py`:

```python
    def create(self, request):
        serializer = CompanyRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        company, user = serializer.save()
        return Response({
            "company_id": str(company.id), "company_name": company.name,
            "email": user.email,
            "detail": "Revisa tu correo para activar tu cuenta.",
        }, status=status.HTTP_201_CREATED)
```

`send_verification_email` se implementa en Task 2; hasta entonces crear `backend/apps/tenancy/verification.py` con un stub mínimo para que el import no falle:

```python
def send_verification_email(user, plan=None):
    return None
```

(El stub se sustituye completo en Task 2; el test de este paso que exige correo se valida al final de Task 2.)

- [x] **Step 5: Ejecutar los tests**

Run: `cd backend && DJANGO_TESTING=true python manage.py test apps.tenancy.tests.test_public_registration -v 2`
Expected: PASS en todos salvo `test_registration_creates_inactive_owner_without_slug` (el envío real del correo llega en Task 2); los demás deben pasar ya. Aceptar transitoriamente solo esa falla y continuar.

- [x] **Step 6: Deja los cambios sin commitear y avisa del punto de control.**

---

### Task 2: Token, correo de verificación y endpoints `verify-email` / `resend-verification`

**Files:**
- Modify: `backend/config/settings.py` (líneas 69-71 y 106)
- Create/replace: `backend/apps/tenancy/verification.py`
- Modify: `backend/apps/tenancy/serializers.py` (añadir serializers al final)
- Modify: `backend/apps/tenancy/views.py` (añadir import y vistas)
- Modify: `backend/config/urls.py` (líneas 98-102)
- Test: `backend/apps/tenancy/tests/test_public_registration.py` (ampliar)

**Interfaces:**
- Consumes: `VerifyEmailSerializer.save() -> (user, company, subscription)`.
- Produces: `make_verification_token(user, plan=None) -> str`, `send_verification_email(user, plan=None)`; `POST /api/v1/auth/verify-email/ {token}` → 200 `{access, refresh, user}`; `POST /api/v1/auth/resend-verification/ {email}` → 200 genérico.

- [x] **Step 1: Escribir los tests que fallan**

Añadir a `PublicRegistrationTests`:

```python
    def verification_token(self):
        import re
        from urllib.parse import unquote
        body = mail.outbox[-1].body
        match = re.search(r"/verificar\?token=(\S+)", body)
        self.assertIsNotNone(match, "el correo debe incluir el enlace de verificación")
        return unquote(match.group(1))

    def test_verification_activates_user_and_starts_chosen_plan(self):
        plan = make_plan(trial_days=21)
        self.register(plan=plan.code)
        response = self.client.post("/api/v1/auth/verify-email/",
                                    {"token": self.verification_token()}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        user = User.objects.get(email="dueno@example.com")
        self.assertTrue(user.is_active)
        subscription = Subscription.objects.get(company=user.memberships.get().company)
        self.assertEqual(subscription.plan_id, plan.id)
        self.assertEqual(subscription.status, Subscription.Status.TRIALING)
        self.assertGreater(subscription.trial_ends_at, timezone.now())
        self.assertTrue(AuditEvent.objects.filter(company=subscription.company,
            action="company.email_verified").exists())

    def test_verification_falls_back_to_default_plan_when_plan_is_gone(self):
        make_plan(code="base", is_default=True, trial_days=7)
        plan = make_plan(code="temporal")
        self.register(plan=plan.code)
        plan.active = False
        plan.save(update_fields=["active"])
        response = self.client.post("/api/v1/auth/verify-email/",
                                    {"token": self.verification_token()}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        subscription = Subscription.objects.get(company__slug="barberia-central")
        self.assertEqual(subscription.plan.code, "base")

    def test_token_is_single_use(self):
        self.register()
        token = self.verification_token()
        first = self.client.post("/api/v1/auth/verify-email/", {"token": token}, format="json")
        self.assertEqual(first.status_code, 200)
        second = self.client.post("/api/v1/auth/verify-email/", {"token": token}, format="json")
        self.assertEqual(second.status_code, 400)
        self.assertIn("ya está verificada", str(second.data))

    def test_invalid_or_expired_token_is_rejected(self):
        response = self.client.post("/api/v1/auth/verify-email/",
                                    {"token": "basura"}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("no es válido", str(response.data))

    def test_resend_is_generic_and_only_emails_pending_accounts(self):
        self.register()
        mail.outbox.clear()
        response = self.client.post("/api/v1/auth/resend-verification/",
                                    {"email": "nadie@example.com"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)
        response = self.client.post("/api/v1/auth/resend-verification/",
                                    {"email": "dueno@example.com"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("/verificar?token=", mail.outbox[0].body)
```

- [x] **Step 2: Ejecutar y ver que fallan**

Run: `cd backend && DJANGO_TESTING=true python manage.py test apps.tenancy.tests.test_public_registration -v 2`
Expected: FAIL con 404 en `/api/v1/auth/verify-email/` y `/api/v1/auth/resend-verification/`.

- [x] **Step 3: Configurar ajustes y throttles**

En `backend/config/settings.py`, junto a `PASSWORD_RESET_TIMEOUT`:

```python
EMAIL_VERIFICATION_TIMEOUT = 60 * 60 * 48
AGENDA_WEB_BASE_URL = os.getenv("AGENDA_WEB_BASE_URL", "http://127.0.0.1:5173").rstrip("/")
```

Ampliar `DEFAULT_THROTTLE_RATES` agregando `"email_verification": "10/hour"` y `"resend_verification": "3/hour"`.

- [x] **Step 4: Implementar `verification.py` completo**

```python
import logging
from urllib.parse import quote

from django.conf import settings
from django.core import signing
from django.core.mail import send_mail

logger = logging.getLogger("agenda.security")
SALT = "identity.email-verification"


def make_verification_token(user, plan=None):
    return signing.dumps(
        {"uid": str(user.pk), "plan": plan.code if plan else ""}, salt=SALT,
    )


def send_verification_email(user, plan=None):
    token = quote(make_verification_token(user, plan), safe="")
    link = f"{settings.AGENDA_WEB_BASE_URL}/verificar?token={token}"
    greeting = f"Hola {user.first_name}:" if user.first_name else "Hola:"
    body = (
        f"{greeting}\n\n"
        "Tu cuenta de AGENDA está casi lista. Confirma tu correo para activarla:\n\n"
        f"{link}\n\n"
        "El enlace vence en 48 horas. Si no creaste esta cuenta, ignora este mensaje.\n"
    )
    try:
        send_mail("Activa tu cuenta de AGENDA", body, None, [user.email])
    except Exception:
        # El registro ya se confirmó al visitante; el reenvío es la vía de recuperación.
        logger.exception("verification_email_failed user_id=%s", user.pk)
```

- [x] **Step 5: Implementar serializers de verificación**

En `backend/apps/tenancy/serializers.py` añadir al inicio `from django.core import signing` y al final:

```python
class VerifyEmailSerializer(serializers.Serializer):
    token = serializers.CharField()

    def validate_token(self, token):
        from apps.identity.models import User
        try:
            payload = signing.loads(
                token, salt="identity.email-verification",
                max_age=settings.EMAIL_VERIFICATION_TIMEOUT,
            )
        except (signing.BadSignature, signing.SignatureExpired):
            raise serializers.ValidationError("El enlace no es válido o venció.")
        user = User.objects.filter(pk=payload.get("uid")).first()
        if user is None:
            raise serializers.ValidationError("El enlace no es válido o venció.")
        if user.is_active:
            raise serializers.ValidationError("La cuenta ya está verificada.")
        self._user = user
        self._plan_code = payload.get("plan") or ""
        return token

    def create(self, validated_data):
        from django.db import transaction
        from apps.audit.services import record_event
        from apps.billing.models import Plan
        from apps.billing.services import default_plan, start_subscription
        user = self._user
        with transaction.atomic():
            user.is_active = True
            user.save(update_fields=["is_active"])
            company = user.memberships.select_related("company").get(active=True).company
            plan = Plan.objects.filter(code=self._plan_code, active=True).first()
            plan = plan or default_plan()
            subscription = start_subscription(company, plan, actor=user) if plan else None
            record_event(
                company=company, actor=user, action="company.email_verified",
                instance=company, metadata={"plan": plan.code if plan else None},
            )
        return user, company, subscription


class ResendVerificationSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def create(self, validated_data):
        from apps.audit.models import AuditEvent
        from apps.billing.models import Plan
        from apps.identity.models import User
        from .verification import send_verification_email
        user = User.objects.filter(
            email__iexact=validated_data["email"], is_active=False,
        ).first()
        if user is not None:
            membership = user.memberships.filter(active=True).select_related("company").first()
            if membership is not None:
                event = AuditEvent.objects.filter(
                    company=membership.company, action="company.registered",
                ).order_by("-created_at").first()
                code = (event.metadata or {}).get("plan") if event else None
                plan = Plan.objects.filter(code=code, active=True).first() if code else None
                send_verification_email(user, plan=plan)
        return validated_data["email"]
```

Necesita `settings` importado arriba del archivo: `from django.conf import settings`.

- [x] **Step 6: Añadir las vistas y rutas**

En `backend/apps/tenancy/views.py`, ampliar el import desde `.serializers` con `ResendVerificationSerializer, VerifyEmailSerializer` y añadir:

```python
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
```

En `backend/config/urls.py`, junto a las rutas de registro y reset (importando las vistas nuevas desde `apps.tenancy.views`):

```python
path("api/v1/auth/verify-email/", VerifyEmailView.as_view(), name="verify-email"),
path("api/v1/auth/resend-verification/", ResendVerificationView.as_view(), name="resend-verification"),
```

- [x] **Step 7: Ejecutar los tests**

Run: `cd backend && DJANGO_TESTING=true python manage.py test apps.tenancy.tests.test_public_registration -v 2`
Expected: PASS (todos).

- [x] **Step 8: Actualizar el test de facturación que asumía suscripción inmediata**

En `backend/apps/billing/tests/test_billing_api.py`, reemplazar `test_registration_uses_default_plan_trial` (línea 259) por una versión que verifique vía token:

```python
    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_verified_registration_uses_default_plan_trial(self):
        import re
        from urllib.parse import unquote
        from django.core import mail
        plan = make_plan("starter-default", trial_days=7, is_default=True)
        response = APIClient().post("/api/v1/auth/register-company/", {
            "company_name": "Nueva SaaS", "email": "owner-nueva@example.com",
            "password": "Strong-Horse-Battery-483!", "first_name": "Dueña",
        }, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        company = Company.objects.get(slug="nueva-saas")
        self.assertFalse(Subscription.objects.filter(company=company).exists())

        body = mail.outbox[-1].body
        token = unquote(re.search(r"/verificar\?token=(\S+)", body).group(1))
        verified = APIClient().post("/api/v1/auth/verify-email/", {"token": token}, format="json")
        self.assertEqual(verified.status_code, 200, verified.data)

        subscription = Subscription.objects.get(company=company)
        self.assertEqual(subscription.plan_id, plan.id)
        self.assertEqual(subscription.status, Subscription.Status.TRIALING)
        self.assertGreater(subscription.trial_ends_at, timezone.now())
        self.assertEqual(company.status, "trial")
        self.assertEqual(Membership.objects.get(company=company).role, Membership.Role.OWNER)
```

Asegurar que el archivo importa `override_settings` y `mail` desde `django.test`/`django.core` (ajustar el import existente).

- [x] **Step 9: Ejecutar ambas suites**

Run: `cd backend && DJANGO_TESTING=true python manage.py test apps.tenancy apps.billing -v 2`
Expected: PASS.

- [x] **Step 10: Deja los cambios sin commitear y avisa del punto de control.**

---

### Task 3: Comando `purge_unverified_companies`

**Files:**
- Create: `backend/apps/tenancy/management/__init__.py` (vacío)
- Create: `backend/apps/tenancy/management/commands/__init__.py` (vacío)
- Create: `backend/apps/tenancy/management/commands/purge_unverified_companies.py`
- Test: `backend/apps/tenancy/tests/test_purge_unverified.py`

**Interfaces:**
- Produces: `python manage.py purge_unverified_companies --days 7 [--dry-run]`.

- [x] **Step 1: Escribir el test que falla**

```python
from datetime import timedelta

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from apps.audit.models import AuditEvent
from apps.identity.models import Membership, User
from apps.tenancy.models import Company, TenantContext


def unverified_company(name, slug, email, *, days_old=10, active=False):
    company = Company.objects.create(name=name, slug=slug)
    user = User.objects.create_user(username=email, email=email, is_active=active)
    Membership.objects.create(user=user, company=company, role=Membership.Role.OWNER)
    AuditEvent.objects.create(company=company, actor=user, action="company.registered",
                              entity_type="Company", entity_id=str(company.id))
    Company.objects.filter(pk=company.pk).update(
        created_at=timezone.now() - timedelta(days=days_old)
    )
    return company, user


class PurgeUnverifiedCommandTests(TestCase):
    def test_deletes_only_old_unverified_companies(self):
        old_company, old_user = unverified_company("Vieja", "vieja", "vieja@example.com")
        recent_company, _ = unverified_company("Nueva", "nueva", "nueva@example.com", days_old=1)
        verified_company, verified_user = unverified_company(
            "Activa", "activa", "activa@example.com", days_old=30, active=True,
        )
        call_command("purge_unverified_companies", "--days", "7")
        self.assertFalse(Company.objects.filter(pk=old_company.pk).exists())
        self.assertFalse(User.objects.filter(pk=old_user.pk).exists())
        self.assertFalse(TenantContext.objects.filter(company_id=old_company.pk).exists())
        self.assertFalse(AuditEvent.objects.filter(company_id=old_company.pk).exists())
        self.assertTrue(Company.objects.filter(pk=recent_company.pk).exists())
        self.assertTrue(Company.objects.filter(pk=verified_company.pk).exists())

    def test_dry_run_deletes_nothing(self):
        company, _ = unverified_company("Vieja", "vieja", "vieja@example.com")
        call_command("purge_unverified_companies", "--days", "7", "--dry-run")
        self.assertTrue(Company.objects.filter(pk=company.pk).exists())
```

- [x] **Step 2: Ejecutar y ver que falla**

Run: `cd backend && DJANGO_TESTING=true python manage.py test apps.tenancy.tests.test_purge_unverified -v 2`
Expected: FAIL con `Unknown command: 'purge_unverified_companies'`.

- [x] **Step 3: Implementar el comando**

```python
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.audit.models import AuditEvent
from apps.identity.models import Membership, User
from apps.tenancy.models import Company, TenantContext


class Command(BaseCommand):
    help = (
        "Elimina empresas registradas por alta autoservicio que nunca verificaron "
        "su correo. Por defecto borra registros de más de 7 días."
    )

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=7)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(days=options["days"])
        company_ids = list(
            Company.objects.filter(
                created_at__lt=cutoff,
                memberships__active=True,
                memberships__user__is_active=False,
            ).values_list("id", flat=True).distinct()
        )
        purged = 0
        for company in Company.objects.filter(id__in=company_ids).select_related():
            owner_ids = list(
                Membership.objects.filter(company=company)
                .values_list("user_id", flat=True)
            )
            if options["dry_run"]:
                self.stdout.write(f"[dry-run] {company.slug}")
                purged += 1
                continue
            with transaction.atomic():
                AuditEvent.objects.filter(company=company).delete()
                Membership.objects.filter(company=company).delete()
                TenantContext.objects.filter(company=company).delete()
                company.delete()
                for user in User.objects.filter(id__in=owner_ids, is_active=False):
                    if not user.memberships.exists():
                        user.delete()
            purged += 1
        self.stdout.write(f"purge_unverified_companies: {purged} empresa(s) procesada(s).")
```

- [x] **Step 4: Ejecutar y verificar**

Run: `cd backend && DJANGO_TESTING=true python manage.py test apps.tenancy.tests.test_purge_unverified -v 2`
Expected: PASS.

- [x] **Step 5: Documentar variables de entorno**

En `backend/.env.example`, bajo el bloque de correo, añadir:

```
# Verificación de correo del alta autoservicio
AGENDA_WEB_BASE_URL=http://127.0.0.1:5173
# Producción (Gmail SMTP)
DJANGO_EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=true
EMAIL_HOST_USER=tu-cuenta@gmail.com
EMAIL_HOST_PASSWORD=clave-de-aplicacion-de-16-caracteres
DEFAULT_FROM_EMAIL=tu-cuenta@gmail.com
```

- [x] **Step 6: Deja los cambios sin commitear y avisa del cierre de la fase backend.**

---

## Fase 2 — Frontend

### Task 4: Extraer `planFormat` y crear la API pública

**Files:**
- Create: `web/src/features/saas/planFormat.ts`
- Create: `web/src/features/saas/planFormat.test.ts`
- Modify: `web/src/features/saas/SaasPlansPage.tsx` (líneas 1-37)
- Modify: `web/src/api/types.ts` (al final)
- Create: `web/src/api/publicAccounts.ts`
- Modify: `web/src/api/runtime.ts` (imports y export final)
- Modify: `web/src/api/queryKeys.ts`

**Interfaces:**
- Produces: `formatAmount(plan)`, `featureSummary(plan)`; `PublicPlan`, `RegisterCompanyInput`, `RegisterCompanyResponse`, `VerifyEmailResponse`; `publicAccountsApi.plans() / registerCompany(input) / verifyEmail(token) / resendVerification(email)`; `queryKeys.publicPlans()`.

- [x] **Step 1: Escribir el test de `planFormat`**

```typescript
import { describe, expect, test } from 'vitest';

import { featureSummary, formatAmount } from './planFormat';

describe('planFormat', () => {
  test('formatea el precio en es-CL con la moneda del plan', () => {
    expect(formatAmount({ price: '19990.00', currency: 'CLP' })).toBe('CLP 19.990');
  });

  test('resume funcionalidades activas con sus límites', () => {
    expect(featureSummary({
      price: '0', currency: 'CLP',
      features: [
        { code: 'sales', enabled: true, limit_value: null },
        { code: 'branches', enabled: true, limit_value: 5 },
        { code: 'inventory', enabled: false, limit_value: null },
      ],
    })).toBe('Ventas y caja · Sucursales: 5');
  });

  test('devuelve un guion cuando no hay funcionalidades activas', () => {
    expect(featureSummary({ price: '0', currency: 'CLP', features: [] })).toBe('—');
  });
});
```

- [x] **Step 2: Ejecutar y ver que falla**

Run: `cd web && npx vitest run src/features/saas/planFormat.test.ts --maxWorkers=4`
Expected: FAIL (módulo inexistente).

- [x] **Step 3: Crear `planFormat.ts` moviendo la lógica existente**

```typescript
import { PLAN_FEATURES } from './planFeatures';

export type PlanLike = {
  price: string;
  currency: string;
  features: { code: string; enabled: boolean; limit_value: number | null }[];
};

const FEATURE_BY_CODE = new Map(PLAN_FEATURES.map((feature) => [feature.code, feature]));

export function formatAmount(plan: Pick<PlanLike, 'price' | 'currency'>): string {
  const amount = Number(plan.price);
  const formatted = Number.isFinite(amount)
    ? amount.toLocaleString('es-CL', { maximumFractionDigits: 2 })
    : plan.price;
  return `${plan.currency} ${formatted}`;
}

export function featureSummary(plan: PlanLike): string {
  const enabled = plan.features.filter((feature) => feature.enabled);
  if (enabled.length === 0) return '—';
  return enabled
    .map((feature) => {
      const definition = FEATURE_BY_CODE.get(feature.code);
      const label = definition?.shortLabel ?? feature.code;
      return definition?.limitLabel && feature.limit_value != null
        ? `${label}: ${feature.limit_value}`
        : label;
    })
    .join(' · ');
}
```

Actualizar `web/src/features/saas/SaasPlansPage.tsx`: borrar `FEATURE_BY_CODE`, `formatAmount` y `featureSummary` locales, importar `{ featureSummary, formatAmount } from './planFormat'` y quitar el import ya no usado de `PLAN_FEATURES`.

- [x] **Step 4: Ejecutar el test**

Run: `cd web && npx vitest run src/features/saas --maxWorkers=4`
Expected: PASS (incluye los tests existentes de `SaasPlansPage`).

- [x] **Step 5: Añadir tipos y API pública**

En `web/src/api/types.ts`:

```typescript
export type PublicPlanFeature = {
  code: string;
  enabled: boolean;
  limit_value: number | null;
};

export type PublicPlan = {
  id: UUID;
  code: string;
  name: string;
  description: string;
  price: string;
  currency: string;
  billing_period: 'monthly' | 'yearly';
  trial_days: number;
  is_default: boolean;
  features: PublicPlanFeature[];
};

export type RegisterCompanyInput = {
  company_name: string;
  email: string;
  password: string;
  first_name?: string;
  plan?: string;
};

export type RegisterCompanyResponse = {
  company_id: UUID;
  company_name: string;
  email: string;
  detail: string;
};

export type VerifyEmailResponse = {
  access: string;
  refresh: string;
  user: User;
};
```

Crear `web/src/api/publicAccounts.ts`:

```typescript
import type { ApiClient } from './client';
import type {
  Paginated, PublicPlan, RegisterCompanyInput, RegisterCompanyResponse,
  VerifyEmailResponse,
} from './types';

export function createPublicAccountsApi(client: ApiClient) {
  return {
    plans: () => client.request<Paginated<PublicPlan>>('/api/v1/plans/', { auth: false }),
    registerCompany: (input: RegisterCompanyInput) =>
      client.request<RegisterCompanyResponse>('/api/v1/auth/register-company/', {
        method: 'POST', body: input, auth: false,
      }),
    verifyEmail: (token: string) =>
      client.request<VerifyEmailResponse>('/api/v1/auth/verify-email/', {
        method: 'POST', body: { token }, auth: false,
      }),
    resendVerification: (email: string) =>
      client.request<{ detail: string }>('/api/v1/auth/resend-verification/', {
        method: 'POST', body: { email }, auth: false,
      }),
  };
}
```

En `web/src/api/runtime.ts`: `import { createPublicAccountsApi } from './publicAccounts';` y al final `export const publicAccountsApi = createPublicAccountsApi(apiClient);`.

En `web/src/api/queryKeys.ts`, dentro del objeto: `publicPlans: () => ['public-plans'] as const,`.

- [x] **Step 6: Verificar tipos**

Run: `cd web && npm run build`
Expected: build sin errores de TypeScript.

- [x] **Step 7: Deja los cambios sin commitear y avisa del punto de control.**

---

### Task 5: Página pública `/precios` con diálogo de contratación

**Files:**
- Create: `web/src/features/public/PublicPricingPage.tsx`
- Create: `web/src/features/public/SignupDialog.tsx`
- Test: `web/src/features/public/PublicPricingPage.test.tsx`

**Interfaces:**
- Consumes: `publicAccountsApi`, `queryKeys.publicPlans()`, `formatAmount`, `featureSummary`, componentes `Button/Field/Input/Dialog/ErrorBanner/Skeleton/EmptyState`.
- Produces: `<PublicPricingPage />` montable en `/precios`; diálogo con estados `form` → `pending` (reenvío).

- [x] **Step 1: Escribir el test que falla**

```tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, test } from 'vitest';

import { server } from '../../test/server';
import { PublicPricingPage } from './PublicPricingPage';

const planFixture = {
  id: 'plan-1', code: 'basico', name: 'Básico', description: 'Agenda y clientes.',
  price: '19990.00', currency: 'CLP', billing_period: 'monthly', trial_days: 14,
  is_default: true,
  features: [{ code: 'sales', enabled: true, limit_value: null }],
};

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <PublicPricingPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('PublicPricingPage', () => {
  test('lista los planes públicos y abre el formulario de contratación', async () => {
    server.use(
      http.get('http://api.test/api/v1/plans/', () =>
        HttpResponse.json({ count: 1, next: null, previous: null, results: [planFixture] }),
      ),
    );
    renderPage();

    expect(await screen.findByText('Básico')).toBeInTheDocument();
    expect(screen.getByText('CLP 19.990')).toBeInTheDocument();
    expect(screen.getByText('Ventas y caja')).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: 'Contratar' }));
    expect(await screen.findByLabelText('Nombre de la empresa')).toBeInTheDocument();
    expect(screen.getByLabelText('Correo')).toBeInTheDocument();
  });

  test('tras registrar muestra el estado de revisión del correo', async () => {
    server.use(
      http.get('http://api.test/api/v1/plans/', () =>
        HttpResponse.json({ count: 1, next: null, previous: null, results: [planFixture] }),
      ),
      http.post('http://api.test/api/v1/auth/register-company/', () =>
        HttpResponse.json({
          company_id: 'c-1', company_name: 'Barbería', email: 'dueno@example.com',
          detail: 'Revisa tu correo para activar tu cuenta.',
        }, { status: 201 }),
      ),
    );
    renderPage();

    await userEvent.click(await screen.findByRole('button', { name: 'Contratar' }));
    await userEvent.type(screen.getByLabelText('Nombre de la empresa'), 'Barbería');
    await userEvent.type(screen.getByLabelText('Correo'), 'dueno@example.com');
    await userEvent.type(screen.getByLabelText('Contraseña'), 'Clave-Segura-2026!');
    await userEvent.click(screen.getByRole('button', { name: 'Crear cuenta' }));

    expect(await screen.findByText(/Revisa tu correo/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Reenviar enlace' })).toBeInTheDocument();
  });
});
```

- [x] **Step 2: Ejecutar y ver que falla**

Run: `cd web && npx vitest run src/features/public --maxWorkers=4`
Expected: FAIL (no existe `PublicPricingPage`).

- [x] **Step 3: Implementar `SignupDialog.tsx`**

```tsx
import { zodResolver } from '@hookform/resolvers/zod';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';

import { ApiError } from '../../api/client';
import { publicAccountsApi } from '../../api/runtime';
import type { PublicPlan } from '../../api/types';
import { Button } from '../../components/ui/Button';
import { Dialog } from '../../components/ui/Dialog';
import { ErrorBanner } from '../../components/ui/ErrorBanner';
import { Field, Input } from '../../components/ui/Field';

const schema = z.object({
  company_name: z.string().min(2, 'Ingresa el nombre de tu empresa.'),
  first_name: z.string().max(150).optional(),
  email: z.string().min(1, 'Ingresa tu correo.').email('Ingresa un correo válido.'),
  password: z.string().min(12, 'Usa al menos 12 caracteres.'),
});

type FormValues = z.infer<typeof schema>;

type Props = {
  plan: PublicPlan | null;
  onOpenChange: (open: boolean) => void;
};

export function SignupDialog({ plan, onOpenChange }: Props) {
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string[]>>({});
  const [pendingEmail, setPendingEmail] = useState<string | null>(null);
  const [resent, setResent] = useState(false);
  const {
    register, handleSubmit, reset,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { company_name: '', first_name: '', email: '', password: '' },
  });

  const open = plan !== null;
  const close = (next: boolean) => {
    if (!next) {
      reset();
      setSubmitError(null);
      setFieldErrors({});
      setPendingEmail(null);
      setResent(false);
    }
    onOpenChange(next);
  };

  async function onSubmit(values: FormValues) {
    if (!plan) return;
    setSubmitError(null);
    setFieldErrors({});
    try {
      const result = await publicAccountsApi.registerCompany({
        company_name: values.company_name,
        first_name: values.first_name || undefined,
        email: values.email,
        password: values.password,
        plan: plan.code,
      });
      setPendingEmail(result.email);
    } catch (error) {
      if (error instanceof ApiError) {
        setSubmitError(error.message);
        if (error.fields) setFieldErrors(error.fields);
      } else {
        setSubmitError('No se pudo crear la cuenta. Intenta nuevamente.');
      }
    }
  }

  async function resend() {
    if (!pendingEmail) return;
    setResent(false);
    try {
      await publicAccountsApi.resendVerification(pendingEmail);
      setResent(true);
    } catch {
      setSubmitError('No se pudo reenviar el enlace. Intenta nuevamente.');
    }
  }

  const errorFor = (name: keyof FormValues) =>
    fieldErrors[name]?.[0] ?? errors[name]?.message;

  return (
    <Dialog
      open={open}
      onOpenChange={close}
      title={pendingEmail ? 'Revisa tu correo' : `Contratar plan ${plan?.name ?? ''}`}
      description={
        pendingEmail
          ? `Enviamos un enlace de activación a ${pendingEmail}. Ábrelo para entrar a tu panel.`
          : 'Crea la cuenta de tu empresa. Te enviaremos un correo para activarla.'
      }
    >
      {pendingEmail ? (
        <div className="space-y-4">
          {resent ? <p className="text-sm text-ink">Enviamos un nuevo enlace.</p> : null}
          {submitError ? <ErrorBanner message={submitError} /> : null}
          <Button type="button" variant="secondary" onClick={resend} className="w-full">
            Reenviar enlace
          </Button>
        </div>
      ) : (
        <form className="space-y-4" onSubmit={handleSubmit(onSubmit)} noValidate>
          {submitError ? <ErrorBanner message={submitError} /> : null}
          <Field label="Nombre de la empresa" htmlFor="signup-company" error={errorFor('company_name')}>
            <Input id="signup-company" {...register('company_name')} />
          </Field>
          <Field label="Tu nombre" htmlFor="signup-name" error={errorFor('first_name')}>
            <Input id="signup-name" autoComplete="given-name" {...register('first_name')} />
          </Field>
          <Field label="Correo" htmlFor="signup-email" error={errorFor('email')}>
            <Input id="signup-email" type="email" autoComplete="email" {...register('email')} />
          </Field>
          <Field label="Contraseña" htmlFor="signup-password" error={errorFor('password')}>
            <Input
              id="signup-password" type="password" autoComplete="new-password"
              {...register('password')}
            />
          </Field>
          <Button type="submit" loading={isSubmitting} loadingLabel="Creando cuenta…" className="w-full">
            Crear cuenta
          </Button>
        </form>
      )}
    </Dialog>
  );
}
```

Nota: si `Button` no admite la variante usada, revisar `web/src/components/ui/Button.tsx` y alinear con las variantes existentes (`primary`/`secondary`). Si `Field` no asocia el error, seguir el patrón de `LoginPage`.

- [x] **Step 4: Implementar `PublicPricingPage.tsx`**

```tsx
import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { Link } from 'react-router-dom';

import { queryKeys } from '../../api/queryKeys';
import { publicAccountsApi } from '../../api/runtime';
import type { PublicPlan } from '../../api/types';
import { Button } from '../../components/ui/Button';
import { EmptyState } from '../../components/ui/EmptyState';
import { ErrorBanner } from '../../components/ui/ErrorBanner';
import { Skeleton } from '../../components/ui/Skeleton';
import { featureSummary, formatAmount } from '../saas/planFormat';
import { SignupDialog } from './SignupDialog';

const PERIOD_LABEL: Record<string, string> = { monthly: 'mes', yearly: 'año' };

export function PublicPricingPage() {
  const [selected, setSelected] = useState<PublicPlan | null>(null);
  const plansQuery = useQuery({
    queryKey: queryKeys.publicPlans(),
    queryFn: () => publicAccountsApi.plans(),
  });

  return (
    <main className="min-h-screen bg-surface">
      <header className="mx-auto flex max-w-5xl items-center justify-between px-6 py-6">
        <span className="text-sm font-semibold uppercase tracking-wide text-brand">AGENDA</span>
        <Link to="/login" className="text-sm font-medium text-ink hover:underline">
          Ya tengo cuenta
        </Link>
      </header>

      <section className="mx-auto max-w-5xl px-6 pb-6 text-center">
        <h1 className="text-3xl font-semibold text-ink">Agenda para tu negocio</h1>
        <p className="mx-auto mt-3 max-w-2xl text-muted">
          Reservas, clientes, equipo, inventario y reportes en un solo panel.
          Elige un plan y comienza hoy mismo; activa tu cuenta desde tu correo.
        </p>
      </section>

      <section className="mx-auto max-w-5xl px-6 pb-16">
        {plansQuery.isError ? (
          <ErrorBanner message="No pudimos cargar los planes. Recarga la página." />
        ) : plansQuery.isLoading ? (
          <div className="grid gap-4 md:grid-cols-3">
            <Skeleton className="h-64" />
            <Skeleton className="h-64" />
            <Skeleton className="h-64" />
          </div>
        ) : (plansQuery.data?.results.length ?? 0) === 0 ? (
          <EmptyState title="Pronto habrá planes disponibles" />
        ) : (
          <div className="grid gap-4 md:grid-cols-3">
            {plansQuery.data?.results.map((plan) => (
              <article key={plan.id} className="flex flex-col rounded-xl border border-line bg-panel p-6 shadow-sm">
                <h2 className="text-lg font-semibold text-ink">{plan.name}</h2>
                <p className="mt-1 text-sm text-muted">{plan.description}</p>
                <p className="mt-4 text-2xl font-semibold text-ink">
                  {formatAmount(plan)}
                  <span className="text-sm font-normal text-muted"> / {PERIOD_LABEL[plan.billing_period] ?? plan.billing_period}</span>
                </p>
                <p className="mt-1 text-sm text-muted">{plan.trial_days} días de prueba</p>
                <p className="mt-4 flex-1 text-sm text-ink">{featureSummary(plan)}</p>
                <Button className="mt-6 w-full" onClick={() => setSelected(plan)}>
                  Contratar
                </Button>
              </article>
            ))}
          </div>
        )}
      </section>

      <SignupDialog plan={selected} onOpenChange={(open) => { if (!open) setSelected(null); }} />
    </main>
  );
}
```

Nota: confirmar las props reales de `EmptyState` y `Skeleton` antes de escribir (usar las mismas que `SaasPlansPage`).

- [x] **Step 5: Ejecutar los tests**

Run: `cd web && npx vitest run src/features/public --maxWorkers=4`
Expected: PASS.

- [x] **Step 6: Deja los cambios sin commitear y avisa del punto de control.**

---

### Task 6: Página `/verificar`, rutas públicas y enlace desde login

**Files:**
- Create: `web/src/lib/hardNavigate.ts`
- Create: `web/src/features/public/VerifyEmailPage.tsx`
- Test: `web/src/features/public/VerifyEmailPage.test.tsx`
- Modify: `web/src/app/router.tsx`
- Modify: `web/src/features/auth/LoginPage.tsx`

**Interfaces:**
- Consumes: `publicAccountsApi.verifyEmail`, `localSessionStore.writeRefresh`, `sessionRuntime`.
- Produces: rutas públicas `/precios` y `/verificar`; `hardNavigate(path)`.

- [x] **Step 1: Escribir el test que falla**

```tsx
import { render, screen } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, expect, test, vi } from 'vitest';

import { REFRESH_KEY } from '../../auth/sessionStore';
import { server } from '../../test/server';
import { VerifyEmailPage } from './VerifyEmailPage';

vi.mock('../../lib/hardNavigate', () => ({ hardNavigate: vi.fn() }));

function renderPage(token: string) {
  render(
    <MemoryRouter initialEntries={[`/verificar?token=${token}`]}>
      <Routes>
        <Route path="/verificar" element={<VerifyEmailPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('VerifyEmailPage', () => {
  test('guarda la sesión y entra al panel cuando el token es válido', async () => {
    server.use(
      http.post('http://api.test/api/v1/auth/verify-email/', () =>
        HttpResponse.json({
          access: 'access-1', refresh: 'refresh-1',
          user: { id: 'u-1', email: 'dueno@example.com', first_name: 'Dueña', last_name: '',
                  is_saas_admin: false, is_superuser: false, must_change_password: false },
        }),
      ),
    );
    const { hardNavigate } = await import('../../lib/hardNavigate');
    renderPage('token-valido');

    expect(await screen.findByText(/Activando tu cuenta/i)).toBeInTheDocument();
    await vi.waitFor(() => expect(hardNavigate).toHaveBeenCalledWith('/'));
    expect(localStorage.getItem(REFRESH_KEY)).toBe('refresh-1');
  });

  test('muestra el error cuando el token venció', async () => {
    server.use(
      http.post('http://api.test/api/v1/auth/verify-email/', () =>
        HttpResponse.json({ token: ['El enlace no es válido o venció.'] }, { status: 400 }),
      ),
    );
    renderPage('token-vencido');
    expect(await screen.findByText('El enlace no es válido o venció.')).toBeInTheDocument();
  });
});
```

- [x] **Step 2: Ejecutar y ver que falla**

Run: `cd web && npx vitest run src/features/public/VerifyEmailPage.test.tsx --maxWorkers=4`
Expected: FAIL (no existe el componente ni `hardNavigate`).

- [x] **Step 3: Implementar `hardNavigate` y `VerifyEmailPage`**

`web/src/lib/hardNavigate.ts`:

```typescript
export function hardNavigate(path: string) {
  window.location.assign(path);
}
```

`web/src/features/public/VerifyEmailPage.tsx`:

```tsx
import { useEffect, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';

import { ApiError } from '../../api/client';
import { publicAccountsApi, sessionRuntime } from '../../api/runtime';
import { localSessionStore } from '../../auth/sessionStore';
import { ErrorBanner } from '../../components/ui/ErrorBanner';
import { hardNavigate } from '../../lib/hardNavigate';

export function VerifyEmailPage() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token') ?? '';
  const started = useRef(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // StrictMode vuelve a ejecutar el efecto; el token es de un solo uso.
    if (started.current) return;
    started.current = true;
    if (!token) {
      setError('Falta el enlace de verificación.');
      return;
    }
    publicAccountsApi.verifyEmail(token).then((data) => {
      localSessionStore.writeRefresh(data.refresh);
      sessionRuntime.accessToken = data.access;
      hardNavigate('/');
    }).catch((cause) => {
      setError(cause instanceof ApiError ? cause.message : 'No se pudo verificar la cuenta.');
    });
  }, [token]);

  return (
    <main className="flex min-h-screen items-center justify-center bg-surface p-6">
      <section className="w-full max-w-sm rounded-xl border border-line bg-panel p-8 text-center shadow-sm">
        <p className="text-sm font-semibold uppercase tracking-wide text-brand">AGENDA</p>
        <h1 className="mt-1 text-2xl font-semibold text-ink">
          {error ? 'No pudimos activar tu cuenta' : 'Activando tu cuenta…'}
        </h1>
        {error ? (
          <div className="mt-4 space-y-4">
            <ErrorBanner message={error} />
            <Link to="/precios" className="text-sm font-medium text-brand hover:underline">
              Volver a los planes
            </Link>
          </div>
        ) : (
          <p className="mt-2 text-sm text-muted">Esto toma solo un momento.</p>
        )}
      </section>
    </main>
  );
}
```

- [x] **Step 4: Registrar las rutas y el enlace de login**

En `web/src/app/router.tsx`, importar ambas páginas y añadir antes de `/login`:

```tsx
{ path: '/precios', element: <PublicPricingPage /> },
{ path: '/verificar', element: <VerifyEmailPage /> },
```

En `web/src/features/auth/LoginPage.tsx`, importar `Link` desde `react-router-dom` y añadir dentro de la `section`, después del `</form>`:

```tsx
<p className="mt-4 text-center text-sm text-muted">
  ¿Aún no tienes cuenta?{' '}
  <Link to="/precios" className="font-medium text-brand hover:underline">Ver planes</Link>
</p>
```

- [x] **Step 5: Ejecutar los tests**

Run: `cd web && npx vitest run src/features/public src/features/auth --maxWorkers=4`
Expected: PASS (el test de `VerifyEmailPage` y los existentes de login).

- [x] **Step 6: Deja los cambios sin commitear y avisa del punto de control.**

---

### Task 7: Verificación integral

**Files:** sin cambios de código salvo correcciones que aparezcan.

- [x] **Step 1: Suite backend completa**

Run: `cd backend && DJANGO_TESTING=true python manage.py test apps -v 1`
Expected: PASS. Si algo falla, corregir con TDD (test rojo primero) y re-ejecutar.

- [x] **Step 2: Suite web, build y lint**

Run:
```
cd web && npm test -- --run --maxWorkers=4
cd web && npm run build
cd web && npm run lint
```
Expected: 0 fallos, build sin errores, lint limpio.

- [x] **Step 3: Prueba funcional en navegador**

Levantar backend (`python manage.py runserver 8000`) y web (`npm run dev`) y recorrer:

1. `/precios` en tema claro y oscuro: planes, precios, botón `Contratar`.
2. Registrar con un correo real de prueba → aparece "Revisa tu correo".
3. En la consola del backend (EMAIL_BACKEND console) copiar el enlace `/verificar?token=...`, abrirlo → redirige a `/` y entra al panel con la empresa creada y el plan elegido.
4. Cerrar sesión y entrar de nuevo con correo/contraseña → funciona.
5. Intentar registrarse con el mismo correo → "Ya existe una cuenta con este correo. Inicia sesión."
6. Verificar el mismo enlace dos veces → "La cuenta ya está verificada."
7. Login muestra "¿Aún no tienes cuenta? Ver planes" y navega a `/precios`.

Registrar evidencia (snapshot/estilos computados; las capturas del navegador interno no están disponibles) y reportar diferencias.

- [x] **Step 4: Reporte final y autorización**

Resumir cambios, comandos ejecutados y resultados. Pedir autorización explícita antes de commitear/pushear (el commit de la spec `47d552b` sigue sin publicarse).

---

## Autorevisión del plan

- Cobertura de la spec: alta con usuario inactivo (Task 1), suscripción diferida y plan elegido (Tasks 1-2), token 48 h de un solo uso (Task 2), reenvío genérico (Task 2), limpieza (Task 3), SMTP/`AGENDA_WEB_BASE_URL` (Tasks 2-3), `/precios` + diálogo + estado pendiente (Task 5), `/verificar` con auto-login (Task 6), enlace en login (Task 6), extracción de formato de planes (Task 4), pruebas y despliegue (Task 7).
- Sin placeholders de código; los pasos que dependen de componentes existentes indican el archivo a cotejar (`Button`, `EmptyState`, `Skeleton`, `Field`) y con qué patrón alinearse.
- Nombres consistentes: `publicAccountsApi`, `queryKeys.publicPlans`, `formatAmount`, `featureSummary`, `send_verification_email`, `hardNavigate`, sal `identity.email-verification`.
- Sin migraciones; el modelo no cambia.
