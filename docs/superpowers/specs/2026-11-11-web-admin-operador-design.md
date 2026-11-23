# Panel web del operador — especificación de diseño

- Fecha: 2026-11-11
- Estado: aprobado; plan en `docs/superpowers/plans/2026-11-11-web-admin-operador.md`
- Cliente: `web/` (nuevo)
- Backend: sin cambios para el núcleo del panel; se amplía con inventario (objetos y
  archivos) y con `working-hours` en la sincronización móvil. La web consume esas
  extensiones en solo lectura.
- Complementa: `docs/superpowers/specs/2026-11-11-inventario-objetos-archivos-design.md`
  y `docs/superpowers/specs/2026-11-11-agenda-calendario-design.md`

## 1. Contexto y objetivo

AGENDA ya ofrece la API multiempresa (reservas, clientes, catálogo, equipo, reportes y marca) y una app Flutter para la operación móvil. Falta una interfaz de escritorio para dueños, administradores y recepción que permita trabajar cómodamente la agenda del día, la ficha de clientes, el catálogo y el equipo sin depender del teléfono.

El objetivo es un panel web del operador, cliente de la misma API y con el mismo aislamiento por empresa. La primera versión cubre el núcleo operativo y una vista de solo lectura del inventario; las ventas editables, la gestión completa de inventario (que vive en Flutter) y la administración SaaS quedan fuera.

## 2. Alcance

### Incluido en v1

1. Autenticación con correo y contraseña, selección de empresa y restauración de sesión.
2. Agenda: vista día y semana con eje horario, filtros por sucursal/trabajador/estado, alta de reserva con disponibilidad real (incluida desde un hueco del calendario), detalle, reprogramación, confirmación, cancelación, completado y no-show.
3. Clientes: listado con búsqueda, alta y edición, activo/inactivo e historial de reservas.
4. Servicios: alta, edición, activación/desactivación, precio, duración, buffers y sucursales.
5. Equipo: trabajadores, horario semanal, ausencias, pausas y bloqueos.
6. Resumen: ventas y caja de solo lectura con filtros de fecha y sucursal.
7. Marca: nombre visible, slug, colores primario/secundario, tema claro/oscuro y logo.
8. Tema visual derivado de la marca de la empresa activa, con modo claro y oscuro.
9. Inventario de solo lectura: listado de objetos (foto, SKU, estado, sucursal, responsable, garantía) y biblioteca de archivos con descarga autenticada. Sin crear, editar, subir ni eliminar.

### Fuera de v1

- Gestión de inventario desde la web: alta/edición de objetos, subida, borrado y stock.
- Compras, transferencias, conteos y valorización.
- Edición de ventas, caja, pagos o gastos.
- Panel SaaS de empresas, planes, suscripciones, pagos o facturas.
- Operación offline, sincronización local, push o notificaciones en tiempo real.
- Internacionalización distinta de español.
- Registro público de empresas o recuperación de contraseña dentro del panel.

## 3. Personas y permisos

El panel sirve a cualquier miembro activo de la empresa, con la interfaz limitada por los permisos que ya devuelve el bootstrap. El backend sigue siendo la autoridad.

| Rol típico | Uso esperado |
| --- | --- |
| Propietario / administrador | Todo el panel, incluida la marca. |
| Manager | Agenda, clientes, catálogo y equipo; reportes. |
| Recepción | Agenda y clientes. |
| Trabajador | Su agenda; el servidor limita las reservas a su propio perfil. |
| Contabilidad | Reportes de solo lectura. |

Permisos usados:

- `bookings.read`, `bookings.write` (un trabajador usa `bookings.own.read` / `bookings.own.write`)
- `customers.read`, `customers.write`
- `catalog.read`, `catalog.write`
- `workforce.read`, `workforce.write`
- `inventory.read` (solo lectura de objetos y archivos)
- `reports.read`
- `company.manage` (marca)

La UI oculta o deshabilita acciones sin permiso; nunca confía en ello como control de seguridad. Un `403` del servidor se muestra como permiso insuficiente. También se respetan las funcionalidades del plan (`features` del bootstrap): una sección cuyo módulo esté apagado no aparece en la navegación y se explica el estado si se accede por URL.

