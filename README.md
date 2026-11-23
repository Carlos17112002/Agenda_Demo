# AGENDA — plataforma SaaS

Base inicial de la plataforma multiempresa de agendamiento, inventario y gestión comercial.

## Estado

Fases 1 a 8 completadas para desarrollo local: API Django modular, identidad JWT, membresías, permisos configurables, contexto tenant, sucursales, auditoría, alta de empresa, recuperación de contraseña, revocación de sesiones, clientes, catálogo de servicios, trabajadores, horarios, ausencias, reservas con disponibilidad real, conflictos transaccionales, portal público de reservas, notificaciones por correo, inventario con libro de movimientos, compras, transferencias, conteos, valorización, ventas, caja, pagos, gastos, informes comerciales, planes configurables, periodos de prueba, suscripciones, pagos, facturas, límites por función, panel superadmin SaaS, API móvil con bootstrap, sincronización incremental, operaciones offline idempotentes, dispositivos y push en cola, y marca blanca por empresa (logo, nombre visible, colores, fondo claro u oscuro y enlace público de reservas) con editor dentro de la app. La app Flutter de `mobile/` consume esta API con agenda, inventario, alertas y perfil, y adopta el tema de la empresa activa. SQLite permanece como base predeterminada. Revisa `docs/architecture.md` para los pendientes de despliegue.

## Arranque local

Requisitos: Python 3.12+ (probado en 3.14) y dependencias de `backend/requirements.txt`.

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

La base local usa SQLite y se mantiene así por defecto. Para una futura transición, configura `AGENDA_USE_POSTGRES=true` junto con `DATABASE_URL`. No uses la clave de desarrollo en producción.

### App móvil (Flutter)

Con el backend en ejecución:

```powershell
cd mobile
flutter pub get
flutter run -d chrome      # navegador; usa -d <dispositivo> para móvil
```

La app apunta por defecto a `http://127.0.0.1:8000`; la pantalla de acceso permite cambiarlo. Con `DJANGO_DEBUG=true` CORS acepta cualquier origen; en otros entornos define `DJANGO_CORS_ORIGINS` con la lista separada por comas. La app aplica el nombre visible, logo, colores y fondo de la empresa activa al tema completo (claro por defecto; las empresas existentes y las nuevas parten en claro salvo que elijan oscuro); el perfil muestra el enlace público de reservas con acción para copiarlo, y el selector de empresa usa la identidad de cada empresa. El perfil incluye **Editar marca** para propietario/administrador (`company.manage`): nombre visible, identificador público, colores con presets, selector de fondo Claro/Oscuro con vista previa en vivo, y subida o eliminación de logo; al guardar exige conexión, advierte si el enlace de reservas cambia y recarga el bootstrap para que toda la app adopte la nueva identidad. Pruebas y análisis:

```powershell
cd mobile
flutter analyze
flutter test
```

### Panel web del operador (React)

El panel de `web/` ofrece agenda, clientes, servicios, equipo, inventario de solo
lectura, resumen y marca para operadores de una empresa. Requiere el backend en
ejecución:

```powershell
cd web
Copy-Item .env.example .env
npm install
npm run dev
```

Abre `http://127.0.0.1:5173`. Consulta `docs/web-admin.md` para variables de
entorno, pruebas E2E y despliegue con Nginx.

## API inicial

