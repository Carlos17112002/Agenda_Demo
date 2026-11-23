# Alta autoservicio con verificación de correo — Diseño

**Fecha:** 2026-11-23
**Estado:** Aprobado (enfoque A); pendiente revisión del spec escrito

## Objetivo

Permitir que un visitante que llega por internet vea los planes del producto, elija uno, cree su empresa y se registre solo, sin intervención del superadmin. El acceso queda bloqueado hasta que confirme su correo mediante un enlace de activación.

## Alcance

**Incluye:**
- Página pública `/precios` con descripción del producto y planes reales (solo activos).
- Formulario de alta: empresa, nombre del propietario, correo, contraseña y plan.
- Cuenta creada pero inactiva hasta verificar el correo.
- Envío de correo de verificación (Gmail SMTP en producción) con token firmado de 48 h.
- Pantalla `/verificar` que activa la cuenta, inicia sesión y entra al panel.
- Reenvío de verificación con límites.
- Limpieza de registros nunca verificados (comando manual).

**No incluye:**
- Pasarela de pago: "contratar" = iniciar prueba; el cobro queda para una etapa posterior.
- Captcha: la mitigación inicial son los límites por IP; si se abre al público general se añadirá después.
- Selección de sucursal/branding en el alta: se configura ya dentro del panel.
- Notificaciones al superadmin por nuevo registro (visible en `/saas`).

## Decisiones clave

1. **Acceso bloqueado hasta verificar.** El propietario se crea con `is_active=False`; simplejwt ya rechaza el login de usuarios inactivos.
2. **La suscripción de prueba inicia al verificar**, no al registrarse, para no consumir días de prueba mientras la cuenta está bloqueada.
3. **La contraseña la elige el visitante** (mínimo 12 caracteres, validadores de Django). No se envían contraseñas por correo.
4. **El slug se genera en el servidor** a partir del nombre de la empresa (con sufijo si está ocupado), oculto al visitante. Se puede ajustar después en Marca.
5. **Correo con Gmail SMTP** (clave de aplicación) mediante el backend SMTP estándar de Django; el código es el mismo para cualquier proveedor.
6. **Auto-login tras verificar**: la pantalla `/verificar` guarda el refresh token recibido y recarga la app; el flujo de restauración existente activa la empresa única y entra al panel.

## Flujo del visitante

1. Entra a `/precios` (pública) y ve la descripción del producto y las tarjetas de planes: nombre, precio (`CLP 19.990`), período, días de prueba y funcionalidades.
2. Pulsa "Contratar" en un plan → se abre el formulario con el plan preseleccionado (también acepta `?plan=<code>`).
3. Completa empresa, nombre, correo, contraseña y confirmación → `POST /api/v1/auth/register-company/`.
4. Ve la pantalla "Revisa tu correo" con su dirección y un botón de reenvío.
5. Abre el enlace del correo (`/verificar?token=…`): la cuenta se activa, se inicia la prueba y queda dentro del panel.
6. Si el enlace venció, puede pedir otro desde "Revisa tu correo" o desde el login.

## Backend

### Endpoints

| Método y ruta | Estado | Cambio |
|---|---|---|
| `GET /api/v1/plans/` | Existe (AllowAny, solo activos) | Sin cambios |
| `POST /api/v1/auth/register-company/` | Existe (AllowAny, throttle 5/h) | Acepta `plan`, genera slug, crea usuario inactivo sin suscripción, envía correo |
| `POST /api/v1/auth/verify-email/` | Nuevo (AllowAny, throttle 10/h) | Valida token, activa, inicia suscripción, devuelve tokens |
| `POST /api/v1/auth/resend-verification/` | Nuevo (AllowAny, throttle 3/h) | Reenvía sin revelar si el correo existe |

### Registro (`CompanyRegistrationSerializer` / `CompanyRegistrationView`)

- Campos: `company_name` (1–180), `email`, `password` (12–128), `first_name` (opcional), `plan` (opcional, debe ser un plan activo).
- `slug`: deja de ser obligatorio; lo genera el servidor con `slugify(company_name)` truncado a 80 caracteres y sufijo `-2`, `-3`… si está ocupado.
- `validate_email`:
  - Cuenta activa existente → `"Ya existe una cuenta con este correo. Inicia sesión."`
  - Cuenta inactiva existente → `"Ya existe un registro pendiente con este correo. Revisa tu correo o solicita un reenvío."`
