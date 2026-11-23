# Usuarios con local predeterminado — Diseño

**Fecha:** 2026-11-19
**Estado:** Aprobado por Carlos (diseño verbal) — pendiente revisión de este documento.

## Contexto

Hoy toda membresía es a nivel empresa: `Membership` guarda el rol y nada más.
No existe API ni pantalla para crear miembros dentro de una empresa; solo el
registro público y la consola SaaS crean al propietario. El panel web abre la
agenda en la primera sucursal (`branches[0]`) y Flutter hace lo mismo, sin
concepto de local asignado.

Carlos necesita que cada empresa pueda crear sus propios usuarios, asignarles un
local y que, al iniciar sesión, el panel y la app abran directamente en ese
local, pudiendo cambiarlo después.

Decisiones ya tomadas:

- El local asignado es **predeterminado editable**, no una restricción dura.
- Los usuarios se crean desde el **panel web**.
- Contraseña: **temporal generada por el sistema, visible una sola vez** y con
  cambio obligatorio en el primer ingreso.
- Gestión: alta, edición de rol/local/estado, baja lógica y **edición de
  permisos** del miembro.
- Si el rol es Trabajador, se puede **crear opcionalmente su perfil de
  trabajador** en la misma operación.
- El local predeterminado aplica a **web y Flutter**.

## Objetivos

1. Crear y administrar miembros de la empresa desde el panel web.
2. Asignar un local predeterminado por membresía.
3. Abrir la agenda en ese local al iniciar sesión, con selector disponible.
4. Entregar credenciales temporales de forma segura y forzar el primer cambio.
5. Permitir editar permisos del miembro reutilizando `PermissionGrant`.

## Fuera de alcance

- Restricción dura por local (ocultar/prohibir otros locales).
- Asignar varios locales por usuario.
- Pruebas de rendimiento y auditoría de seguridad (frentes separados ya
  acordados: staging + Locust después).
- Borrado físico de usuarios o membresías.
- Invitaciones por correo.

## Modelo de datos

### `Membership` (`apps/identity/models.py`)

- `default_branch` — FK a `tenancy.Branch`, `null=True, blank=True`,
  `on_delete=SET_NULL`, `related_name="default_for_memberships"`.
  - Debe pertenecer a la misma empresa; se valida en el serializer de alta y
    edición (no en la base para permitir migraciones sin bloqueo).
  - `SET_NULL` para no impedir la baja lógica de una sucursal.
- Sin cambios de unicidad: `(company, user)` sigue siendo único.
- La baja de un miembro solo marca `Membership.active=False`; **no** toca
  `User.is_active`, porque el mismo usuario puede pertenecer a otras empresas.

### `User` (`apps/identity/models.py`)

- `must_change_password` — `BooleanField(default=False)`.
  - `True` al crear un miembro con clave temporal.
  - Se limpia al cambiar la contraseña.
  - El login y el bootstrap lo exponen para que web y Flutter bloqueen.

### `WorkerProfile`

No cambia el modelo. Al crear un miembro con rol `worker` y la opción activa,
se crea un `WorkerProfile` con:

- `membership` = la membresía nueva.
- `company` = la empresa del contexto.
- `first_name` / `last_name` derivados del nombre ingresado (`first_name` es
  obligatorio en el modelo; si el nombre viene vacío se usa el correo).
- `email` = correo del usuario.
- `branches` = el local predeterminado, si existe.
- `color` = valor por defecto del modelo; sin horarios ni pausas (se configuran
  después en Equipo).
- `active = True`.

## API

### Miembros — nuevo `MembershipViewSet`

Registro: `router.register("members", MembershipViewSet, basename="member")` en
`config/urls.py`, dentro del router principal autenticado.

Permisos: `IsAuthenticated` + `HasTenantContext` + rol `owner` o `admin` de la
empresa del contexto. Un `admin` no puede crear, editar ni desactivar miembros
con rol `owner` o `admin`; solo el `owner` puede.

- `GET /api/v1/members/`
  - Lista paginada de membresías de la empresa del contexto.
  - Campos: `id`, `user` (`id`, `email`, `first_name`, `last_name`, `is_active`),
    `role`, `role_display`, `default_branch` (`id`, `name` o `null`),
    `active`, `created_at`.
  - Búsqueda por correo/nombre; orden por nombre.