- `POST /api/v1/auth/token/` — email y contraseña; devuelve tokens JWT (máximo 5 intentos por minuto/IP).
- `POST /api/v1/auth/token/refresh/` — renovar token (tokens previos pasan a blacklist).
- `POST /api/v1/auth/logout/` — invalida el refresh token actual.
- `POST /api/v1/auth/password-reset/` — solicita restablecimiento (respuesta uniforme exista o no la cuenta).
- `POST /api/v1/auth/password-reset/confirm/` — `{ "token": "…", "new_password": "…" }`; token firmado, de un uso y válido por una hora.
- `POST /api/v1/auth/register-company/` — alta pública; crea empresa, cuenta propietaria, membresía inicial, suscripción de prueba con el plan predeterminado (si existe) y auditoría en una transacción.
- `GET /api/v1/companies/mine/` — empresas activas asociadas al usuario, con nombre visible, logo, colores, fondo y enlace público.
- `GET|PATCH /api/v1/company/branding/` — marca de la empresa activa: `display_name`, `slug`, `primary_color`, `secondary_color`, `theme_mode` (`light` u `dark`, claro por defecto) y `can_manage`. Editar requiere `company.manage` (propietario/administrador). El `slug` es único, en minúsculas y no puede usar identificadores reservados.
- `POST|DELETE /api/v1/company/branding/logo/` — sube o elimina el logo de la empresa; acepta PNG, JPEG o WebP de hasta 2 MB y 4000 × 4000 px. Ambas rutas auditan `company.branding_updated`.
- `POST /api/v1/tenant-contexts/` — `{ "company": "<uuid>" }`; crea contexto de 8 horas tras validar membresía.
- `GET /api/v1/tenant-contexts/current/` — contexto seleccionado.
- `GET /api/v1/branches/` y `POST /api/v1/branches/` — sucursales aisladas por tenant (escritura requiere permiso `branches.manage`).
- `/api/v1/permission-grants/` — grants allow/deny por membresía y sucursal; gestión restringida a propietario/administrador.
- `/api/v1/customers/` — clientes de la empresa (`customers.read` / `customers.write`); búsqueda por nombre, correo, teléfono o documento y filtro `active`.
- `/api/v1/services/` — catálogo de servicios con duración, precio, buffers y sucursales opcionales (`catalog.read` / `catalog.write`); filtros `active` y `branch`.
- `/api/v1/workers/` — trabajadores con sucursales y vínculo opcional a membresía (`workforce.read` / `workforce.write`).
- `/api/v1/working-hours/` — turnos semanales por trabajador y sucursal; valida solapamientos y orden de horas.
- `/api/v1/time-off/` — ausencias por trabajador y sucursal opcional.
- `/api/v1/breaks/` — pausas semanales por trabajador y sucursal (por ejemplo almuerzo); valida solapamientos.
- `/api/v1/blocked-slots/` — bloqueos puntuales de la agenda de un trabajador.
- `/api/v1/bookings/` — agenda de la empresa (`bookings.read` / `bookings.write`); filtros `branch`, `worker`, `service`, `customer`, `status`, `date`, `date_from`, `date_to`, búsqueda por cliente/código y ordenamiento. El alta calcula el término desde la duración del servicio y valida que el inicio sea un cupo libre.
- `GET /api/v1/bookings/availability/?branch=&service=&worker=&date=` — cupos libres de un trabajador para un día local de la sucursal (paso de 15 minutos; considera turnos, pausas, bloqueos, ausencias y buffers).
- `POST /api/v1/bookings/{id}/confirm/`, `/cancel/`, `/complete/`, `/no-show/` y `/reschedule/` — comandos explícitos, auditados e idempotentes; `cancel` acepta `reason` y `reschedule` acepta `start_at`, `worker` y `reason`.
- `/api/v1/inventory/categories/`, `/inventory/products/`, `/inventory/warehouses/` y `/inventory/suppliers/` — catálogo de inventario (`inventory.read` / `inventory.write`); filtros `active`, `category` y `branch`, búsqueda y baja lógica.
- `/api/v1/inventory/movements/` — libro de movimientos de solo lectura; `POST` registra ingresos o salidas manuales (`kind` `entry`/`exit`) y actualiza el saldo en la misma transacción.
- `GET /api/v1/inventory/stock/` — saldos por bodega y producto con filtros `warehouse`, `product`, `below_reorder`, `positive` y búsqueda; `GET /inventory/stock/valuation/` agrupa cantidad y valor por bodega.
- `/api/v1/purchases/` — órdenes de compra (`purchases.read` / `purchases.write`) con líneas de producto; `POST {id}/submit/`, `/receive/` y `/cancel/` son comandos auditados. La recepción genera movimientos, actualiza el costo promedio y es idempotente.
- `/api/v1/inventory/transfers/` — transferencias entre bodegas con `POST {id}/dispatch/`, `/complete/` y `/cancel/`; el despacho descuenta el origen y la cancelación en tránsito devuelve el stock con movimientos de compensación.
- `/api/v1/inventory/stocktakes/` — conteos físicos por bodega; `POST {id}/complete/` compara lo contado con el saldo y genera ajustes solo cuando hay diferencia.
- `/api/v1/sales/` — ventas de productos y servicios (`sales.read` / `sales.write`); el alta queda en borrador, `POST {id}/complete/` registra los pagos, descuenta stock y completa la venta, y `POST {id}/cancel/` anula con compensación. Filtros `branch`, `customer`, `warehouse`, `status`, `date_from`, `date_to`.
- `/api/v1/cash-sessions/` — cajas por sucursal (`cash.read` / `cash.manage`); `POST` abre una caja y `POST {id}/close/` la concilia calculando esperado y diferencia. Solo puede existir una caja abierta por sucursal.
- `/api/v1/expenses/` — gastos con categoría, método de pago y sucursal (`expenses.read` / `expenses.write`); los gastos en efectivo requieren una caja abierta y `POST {id}/cancel/` los anula.
- `GET /api/v1/payments/` — pagos registrados (`payments.read`) con filtros `sale`, `cash_session`, `method`, `status` y fechas.
- `GET /api/v1/reports/sales-summary/` — informe de ventas completadas por rango de fechas y sucursal: totales, margen, métodos de pago, serie diaria, sucursales y productos/servicios más vendidos (`reports.read`).
- `GET /api/v1/reports/cash-summary/` — resumen de cajas y gastos del rango: apertura, ventas en efectivo, gastos, esperado, cierre y diferencia.
- `GET /api/v1/plans/` — planes activos públicos con sus funcionalidades y límites (sin autenticación), ordenados por posición y precio.
- `GET /api/v1/subscription/` — suscripción abierta de la empresa (`subscription.read`): plan, estado efectivo, días restantes y fechas del periodo.
- `POST /api/v1/subscription/change-plan/` — cambia el plan de la suscripción abierta (`subscription.manage`); `POST /subscription/cancel/` acepta `immediate` y `POST /subscription/resume/` revierte una cancelación programada.
- `GET /api/v1/subscription/payments/` y `/subscription/invoices/` — pagos y facturas de la empresa (`subscription.read`).
- `/api/v1/saas/plans/` — CRUD de planes con funcionalidades anidadas (solo `is_saas_admin`); un plan predeterminado excluye al anterior.
- `/api/v1/saas/subscriptions/` — listado, detalle y alta de suscripciones por empresa; `POST {id}/record-payment/`, `/change-plan/`, `/cancel/`, `/resume/` y `/expire/` son comandos auditados e idempotentes.
- `/api/v1/saas/payments/`, `/api/v1/saas/invoices/` y `/api/v1/saas/companies/` — lectura global con filtros por empresa, plan, suscripción y estado; `POST /saas/companies/{id}/change-status/` suspende o cierra una empresa.
- `GET /api/v1/saas/summary/` — métricas del panel: empresas por estado, suscripciones por estado efectivo, MRR, ingresos del mes y pruebas por vencer.
- `GET /api/v1/public/<slug>/` — perfil público de la empresa con sucursales, servicios y trabajadores activos (sin datos internos) y su bloque `branding`.
- `/b/<slug>/` — página pública de reservas con la marca de la empresa (logo, nombre, colores, fondo claro u oscuro y favicon). `/b/<slug>/reserva/<code>/` abre el detalle o la cancelación de una reserva existente. Consume los mismos endpoints públicos y no duplica la lógica de agenda.
- `/api/v1/public/<slug>/availability/` — disponibilidad pública por sucursal, servicio, trabajador y fecha.
- `POST /api/v1/public/<slug>/bookings/` — reserva pública con datos de contacto; reutiliza el cliente por correo, crea la reserva y envía confirmación.
- `GET /api/v1/public/<slug>/bookings/<code>/` y `POST .../cancel/` — consulta y cancelación en línea con el código público opaco.