- `provision_company` gana el parámetro `defer_subscription=True` para este flujo: crea empresa, usuario (`is_active=False`) y membresía `owner`, sin suscripción. El resto de flujos (consola SaaS) no cambian.
- Tras crear, envía el correo de verificación y responde `201 {"detail": "Revisa tu correo para activar tu cuenta.", "email": "<correo>"}` sin credenciales ni tokens.

### Token de verificación

- `django.core.signing.dumps({"uid": …, "plan": "<code>"}, salt="identity.email-verification")` con `max_age = EMAIL_VERIFICATION_TIMEOUT` (48 h, nuevo setting).
- Uso único: si el usuario ya está activo, el endpoint responde `400 {"detail": "La cuenta ya está verificada."}` sin emitir tokens.
- Si el plan del token ya no existe o está inactivo al verificar, se usa `default_plan()`; si tampoco hay plan por defecto, la cuenta queda activa sin suscripción (el superadmin la ve como inactiva y puede asignarle plan).

### Confirmación (`VerifyEmailView`)

- `POST {"token": "..."}` → valida firma y vencimiento, activa al usuario, inicia suscripción con `start_subscription(company, plan, trial_days=plan.trial_days)` y registra auditoría `company.email_verified` (actor: el propio usuario). No cambia `company.status` (ya queda en `trial` por defecto).
- Responde igual que el login: `{"access", "refresh", "user"}` para el auto-login.

### Reenvío (`ResendVerificationView`)

- `POST {"email": "..."}` → si existe una cuenta inactiva con ese correo, regenera token y envía el correo. Siempre responde `200 {"detail": "Si la cuenta está pendiente, enviamos un nuevo enlace."}` (no revela existencia).

### Correo