## 4. Arquitectura del cliente

### Stack

- React + TypeScript con Vite.
- React Router para rutas.
- TanStack Query para estado del servidor y caché de consultas.
- React Hook Form + Zod para formularios y validación previa.
- Tailwind CSS con variables CSS para los tokens de marca.
- Primitivas Radix para diálogos, selects, popovers y menús accesibles.
- Vitest + React Testing Library + Mock Service Worker para pruebas de unidad/integración.
- Playwright para pruebas end-to-end contra Django local.

No se usa una librería de componentes pesada: los componentes propios viven en `components/ui` y respetan los tokens de marca.

### Estructura propuesta

```text
web/
  index.html
  package.json
  vite.config.ts
  src/
    main.tsx
    app/                 router, providers, layout protegido
    api/                 cliente HTTP y módulos por dominio, tipos DTO
    auth/                AuthProvider, almacenamiento de sesión, guards
    components/ui/       botones, campos, tablas, diálogos, estados vacíos
    features/
      auth/              login
      companies/         selector de empresa
      agenda/            calendario, disponibilidad, formulario y detalle
      customers/         listado, formulario e historial
      services/          catálogo
      team/              trabajadores, horarios, ausencias y bloqueos
      summary/           ventas y caja
      inventory/         objetos y archivos de solo lectura
      branding/          editor de marca
    theme/               tokens, ThemeProvider, aplicación de marca
    lib/                 fechas, errores, permisos, formato
  e2e/
```

### Cliente HTTP

Un único cliente envuelve `fetch` y aplica:

- Base URL configurable (`VITE_API_BASE_URL`, por defecto `http://127.0.0.1:8000`).
- `Authorization: Bearer <access>` cuando hay sesión.
- `X-Tenant-Context: <contextId>` cuando hay empresa activa.
- Un solo intento de refresh ante `401`; si falla, cierra sesión.
- Normalización de errores a `{status, message, fields?}`:
  - `400`: mensaje por campo cuando exista.
  - `401`: refresh o logout.
  - `402`: suscripción/plan no habilitado.
  - `403`: permiso insuficiente.
  - `409`: conflicto de agenda o stock (se muestra el mensaje del servidor).
  - `0`/red: banner de reconexión con reintento manual.

### Caché y cambio de empresa

El panel no guarda datos de negocio en almacenamiento local. TanStack Query mantiene solo caché en memoria y se limpia por completo al cambiar de empresa o cerrar sesión. Cada consulta incluye la empresa activa en su clave para impedir resultados cruzados.

## 5. Sesión, empresa y contexto tenant

### Inicio de sesión

1. `POST /api/v1/auth/token/` con `{email, password}`.
2. Respuesta: `{access, refresh, user:{id, email, first_name, last_name, is_saas_admin}}`.
3. El access vive en memoria; el refresh se guarda en `localStorage` bajo `agenda.web.refresh`.
4. `GET /api/v1/companies/mine/`.
5. Si hay una sola empresa, se selecciona automáticamente; si hay varias, se muestra `/empresa`.

### Selección de empresa

1. `POST /api/v1/tenant-contexts/` con `{company: "<id>"}`.
2. Se guarda `{companyId, contextId, companyName}` en `localStorage` (`agenda.web.session`).
3. `GET /api/v1/mobile/bootstrap/` con el contexto.
4. Se aplican permisos, marca, sucursales y estado de suscripción.
5. Se limpia la caché de consultas y se navega a `/agenda`.

Al elegir otra empresa se crea siempre un contexto nuevo, aunque el anterior siga vigente. Esto replica el arreglo aplicado en Flutter y evita reutilizar el tenant equivocado.

### Restauración y cierre