### API móvil

- `GET /api/v1/mobile/bootstrap/` — perfil, empresa activa, membresía/rol, permisos efectivos, funcionalidades del plan, módulos habilitados, sucursales, suscripción y recursos sincronizables. Sigue disponible con suscripción vencida para permitir renovación; los módulos se informan apagados.
- `GET /api/v1/mobile/sync/<resource>/?since=<iso>` — sincronización incremental por `updated_at` (movimientos usan `created_at`) con paginación de 50 y cursor `next_since`. Recursos: `branches`, `services`, `workers`, `customers`, `bookings`, `products`, `warehouses`, `stock` y `movements`. Respeta permisos, funcionalidad del plan y aislamiento; un trabajador solo recibe sus propias reservas.
- `POST /api/v1/mobile/operations/` — lote `{ "operations": [{ "client_id": "<uuid>", "type": "...", "payload": {...} }] }` con `booking.create`, `booking.cancel`, `booking.reschedule` e `inventory.movement`. Devuelve por operación `applied`, `conflict` o `rejected` con `http_status`. `client_id` es idempotente por empresa; reutilizarlo con otro tipo responde `409`. Los conflictos de cupo/stock y los cruces de empresa se informan sin aplicar cambios.
- `GET|POST /api/v1/mobile/devices/` — lista o registra (upsert) la instalación actual con plataforma, token push, versión e idioma; `DELETE /api/v1/mobile/devices/<installation_id>/` la desactiva.
- `GET /api/v1/mobile/notifications/` — centro de notificaciones del usuario en la empresa con `unread_count` y filtro `unread=true`; `POST .../<id>/read/` marca una y `POST .../read-all/` todas. Dispositivos y notificaciones siguen accesibles con suscripción vencida.
- Push: los eventos de reserva (creada, confirmada, reprogramada, cancelada) y el stock bajo encolan `PushMessage` y se entregan después del commit con el proveedor `console` en desarrollo o un webhook/FCM configurable por variables de entorno.