- `POST /api/v1/members/`
  - Cuerpo:
    ```json
    {
      "email": "ana@empresa.cl",
      "first_name": "Ana",
      "last_name": "Pérez",
      "role": "reception",
      "default_branch": "uuid-o-null",
      "create_worker_profile": false
    }
    ```
  - Genera contraseña temporal con el mismo criterio que la consola SaaS
    (`get_random_string` + sufijo que cumple la política).
  - Crea `User` (inactivo no; activo con `must_change_password=True`) y
    `Membership`.
  - Si `create_worker_profile=true`, exige `role="worker"` y crea el
    `WorkerProfile` en la misma transacción.
  - Respuesta `201`:
    ```json
    {
      "member": { "...": "serializer de membresía" },
      "temporary_password": "Abc123...-Aa1!",
      "worker_profile": { "id": "..." }
    }
    ```
  - `worker_profile` es `null` cuando no se pidió. El formato de la clave
    temporal replica `generate_temporary_password()` de
    `apps/tenancy/serializers.py` (`get_random_string(12) + "-Aa1!"`).
  - La contraseña temporal **solo** aparece en esta respuesta; no se guarda en
    claro ni se envía por correo.

- `PATCH /api/v1/members/{id}/`
  - Permite `role`, `default_branch`, `active`, `first_name`, `last_name`.
  - No permite cambiar `company` ni `user`.
  - Validaciones:
    - `default_branch` de otra empresa → `400`.
    - Desactivar al último `owner` activo → `400`.
    - Un `admin` no puede editar un miembro `owner`/`admin` → `403`.
    - El usuario no puede desactivarse a sí mismo → `400`.

- `DELETE /api/v1/members/{id}/` → baja lógica (`active=False`), con las mismas
  protecciones anteriores. Devuelve `204`.

- Errores: correo existente → `400` ("Ya existe una cuenta con este correo.").

### Cambio de contraseña forzado

Nuevo endpoint en `apps/identity/views.py`:

- `POST /api/v1/auth/password/change/`
  - Autenticado (JWT normal), cuerpo:
    ```json
    { "current_password": "...", "new_password": "..." }
    ```
  - Valida con `validate_password`, verifica la clave actual y rechaza que la
    nueva sea igual.
  - Guarda la nueva clave y `must_change_password=False`.
  - Revoca tokens previos con `revoke_user_tokens(user)` (avanza
    `jwt_valid_after` y marca en lista negra los refresh existentes) y **luego**
    emite un par nuevo con `RefreshToken.for_user(user)`, de modo que su `iat`
    queda después del corte. Respuesta `200`:
    `{ "access": "...", "refresh": "...", "must_change_password": false }`.
  - Errores: `400` con `current_password` inválida o política incumplida.

### Bootstrap y login

- `LoginSerializer` agrega `must_change_password` al objeto `user`.
- `MobileBootstrapView` agrega:
  - `user.must_change_password`
  - `membership.default_branch`: `{ "id", "name" }` o `null`
  - `permission_catalog`: lista ordenada de `PERMISSION_CATALOG` (solo códigos;
    el panel pone etiquetas y agrupación)
  - `role_defaults`: mapa `{ rol: [permisos] }` desde `ROLE_DEFAULTS`, con
    `"*"` expandido a todo el catálogo, para que el editor muestre qué es
    heredado del rol.
- `PermissionGrantViewSet` no cambia: el panel lo usa para el editor de
  permisos (allow/deny, alcance empresa o local).

## Panel web

- Nueva sección **Usuarios** (`/usuarios`) en `NAV_ITEMS` con permiso
  `company.manage`.
- `MembersPage`:
  - Tabla: nombre, correo, rol, local, estado, acciones (Editar, Permisos,
    Desactivar).
  - Alta en diálogo: correo, nombre, apellidos, rol, local (solo locales
    activos), casilla "Crear perfil de trabajador" visible solo con rol
    Trabajador.
  - Al crear, modal con la contraseña temporal y botón "Copiar"; se cierra con
    Escape y el foco vuelve al disparador.
  - Edición: rol, local y estado con las mismas validaciones del backend.
  - Editor de permisos: lista agrupada por módulo (prefijo del código, p. ej.
    `bookings.*`), etiquetas en un mapa local del frontend; para cada permiso,
    estado (heredado del rol según `role_defaults`, permitir, denegar) y
    alcance (empresa o local). Las concesiones se guardan como `PermissionGrant`
    con `effect="allow"|"deny"` y `branch` opcional, vía
    `/api/v1/permission-grants/`.