- Al cargar: se lee el refresh, se obtiene un access nuevo con `POST /api/v1/auth/token/refresh/`, se restauran contexto y empresa guardados y se pide bootstrap.
- Si el contexto guardado ya no es válido (`401/403`), se pide de nuevo `/companies/mine/`: una empresa accesible se selecciona automáticamente y varias llevan al selector.
- Si el refresh ya no es válido, se limpia el almacenamiento y se muestra `/login`.
- Logout: `POST /api/v1/auth/logout/` con `{refresh}` (Bearer access), limpieza de almacenamiento y caché de consultas.
- No se persisten datos de negocio ni bootstrap en disco.

## 6. Rutas y layout

| Ruta | Pantalla | Permiso |
| --- | --- | --- |
| `/login` | Acceso | público |
| `/empresa` | Selector de empresa | sesión |
| `/agenda` | Agenda día/semana | `bookings.read` u `bookings.own.read` |
| `/clientes` | Clientes | `customers.read` |
| `/servicios` | Servicios | `catalog.read` |
| `/equipo` | Trabajadores y horarios | `workforce.read` |
| `/inventario` | Objetos y archivos (solo lectura) | `inventory.read` |
| `/resumen` | Ventas y caja | `reports.read` |
| `/marca` | Editor de marca | `company.manage` |

Layout protegido:

- Barra lateral con las secciones permitidas.
- Encabezado con logo/nombre de la empresa, selector de empresa cuando hay más de una, usuario y menú de cierre de sesión.
- Botón de recarga que invalida las consultas de la pantalla actual y vuelve a pedir bootstrap.
- Contenido pensado para escritorio (1280 px) y usable desde tablet (768 px); sin diseño móvil dedicado.

La raíz `/` redirige a `/agenda` si hay sesión y a `/login` si no.

## 7. Módulos

### 7.1 Agenda

Consulta:

- `GET /api/v1/bookings/` con `branch`, `worker`, `service`, `customer`, `status`, `date`, `date_from`, `date_to`, `page`, `ordering`.
- Vista día: `date=<día>`.
- Vista semana: `date_from`/`date_to` del lunes a domingo.

Alta:

1. Elegir sucursal, servicio, trabajador y día.
2. `GET /api/v1/bookings/availability/?branch=&service=&worker=&date=` devuelve `{date, timezone, slots:[{start_at, end_at, label}]}`.
3. Elegir una hora y un cliente existente o crear uno en el mismo diálogo.
4. `POST /api/v1/bookings/` con `{branch, customer, service, worker, start_at, notes}`.
5. Un `409` se muestra sin cerrar el formulario para elegir otro horario.

Detalle y acciones:

- `POST /api/v1/bookings/<id>/confirm/`
- `POST /api/v1/bookings/<id>/reschedule/` con `{start_at, worker?, reason?}`
- `POST /api/v1/bookings/<id>/cancel/`, `/complete/`, `/no-show/` con `{reason?}`
- `PATCH /api/v1/bookings/<id>/` solo modifica `notes`.
- La reprogramación usa la acción dedicada, nunca un PATCH genérico.

Presentación:

- La agenda siempre trabaja con una sucursal seleccionada; los límites del día y de la semana se calculan en la zona horaria de esa sucursal y el encabezado la indica.
- Vista día con columnas por trabajador y eje horario.
- Vista semana con una columna por día y el mismo eje horario; el rango de horas sale de los turnos de atención de la sucursal y, sin datos, usa 08:00–20:00.
- Los horarios se consultan con `GET /api/v1/working-hours/?branch=<id>` paginando todas las páginas (50 por página). Ese endpoint exige `workforce.read` y la función `workforce` del plan: un trabajador sin `workforce.read` recibe `403`, y recepción lo recibe solo si el plan no incluye `workforce`. Cuando la consulta falla (`403` o red), el calendario usa el respaldo 08:00–20:00, muestra un aviso y no bloquea la agenda. El plan de calendario no modifica ese permiso.
- Un clic en un hueco abre el alta con fecha y hora preseleccionadas; en la vista Día también preselecciona al trabajador de la columna. El diálogo consulta disponibilidad y solo permite confirmar un slot ofrecido.
- Colores por estado y por color del trabajador cuando exista.
- Acciones visibles según `bookings.write` u `bookings.own.write`; trabajador solo ve sus reservas porque el servidor ya filtra.

### 7.2 Clientes