Los listados están paginados (50 por página) y aceptan `search` y `ordering` cuando el recurso lo define. Las bajas de clientes, servicios, trabajadores y sucursales son lógicas (`active=false`) y quedan auditadas junto con altas y ediciones. El campo `company` nunca se acepta desde el cliente.

Cada sucursal define su zona horaria IANA (`America/Santiago` por defecto) y la disponibilidad se calcula en esa zona. La agenda usa turnos semanales, pausas, bloqueos puntuales, ausencias, buffers del servicio y reservas activas; los cupos se alinean cada 15 minutos. Crear o reprogramar toma un bloqueo por trabajador (`select_for_update`) y responde `409` si el cupo dejó de estar disponible. En SQLite el bloqueo no ofrece concurrencia real: la garantía estricta se activa al migrar a PostgreSQL. Las reservas guardan una instantánea del nombre, duración, precio y buffers del servicio para que cambios posteriores del catálogo no alteren el historial. La baja de reservas no existe: se cancelan con el comando correspondiente. El rol `worker` solo ve y agenda su propia agenda (`bookings.own.read` / `bookings.own.write`).

Las notificaciones se registran en `Notification` dentro de la misma transacción y se envían después del commit (`transaction.on_commit`). Si el envío falla, la notificación queda `failed` con el error. En local el correo se imprime en consola; configura un backend real para producción. El portal público está limitado a 30 solicitudes por minuto/IP y expone únicamente sucursales, servicios, trabajadores activos y códigos públicos de 10 caracteres.

El inventario usa un saldo por bodega y producto con costo promedio ponderado. `InventoryMovement` es append-only: no se edita ni se elimina; las correcciones se registran como movimientos de compensación. Las compras recibidas, transferencias y conteos escriben en ese libro, y el stock nunca queda negativo (una salida o despacho sin existencias responde `409`). Compras, transferencias y conteos usan estados y comandos idempotentes con auditoría; los documentos recibidos o conciliados no se cancelan. Las cantidades son decimales y los importes usan `Decimal`; la moneda operativa por empresa aún no se modela. El libro y los documentos son de solo lectura en la administración Django.

Las ventas nacen en borrador con líneas de producto o servicio y precio congelado por línea. Completar una venta exige que los pagos sumen exactamente el total, descuenta los productos del libro de inventario (`kind=sale`), guarda el costo promedio como costo de la línea y es idempotente. Anular una venta completada devuelve el stock con movimientos `sale_cancel` y marca los pagos como reembolsados; no se permite anular efectivo de una caja ya cerrada. Los pagos en efectivo requieren una caja abierta de la misma sucursal; tarjeta, transferencia y otros pueden registrarse sin caja. Cerrar una caja calcula el efectivo esperado (apertura + ventas en efectivo − gastos en efectivo) y guarda la diferencia contra el monto contado. Los gastos son inmutables salvo su anulación; los gastos y reembolsos que afectan una caja cerrada se rechazan con `409`. Los informes usan la zona horaria de la sucursal cuando se filtra por sucursal y `America/Santiago` en caso contrario.