- Cambio de clave obligatorio:
  - Ruta `/cambiar-clave` fuera del layout principal.
  - Si `bootstrap.user.must_change_password` es `true`, el guard redirige a esa
    ruta desde cualquier pantalla y bloquea la navegación hasta completar el
    cambio.
- Local predeterminado:
  - `AuthProvider` expone `defaultBranchId` desde
    `bootstrap.membership.default_branch`.
  - `AgendaPage` inicializa `branchId` con el local predeterminado solo si
    aparece en `branches` con `active !== false`; si no, usa el primer local
    activo y, en su defecto, el primero de la lista.
  - El selector de sucursal sigue funcionando igual.

## Flutter

- `Bootstrap.membership` expone `default_branch`; se agrega un getter
  `defaultBranchId`.
- `AgendaScreen` inicializa `_branchId` con el local predeterminado solo si
  está en `branches` y activo; si no, con el primer local activo y, en su
  defecto, con el primero de la lista.
- Si `bootstrap.user.must_change_password == true`, tras el login se muestra una
  pantalla de cambio de clave que llama a `/api/v1/auth/password/change/`;
  al completarla se recarga el bootstrap y se entra a la app.

## Seguridad

- Toda consulta y escritura queda acotada por `HasTenantContext` y por la
  empresa del `Membership`; nunca se acepta `company` desde el cliente.
- El local se valida contra la empresa del contexto.
- La contraseña temporal se genera en servidor y solo viaja una vez en la
  respuesta de alta; no se registra en logs ni en auditoría.
- Las mutaciones de miembros generan eventos de auditoría con el actor, el
  miembro afectado y los campos cambiados, sin incluir contraseñas.
- El endpoint de cambio de clave usa el throttle `user` existente y revoca
  tokens emitidos antes del cambio.

## Pruebas

### Backend

- Alta de miembro por propietario y por administrador; rechazo para roles sin
  permiso.
- `admin` no puede crear/editar `owner`/`admin`.
- `default_branch` de otra empresa → `400`.
- Desactivar al último `owner` → `400`; autodesactivación → `400`.
- Alta con `create_worker_profile` crea el perfil vinculado y con el local.
- Alta con correo existente → `400`.
- `must_change_password` viaja en login y bootstrap.
- Cambio de clave: clave actual incorrecta → `400`; éxito limpia la marca y
  revoca tokens previos.
- Aislamiento: un miembro de la empresa A no puede listar ni editar miembros de
  B (mismo patrón que las pruebas existentes de aislamiento).

### Web

- Vitest: formulario de alta valida campos y rol/local; tabla lista miembros;
  editor de permisos envía allow/deny correctos; `AgendaPage` usa el local
  predeterminado y cae al primero si no está.
- Playwright: crear miembro y ver credenciales una vez; iniciar sesión con el
  nuevo usuario y verificar redirección al local; cambio de clave forzado;
  intento de desactivar al último propietario muestra error.

### Flutter

- Prueba de `Bootstrap.fromJson` con `default_branch` y
  `must_change_password`.
- Prueba de selección inicial de local en la agenda.

## Migración y compatibilidad

- Migraciones nuevas: `must_change_password` con default `False` y
  `default_branch` nullable. No requieren relleno de datos.
- Clientes antiguos (Flutter ya instalado) ignoran los campos nuevos; el
  comportamiento previo (primera sucursal) se mantiene si el local es `null`.
- El repositorio no tiene commits; no se hará commit ni push sin autorización
  explícita de Carlos.

## Riesgos

- **Scope creep en permisos:** el editor de permisos puede crecer; se limita al
  catálogo existente y a allow/deny por empresa o local.
- **Usuarios existentes sin local:** quedan con `null` y siguen usando la
  primera sucursal hasta que un administrador les asigne una.
- **Clave temporal en pantalla:** depende de que el administrador la copie; el
  modal debe impedir que se pierda por accidente (confirmación al cerrar).
- **WorkerProfile duplicado:** si el correo ya tiene perfil de trabajador en la
  empresa, se rechaza el alta con un mensaje claro.