- `GET /api/v1/customers/?search=&active=&ordering=&page=`.
- Alta/edición: `first_name`, `last_name`, `email`, `phone`, `document_id`, `notes`, `active`.
- Historial: `GET /api/v1/bookings/?customer=<id>&ordering=-start_at`.
- Listado con búsqueda por nombre, correo, teléfono o documento; estado vacío con acción de alta.
- Borrado lógico mediante `active=false` con confirmación.

### 7.3 Servicios

- `GET /api/v1/services/?search=&active=&branch=`.
- Alta/edición: `name`, `description`, `duration_minutes`, `price`, `buffer_before_minutes`, `buffer_after_minutes`, `branches`, `active`.
- Precio y duración obligatorios; duración entre 5 y 480 minutos; buffers entre 0 y 120; nombre único por empresa.
- Selección múltiple de sucursales. Si no se elige ninguna, el servicio queda disponible en todas las sucursales, según la regla del backend.

### 7.4 Equipo

Cuatro secciones dentro de la misma pantalla:

- Trabajadores: `GET/POST/PATCH /api/v1/workers/` con `first_name`, `last_name`, `email`, `phone`, `job_title`, `color`, `branches`, `active` y `membership` opcional.
- Horario semanal: `/api/v1/working-hours/` con `worker`, `branch`, `weekday` (0–6), `start_time`, `end_time`.
- Ausencias: `/api/v1/time-off/` con `worker`, `branch`, `starts_at`, `ends_at`, `reason`.
- Pausas y bloqueos: `/api/v1/breaks/` (`worker`, `branch`, `weekday`, `start_time`, `end_time`, `label`) y `/api/v1/blocked-slots/` (`worker`, `branch`, `starts_at`, `ends_at`, `reason`).

El alta de trabajador puede dejar `membership` vacío; la asignación de credenciales de acceso no forma parte de v1.

### 7.5 Resumen

Ventas:

- `GET /api/v1/reports/sales-summary/?date_from=&date_to=&branch=`.
- Se muestran `totals` (ventas, total, pagado, margen, ticket promedio), `by_day`, `by_payment_method`, `by_branch`, `top_services` y `top_products`.

Caja:

- `GET /api/v1/reports/cash-summary/?date_from=&date_to=&branch=`.
- Se muestran `totals`, `sessions`, `expenses_by_category` y `expenses_by_method`.

Rango inicial: últimos 7 días. Filtro por sucursal y rango de fechas reutilizado en ambas tarjetas. Sin acciones de escritura.

### 7.6 Marca

- `GET /api/v1/company/branding/` devuelve `display_name`, `logo_url`, `primary_color`, `secondary_color`, `theme_mode`, `booking_url`, `name`, `slug`, `can_manage`.
- `PATCH /api/v1/company/branding/` con `display_name`, `slug`, `primary_color`, `secondary_color`, `theme_mode`.
- `POST /api/v1/company/branding/logo/` multipart campo `logo`; `DELETE` para quitarlo.
- Logo válido: PNG, JPEG o WebP, máximo 2 MB y 4000 × 4000 px.
- Vista previa en vivo de colores, tema y logo.
- Advertencia explícita si el slug cambia porque altera el enlace público.
- Al guardar se refresca el bootstrap y se reaplica el tema en todo el panel.

### 7.7 Inventario (solo lectura)

Ruta `/inventario`, visible con permiso `inventory.read` y feature `inventory`. Dos
pestañas:

- **Objetos**: `GET /api/v1/inventory/products/?kind=asset&search=&branch=&status=&active=&page=`.
  Tabla con foto, nombre, SKU, estado (`status_display`), sucursal, responsable y fin de
  garantía. La foto se pide como blob autenticado con
  `GET /api/v1/inventory/products/{id}/photo/`; si no hay foto o la descarga falla,
  se muestra la inicial del nombre.
- **Archivos**: `GET /api/v1/inventory/documents/?search=&linked=&product=&page=`.
  Tabla con nombre y nombre original, vínculo, tamaño, autor y acción de descarga. La
  descarga usa `GET /api/v1/inventory/documents/{id}/download/` mediante `fetch` con
  Bearer y `X-Tenant-Context`, y se entrega como blob con `Content-Disposition`; nunca
  se enlaza una URL pública.