- Asunto: `Activa tu cuenta de AGENDA`.
- Cuerpo: enlace `${AGENDA_WEB_BASE_URL}/verificar?token=…` y aviso de vencimiento (48 h).
- Nuevo setting `AGENDA_WEB_BASE_URL` (default `http://127.0.0.1:5173`).
- Producción (Gmail SMTP) por variables de entorno: `DJANGO_EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend`, `EMAIL_HOST=smtp.gmail.com`, `EMAIL_PORT=587`, `EMAIL_USE_TLS=true`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` (clave de aplicación), `DEFAULT_FROM_EMAIL`. En desarrollo se mantiene el backend de consola.

### Limpieza de registros nunca verificados

- Comando `python manage.py purge_unverified_companies --days 7 [--dry-run]`.
- Selecciona usuarios inactivos sin verificar (dueños de empresa, `date_joined` anterior al corte) y, en una transacción, elimina: eventos de auditoría de esa empresa (nunca llegó a operar), membresías, contextos de tenant, empresa y usuario. Sin suscripciones porque se difieren al verificar.
- Documentado como tarea manual/cron externo (Render Free no incluye cron jobs).

## Frontend (panel React)

### Rutas públicas nuevas

- `/precios` → `PublicPricingPage`.
- `/verificar` → `VerifyEmailPage`.
- Ambos fuera de los guards (accesibles sin sesión), con un layout público simple (marca AGENDA, centrado, máximo ~1100 px, tema claro por defecto y respeto del toggle si ya existe).

### Página de planes

- Consulta `['public-plans']` → `GET /api/v1/plans/` (cliente sin credenciales).
- Tarjetas por plan: nombre, descripción, precio formateado, período, "14 días de prueba" (o "Sin prueba"), funcionalidades activas con límites, Badge "Predeterminado" si aplica y botón "Contratar".
- Extracción de `formatAmount` y resumen de funcionalidades a `web/src/features/saas/planFormat.ts` para reutilizarlos en `SaasPlansPage` y esta página.
- Estados de carga (Skeleton), vacío y error con reintento.

### Formulario de alta

- Diálogo sobre `/precios` con el plan preseleccionado (o seleccionable entre los activos).
- Campos: nombre de la empresa, nombre del propietario, correo, contraseña, confirmación (deben coincidir) y plan.
- Zod + react-hook-form, mismos patrones que el resto del panel; errores de campos del servidor mapeados al formulario (`ApiError.fields`).
- Al recibir 201 se cierra el diálogo y la página pasa al estado "Revisa tu correo" con la dirección, el botón "Reenviar enlace" (llamada al endpoint, con confirmación visual) y un enlace para volver a planes.

### Pantalla de verificación

- Lee `token` del query string y llama a `POST /api/v1/auth/verify-email/` al montar (una sola vez).
- Éxito: guarda `refresh` con `localSessionStore.writeRefresh(...)` y hace `window.location.replace('/')`; la restauración de sesión existente refresca tokens, activa la empresa única y entra al panel.
- Error (token vencido/usado/cuenta ya verificada): mensaje claro y enlaces "Iniciar sesión" y "Volver a planes".
- Sin token: mensaje "El enlace no es válido".

### Login

- `LoginPage` añade el enlace "¿Aún no tienes cuenta? Ver planes" hacia `/precios`.

### Cliente API

- `web/src/api/publicAccounts.ts`: `plans()`, `registerCompany(input)`, `verifyEmail(token)`, `resendVerification(email)`; tipados nuevos en `api/types.ts`: `PublicPlan` (id, code, name, description, price, currency, billing_period, trial_days, is_default, features) y `RegisterCompanyInput` (company_name, first_name, email, password, plan).

## Errores y mensajes

| Caso | Respuesta | UI |
|---|---|---|
| Correo ya registrado (activo) | 400 campo `email` | Error bajo el campo |
| Registro pendiente mismo correo | 400 campo `email` con guía de reenvío | Error bajo el campo |
| Slug ocupado | Resuelto en servidor con sufijo | — |
| Plan inactivo/inexistente | 400 campo `plan` | Error bajo el plan |
| Clave corta o común | 400 campo `password` | Error bajo el campo |
| Token inválido/vencido | 400 `detail` | Pantalla de error con acciones |
| Token ya usado | 400 `detail` "La cuenta ya está verificada." | Pantalla de error con "Iniciar sesión" |
| Límite de intentos | 429 | Mensaje "Demasiados intentos. Espera unos minutos." |

## Seguridad

- Throttles por IP: registro 5/h (existente), confirmación 10/h, reenvío 3/h.
- Respuestas genéricas en reenvío (no filtra si un correo existe).
- Tokens firmados con `SECRET_KEY`, vencimiento 48 h y uso único.
- Validación de correo y slug únicos; creación atómica (empresa + usuario + membresía).
- Auditoría: `company.registered` (con `source=public_registration`, IP y user-agent, ya existente) y `company.email_verified`.
- Sin cambios a la regla de aislamiento por empresa: el alta crea una empresa nueva y su propietario; el resto del sistema no cambia.

## Pruebas

**Backend (`apps/tenancy/tests/test_public_registration.py`, `apps/identity/tests/test_email_verification.py`):**
- El registro con plan crea empresa + usuario inactivo sin suscripción y envía correo (con `locmem` backend en tests).
- Usuario inactivo no puede iniciar sesión.
- Verificación activa la cuenta, crea suscripción `trialing` con el plan elegido y devuelve tokens válidos.
- Token vencido, alterado o ya usado → 400 sin tokens.
- Plan inactivo rechazado; sin plan se usa el predeterminado al verificar.
- Slug automático único (colisiones → sufijo).
- Reenvío responde igual exista o no el correo.
- Comando de limpieza borra registros viejos no verificados y conserva los recientes (`--dry-run` no borra).
- El alta desde la consola SaaS (superadmin) mantiene su comportamiento actual.

**Web (Vitest + MSW):**
- `/precios` lista planes activos con precio, prueba y funcionalidades; estado vacío y error.
- Alta: envía el payload correcto (sin slug), muestra errores de campo y el estado "Revisa tu correo".
- Reenvío desde el estado pendiente llama al endpoint.
- `/verificar` con token válido guarda refresh y redirige; con token inválido muestra el error con enlaces.
- `/login` muestra el enlace a planes.

## Despliegue

- Render: definir las variables SMTP de Gmail y `AGENDA_WEB_BASE_URL` con el dominio del panel.
- Sin migraciones de base de datos (no hay cambios de modelos).
- Ejecutar la limpieza de registros no verificados manualmente o mediante un cron externo.

## Riesgos y limitaciones

- Cuentas basura: los throttles mitigan pero no eliminan el riesgo; captcha queda como siguiente paso si el volumen lo exige.
- Registros abandonados: consumen correo/slug hasta la limpieza (7 días), ejecutada manualmente.
- Gmail limita a ~500 correos/día; suficiente para el volumen inicial.
- El auto-login depende de una recarga completa del panel tras verificar (comportamiento intencional y documentado).