La facturación SaaS es independiente de los datos de negocio. `Plan` define precio, moneda, periodo (`monthly`/`yearly`), días de prueba, plan predeterminado y `PlanFeature` con `enabled` y `limit_value`; no hay lógica por nombre de plan. Una empresa puede tener una sola suscripción abierta (constraint parcial). El estado efectivo se calcula en cada lectura: `trialing`, `active`, `past_due` (7 días de gracia tras el vencimiento), `expired` o `canceled`; cancelar al final del periodo conserva el acceso hasta el vencimiento y la cancelación inmediata lo corta. Registrar un pago extiende el periodo, emite una factura `FAC-000001` por empresa y reactiva la suscripción; una referencia repetida devuelve el mismo pago. Si la empresa nunca tuvo suscripción conserva acceso heredado (modo local); si tuvo suscripciones pero ninguna abierta, los módulos de negocio responden `402` y solo la facturación sigue disponible. Un módulo deshabilitado responde `403` y los límites de sucursales/trabajadores activos se validan al crear (`402`). El portal público también se oculta cuando la suscripción no está vigente o el plan no incluye reservas.

La primera propietaria inicia sesión con el endpoint de token y crea su contexto de empresa igual que otros usuarios. La cuenta SaaS se crea por el comando de administración/provisionamiento fuera del registro público; el endpoint público nunca permite otorgar `is_saas_admin`. En local, el correo de reset se imprime en la consola del servidor. Usa `DJANGO_EMAIL_BACKEND` y `DEFAULT_FROM_EMAIL` para conectar un backend real; producción falla al iniciar si continúa configurado el backend de consola.

Los tests se ejecutan con `DJANGO_TESTING=true python manage.py test` desde `backend/`. En PowerShell: `$env:DJANGO_TESTING="true"; python manage.py test`. La variable usa cache dummy durante la suite y evita que los throttles de peticiones afecten ejecuciones repetidas.

Enviar `Authorization: Bearer <access>` en las rutas protegidas. Para operaciones tenant-aware, enviar además `X-Tenant-Context: <uuid>` del contexto emitido por el servidor. La autenticación JWT valida usuario, vigencia, estado de empresa y membresía activa. Los viewsets tenant-scoped usan `TenantModelViewSet`, que filtra por empresa, aplica permisos por acción, audita cambios y asigna `company` desde el servidor.

## Estructura

- `backend/config`: configuración, rutas y despliegue ASGI/WSGI.
- `backend/apps/identity`: usuario y membresía/rol.
- `backend/apps/tenancy`: empresa, sucursal, resolución de tenant y base de API tenant.
- `backend/apps/audit`: eventos de auditoría de solo lectura.
- `backend/apps/customers`: clientes.
- `backend/apps/catalog`: catálogo de servicios.
- `backend/apps/workforce`: trabajadores, horarios y ausencias.
- `backend/apps/bookings`: reservas, disponibilidad, conflictos, comandos de agenda y portal público.
- `backend/apps/notifications`: registro y envío de correos transaccionales.
- `backend/apps/inventory`: catálogo, bodegas, proveedores, saldos, libro de movimientos, compras, transferencias y conteos.
- `backend/apps/sales`: ventas, pagos, cajas y gastos.
- `backend/apps/reports`: informes comerciales y de caja de solo lectura.
- `backend/apps/billing`: planes, funcionalidades, suscripciones, pagos, facturas, gating y panel superadmin SaaS.
- `backend/apps/mobile`: bootstrap, sincronización incremental, operaciones offline idempotentes, dispositivos, notificaciones y push.
- `mobile`: aplicación Flutter (agenda, inventario, alertas y perfil) con caché local, cola offline idempotente, conflictos visibles, tema dinámico por empresa y editor de marca para propietario/administrador.
- `backend/templates` y `backend/static/public`: plantilla, estilos y JavaScript de la página pública white-label de reservas.
- `docs/architecture.md`: arquitectura, entidades, permisos, API, diseño y fases.

## Configuración

Variables: `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_CORS_ORIGINS`, `AGENDA_USE_POSTGRES`, `DATABASE_URL`, `DJANGO_EMAIL_BACKEND`, `DEFAULT_FROM_EMAIL`, `AGENDA_PUSH_PROVIDER`, `AGENDA_PUSH_WEBHOOK_URL`, `AGENDA_PUSH_TOKEN`, `AGENDA_PUBLIC_BASE_URL`. PostgreSQL solo se activa con `AGENDA_USE_POSTGRES=true` y `DATABASE_URL`; instala el driver `psycopg[binary]` incluido en requirements cuando llegue la migración. `AGENDA_PUBLIC_BASE_URL` define la base absoluta del enlace público de reservas (por defecto `http://localhost:8000`). Los logos se guardan en `MEDIA_ROOT` y, en desarrollo, se sirven bajo `/media/`; en producción usa almacenamiento de objetos o el servidor web.