Reglas:

- Sin acciones de escritura: no hay alta, edición, subida ni eliminación.
- Los filtros de sucursal y estado se validan contra los choices del backend.
- La lista se pagina con el sobre `{count, next, previous, results}`.
- Un error de red muestra el banner de reconexión; un `403` explica que falta
  `inventory.read`.
- Cambiar de empresa limpia la caché de consultas y vuelve a la primera página.

## 8. Tema y accesibilidad

- `primary_color` y `secondary_color` se convierten en variables CSS; el tema claro/oscuro inicial sigue `theme_mode` de la empresa.
- El usuario puede alternar claro/oscuro en la sesión sin modificar la configuración de la empresa.
- Contraste mínimo AA en texto y controles; foco visible; navegación completa por teclado; diálogos con foco atrapado y cierre con Escape.
- Tablas con encabezados semánticos, estados vacíos descriptivos y mensajes de error junto al campo.

## 9. Errores y estados

- Carga inicial con esqueleto por pantalla; nunca una tabla vacía mientras se consulta.
- Sin resultados: mensaje claro y acción principal.
- Red caída: banner persistente con "Reintentar"; las acciones de escritura se deshabilitan.
- `409` de agenda: mensaje del servidor y opción de elegir otro horario.
- `402`: aviso con el mensaje del servidor indicando que el plan actual no habilita la acción; no se bloquea la navegación permitida. La facturación de la empresa queda fuera de v1, así que no se enlaza a una pantalla inexistente.
- `403`: aviso de permiso insuficiente y regreso a la última pantalla válida.
- Error inesperado: mensaje genérico con identificador de solicitud cuando el servidor lo entregue.

## 10. Pruebas

### Unitarias e integración (Vitest + RTL + MSW)

- Cliente HTTP: cabeceras, refresh único, logout ante refresh inválido y normalización de errores.
- AuthProvider: login, restauración, selección de empresa, cambio de empresa limpia la caché y recrea contexto.
- Permisos: rutas y acciones ocultas/deshabilitadas según bootstrap.
- Agenda: validación del formulario, flujo de disponibilidad, conflicto 409 y acciones
  de estado; rango horario desde turnos y respaldo 08:00–20:00; eje y columnas de la
  semana; clic en hueco abre el alta con fecha/hora/trabajador y consulta
  disponibilidad.
- Clientes, servicios y equipo: validaciones y envío de payloads.
- Marca: validación de colores, slug y logo; refresco de bootstrap.
- Resumen: render de totales y filtros.
- Inventario: listas de objetos y archivos con MSW, descarga de documento como blob
  con cabeceras, foto autenticada, filtros, paginación y estado sin permiso.

### End-to-end (Playwright, Django local)

1. Login del superadmin y selección de Estudio Aurora.
2. Alta de reserva usando disponibilidad, reprogramación y cancelación.
3. Alta de reserva desde un hueco de la semana; la grilla muestra el eje horario y la
   reserva aparece en la hora correcta.
4. Alta y búsqueda de cliente; historial con la reserva creada.
5. Alta de servicio y trabajador con horario; disponibilidad refleja el horario.
6. Resumen de ventas/caja para un rango conocido.
7. Edición de marca y verificación de tema y enlace público.
8. Inventario: listar objetos y archivos de Estudio Aurora, descargar un documento y
   comprobar que no existe ninguna acción de escritura.
9. Cambio a Marca Demo Visual: agenda e inventario vacíos, sin datos de Aurora y
   `X-Tenant-Context` nuevo.
10. Recarga de página: sesión restaurada en la empresa correcta.
11. Logout: almacenamiento y caché limpios; acceso a rutas privadas redirige a login.

Las extensiones de backend tienen sus propias pruebas dirigidas: inventario (objetos,
archivos, cuota, aislamiento) y `working-hours` en la sincronización móvil. La web no
cambia ninguna API del núcleo, pero consume esos endpoints y debe cubrirlos con MSW.
Si se ajusta CORS para un origen web no local, se cubrirá con una prueba de
configuración.

## 11. Fases de entrega

1. **Shell**: proyecto Vite, router, cliente HTTP, AuthProvider, login, selector de empresa, layout, tokens de marca y CI de lint/pruebas.
2. **Agenda**: consultas, vistas día/semana con eje horario, disponibilidad, alta (también desde hueco), detalle y transiciones.
3. **Clientes**: listado, búsqueda, alta/edición e historial.
4. **Servicios y equipo**: catálogo y gestión de trabajadores, horarios, ausencias y bloqueos.
5. **Resumen, inventario y marca**: reportes de solo lectura, inventario de solo lectura y editor de marca con vista previa.
6. **Cierre**: E2E, accesibilidad, documentación y build de producción.

Cada fase termina con pruebas verdes y validación visual en claro/oscuro.

## 12. Despliegue

- Desarrollo: Vite en `5173` con proxy `/api` y `/media` hacia `http://127.0.0.1:8000`.
- Producción: `npm run build` genera estáticos; se sirven con Nginx o Django con fallback a `index.html` para rutas del SPA.
- API y panel en el mismo origen recomendado; si no, definir `DJANGO_CORS_ORIGINS` y `VITE_API_BASE_URL`.
- Cabeceras recomendadas: CSP `script-src 'self'`, `frame-ancestors 'none'`, `Referrer-Policy: no-referrer`, HSTS en HTTPS.
- El despliegue general (Postgres, servidor de aplicaciones, correo, push) sigue su propio plan; este documento solo define el cliente web.

## 13. Riesgos y decisiones asumidas

- **Refresh en `localStorage`**: aceptado para v1 con CSP estricta y sin scripts de terceros. Antes de exponer el panel a internet se migrará a cookie httpOnly con CSRF.
- **Sin caché local**: el panel requiere conexión; evita repetir el problema de aislamiento de datos entre empresas.
- **Zona horaria**: toda hora de agenda se interpreta y muestra en la zona de la sucursal; el rango semanal se calcula con esa zona.
- **PATCH de reserva**: el backend solo permite editar notas por PATCH; reprogramar y cambiar estado usan acciones dedicadas.
- **Permisos de trabajador**: el servidor limita reservas y disponibilidad al propio perfil; la UI no necesita duplicar esa regla.
- **Límites de plan**: un `402` puede aparecer al crear trabajadores o sucursales; se muestra el mensaje del servidor.

No quedan decisiones abiertas para v1.

## 14. Criterios de aceptación

1. Un miembro con permisos inicia sesión, elige empresa y llega a la agenda sin pasos intermedios innecesarios.
2. La semana muestra un eje horario; el rango sale de los turnos y, sin datos, usa 08:00–20:00.
3. Puede crear una reserva solo con horarios ofrecidos por disponibilidad, también al hacer clic en un hueco del calendario; un conflicto muestra el mensaje del servidor y permite reintentar.
4. Puede reprogramar, confirmar, completar, marcar no-show y cancelar con el resultado reflejado en la agenda.
5. Clientes, servicios y equipo se crean y editan con validación local y errores del servidor visibles por campo.
6. El resumen coincide con los totales de la API para el mismo rango y sucursal.
7. La marca se edita con vista previa; al guardar, tema, logo y nombre se aplican en todo el panel y el enlace público es correcto.
8. Inventario lista objetos y archivos de la empresa y permite descargar con sesión; no ofrece ninguna acción de escritura.
9. Cambiar de empresa limpia los datos visibles, crea un contexto nuevo y ninguna consulta mezcla empresas.
10. Recargar la página restaura sesión y empresa; un contexto inválido lleva al selector o a la única empresa accesible.
11. Logout elimina tokens, contexto y caché; las rutas privadas redirigen a login.
12. La interfaz funciona en claro y oscuro, con teclado y contraste AA, en 1280 px y 768 px.
13. La app Flutter no se modifica desde este plan; el backend solo cambia por inventario, `working-hours` en sync y configuración de CORS/orígenes para el nuevo cliente.
