# Arquitectura inicial

## 1. Arquitectura general

La primera entrega usa un monolito modular: Django REST Framework organiza dominios independientes en aplicaciones, con PostgreSQL como almacenamiento transaccional. Redis/Celery atenderán trabajos asíncronos (recordatorios, correo, tareas programadas). React/TypeScript será el cliente administrativo web; Flutter consume la misma API para el cliente móvil (Fases 7–8). Archivos se almacenarán fuera de la base de datos y se servirán mediante almacenamiento de objetos.

```text
Web React ─┐
Flutter ───┼── API REST Django ── PostgreSQL
Portal web ┘         ├─────────── Redis / Celery
                     ├─────────── almacenamiento de objetos
                     └─────────── correo / push
```

Se mantienen límites de dominio para que inventario, reservas o notificaciones puedan extraerse más adelante si hay una necesidad de escala medida.

## 2. Estructura de carpetas

```text
backend/config/                 configuración, API, ASGI/WSGI
backend/apps/identity/          usuarios, membresías, autenticación
backend/apps/tenancy/           empresas, sucursales y contexto tenant
backend/apps/audit/              eventos de auditoría
backend/apps/<dominio>/          aplicación modular por dominio
backend/templates/public/       página pública white-label de reservas
backend/static/public/          estilos y JavaScript de la página pública
web/                             cliente React + TypeScript (fase futura)
mobile/                          Flutter (Fases 7–8)
infra/                           Docker, despliegue y monitoreo
docs/                            decisiones y contratos
```

Cada app debe separar modelos, reglas de dominio, API/serializadores, permisos y tareas. Los módulos futuros son billing, workforce, customers, catalog, bookings, inventory, purchasing, sales, notifications y reporting.

## 3. Modelo de datos

Entidades iniciales: `User`, `Company`, `Membership`, `PermissionGrant`, `Branch`, `TenantContext`, `AuditEvent`. Implementadas en Fase 2: `Customer`, `Service`, `WorkerProfile`, `WorkingHours` y `TimeOff`, todas con `company` obligatorio. Implementadas en Fase 3: `Booking` (con instantánea de servicio, buffers y código público), `Notification` (outbox de correo), `Break` (pausa semanal) y `BlockedSlot` (bloqueo puntual). Implementadas en Fase 4: `Category`, `Product`, `Warehouse`, `Supplier`, `StockBalance`, `InventoryMovement`, `PurchaseOrder`, `PurchaseLine`, `Transfer`, `TransferLine`, `Stocktake` y `StocktakeLine`. Implementadas en Fase 5: `Sale`, `SaleLine`, `PaymentRecord`, `CashSession` y `Expense`. Implementadas en Fase 6: `Plan`, `PlanFeature`, `Subscription`, `Payment` e `Invoice`. Implementadas en Fase 7: `DeviceInstallation` (instalación y token push por empresa/usuario), `PushMessage` (outbox de notificaciones push) y `MobileOperation` (registro idempotente de operaciones offline por `client_id`).

Entidades siguientes:

- Operación/control: `ServiceConsumptionRule`.

Los identificadores son UUID en los agregados públicos principales. Fechas se guardan con zona horaria. Importes monetarios usan decimal y moneda explícita; cantidades usan decimal para admitir unidades fraccionables.

## 4. Relaciones

```text
Company 1──* Membership *──1 User
Company 1──* Branch 1──* Warehouse
Company 1──* Customer / WorkerProfile / Service / Product
Branch 1──* Booking *──1 Customer; Booking *──1 WorkerProfile y Service
Warehouse 1──* StockBalance *──1 Product
Product 1──* InventoryMovement
Sale 1──* SaleLine; PurchaseOrder 1──* PurchaseLine
Sale 1──* PaymentRecord *──0..1 CashSession
Branch 1──* CashSession 1──* Expense
Company 1──* Subscription *──1 Plan; Plan 1──* PlanFeature
```

Las entidades de negocio llevan `company_id`. Las operaciones ligadas a una sede también llevan `branch_id` y, para stock físico, `warehouse_id`. Se requieren claves únicas compuestas por tenant para SKU, códigos de sucursal y códigos públicos.

## 5. Aislamiento multiempresa

La primera versión usa tablas compartidas y `company_id` obligatorio, con índices y unicidad compuesta por empresa. El cliente nunca elige arbitrariamente el tenant por query/body. Primero lista empresas vinculadas por membresía; después solicita un contexto de tenant, que se emite con UUID opaco ligado al usuario, expira y solo se crea tras comprobar membresía activa y estado habilitado. Las solicitudes tenant-aware envían ese contexto; la autenticación JWT lo resuelve contra el usuario, membresía, vigencia y estado de empresa en cada solicitud. `TenantQuerysetMixin` falla cerrado y filtra todos los objetos por la empresa contextual. Al crear registros, el servidor asigna la empresa.

Además de scoping en la API, deben usarse constraints de base de datos y pruebas negativas de aislamiento. En producción se evaluará PostgreSQL Row-Level Security como defensa adicional. Las tareas de fondo deben recibir explícitamente `company_id`, validarlo y limpiar el contexto entre tareas. Acciones de soporte superadmin se auditan y no reutilizan el contexto de usuario de empresa.

## 6. Sistema de permisos

La autorización evalúa identidad, membresía activa, rol/permisos, alcance de sucursal y estado de suscripción/funcionalidad. Roles iniciales: owner, admin, manager, reception, worker, inventory, accounting. `PermissionGrant` permite allow/deny por membresía y sucursal; deny prevalece sobre permiso de rol. Sucursales y permisos tienen endpoints iniciales, con lectura limitada al tenant y escritura restringida. Los planes usarán `PlanFeature` con valores/límites editables, nunca constantes codificadas por nombre del plan.

## 7. Diseño de API

Prefijo versionado `/api/v1/`; REST JSON, JWT de vida corta y refresh rotativo, paginación/filtros, errores coherentes y esquema OpenAPI. Recursos previstos: `/auth`, `/companies/mine`, `/tenant-contexts`, `/branches`, `/customers`, `/workers`, `/services`, `/bookings`, `/inventory/products`, `/inventory/movements`, `/purchases`, `/sales`, `/cash-sessions`, `/expenses`, `/payments`, `/reports`, `/subscriptions`. Las reservas exponen además `/bookings/availability/` y acciones explícitas de estado, y el portal público vive bajo `/public/<company-slug>/`.

Comandos que cambian estado (confirmar reserva, recibir compra, completar venta, conciliar conteo) serán operaciones explícitas, transaccionales, autorizadas e idempotentes. Disponibilidad se protege contra carreras con transacción y bloqueo por trabajador; en PostgreSQL se evaluará además una restricción de exclusión por rango. Los movimientos de inventario son append-only y los errores se compensan con movimientos enlazados. Las notificaciones usan un registro persistente y envío posterior al commit.

## 8. Diseño visual

Tema oscuro: `#090909` fondo, `#151515` superficie, `#252525` bordes/superficie elevada, `#E50914` acción principal y `#8B0000` estados de error/énfasis; blanco para contenido primario y `#A0A0A0` para secundario. Sidebar compacta, navegación por rol, resúmenes de operación, tablas densas legibles, calendario claro, estados con texto además de color y diseño adaptable. Animaciones breves y respetuosas con reducción de movimiento.

## 9. Plan de implementación

1. Fundamentos: estructura, configuración, identidad, tenant, membresía, RBAC, admin y auditoría.
2. Gestión empresarial: empresas, sucursales, trabajadores, clientes, servicios y disponibilidad.
3. Agendamiento: calendario, conflictos, portal público, cambios y notificaciones.
4. Inventario: catálogo, bodegas, libro de movimientos, proveedores/compras, transferencias, conteos y valorización.
5. Comercial: ventas, caja, pagos, gastos e informes.
6. SaaS: planes configurables, periodos de prueba, pagos, ciclo de vida y límites por función.
7. Móvil: perfiles, agenda, inventario, sincronización y push.
8. Lanzamiento: seguridad, aislamiento, concurrencia, backups, observabilidad, rendimiento y despliegue.

Cada fase debe completar reglas de dominio, migraciones, documentación de API y verificación de sus flujos antes de ampliar el alcance.

## Estado de Fase 1

Implementado: usuario email/JWT, empresa, membresía y roles iniciales, permisos allow/deny, sucursales, contextos tenant con expiración, endpoints iniciales, administración Django y auditoría de solo lectura. Las pruebas cubren tenant no autorizado, contexto expirado, membresía revocada, empresa suspendida, filtrado de sucursales y asignación de `company` por servidor.

Fase 1 completada para desarrollo local: el alta crea empresa y propietario en una transacción; recuperación de contraseña es opaca, firmada, expira y se invalida al usarse; login y recuperación tienen límites por IP; logout invalida refresh token; desactivar una cuenta invalida sesiones; administración limita datos por rol/empresa; auditoría es de solo lectura; SQLite queda como base predeterminada y no cambia a PostgreSQL hasta activar expresamente `AGENDA_USE_POSTGRES=true`.

Antes de producción quedan decisiones operativas: configurar proveedor real de correo y secretos, revisar política de retención de auditoría, añadir logging/monitoreo y copias de seguridad, y planificar la migración PostgreSQL con RLS. La suite actual valida los flujos de Fase 1 y aislamiento base; pruebas de penetración y revisión de seguridad independiente siguen siendo trabajo de lanzamiento.

## Estado de Fase 2

Implementado: clientes, catálogo de servicios (duración, precio, buffers y disponibilidad por sucursal), trabajadores con vínculo opcional a membresía, turnos semanales por sucursal y ausencias. Los recursos usan `TenantModelViewSet`: filtrado por empresa, permisos por acción (`customers.*`, `catalog.*`, `workforce.*`, `branches.read/manage`), paginación de 50, búsqueda, ordenamiento, baja lógica para clientes/servicios/trabajadores/sucursales y auditoría de altas, ediciones y desactivaciones. Los serializers rechazan `company` del cliente y validan que sucursales, membresías y trabajadores pertenezcan a la empresa activa. Los turnos se validan contra solapamientos en la misma sucursal, día y trabajador.

La Fase 3 resolvió las reglas de disponibilidad combinadas, la zona horaria por sucursal y el bloqueo transaccional por trabajador. Las excepciones de horario por fecha y la concurrencia real en PostgreSQL quedan para lanzamiento; la migración a PostgreSQL sigue diferida por decisión de producto y el volumen esperado de SQLite es solo de desarrollo.

## Estado de Fase 3

Implementado: `Branch.timezone` (IANA validada, `America/Santiago` por defecto); `Booking` con `branch`, `customer`, `service`, `worker`, rango visible, bloque con buffers, estado, origen, código público, campos de cancelación y autor, más instantánea de nombre, duración, precio y buffers del servicio. Restricciones de base de datos aseguran `end_at > start_at` y coherencia de los buffers.

Disponibilidad: el motor combina turnos semanales de la sucursal, pausas recurrentes (`Break`), bloqueos puntuales (`BlockedSlot`), ausencias (`TimeOff` con o sin sucursal), reservas activas y buffers del servicio. Los cupos se generan cada 15 minutos en la zona horaria de la sucursal, respetan el ajuste horario y excluyen horas pasadas. El portal público y la agenda interna usan el mismo cálculo.

Conflictos y comandos: crear y reprogramar se ejecutan en transacción con `select_for_update` sobre el trabajador, recalculan disponibilidad, rechazan inicios fuera de cupo, solapamientos con buffers o ausencias (`409`) y registran auditoría. Confirmar, cancelar, completar y marcar inasistencia son acciones explícitas e idempotentes sobre estados válidos; no se eliminan reservas. Reprogramar conserva la instantánea del servicio y notifica el cambio.

API y permisos: `/api/v1/bookings/` con filtros por sucursal, trabajador, servicio, cliente, estado y fechas locales; `/availability/`; acciones `confirm`, `cancel`, `complete`, `no-show` y `reschedule`. El rol `worker` queda limitado a su propia agenda y disponibilidad mediante `bookings.own.read` / `bookings.own.write`. El portal público `GET /api/v1/public/<slug>/`, `.../availability/`, `POST .../bookings/`, consulta y cancelación por código opaco está limitado a empresas activas o en prueba, no expone correos internos y usa throttle de 30 solicitudes por minuto/IP.

Notificaciones: `Notification` registra destinatario, asunto, cuerpo, estado y error. El registro se crea en la transacción de la reserva y el envío ocurre en `transaction.on_commit`; una falla deja el registro en `failed` sin revertir la reserva. En desarrollo el correo se imprime en consola; envío asíncrono con reintentos, recordatorios y Celery quedan para lanzamiento.

Concurrencia: `select_for_update` serializa reservas por trabajador en PostgreSQL. SQLite, al ser la base local, no ofrece esa garantía real de concurrencia; antes de producción se debe migrar a PostgreSQL y evaluar una restricción de exclusión por rango para defensa adicional. También quedan pendientes: relación explícita trabajador-servicio, excepciones de horario por fecha, reprogramación en lote, recordatorios, y las interfaces web/móvil.

## Estado de Fase 4

Implementado: catálogo de inventario (`Category`, `Product` con SKU único por empresa, unidad, costo, precio, punto de recompra y código de barras), `Warehouse` opcionalmente ligada a sucursal, `Supplier` y saldos `StockBalance` por bodega y producto con costo promedio ponderado. Los recursos usan `TenantModelViewSet`, permisos `inventory.*` / `purchases.*`, paginación de 50, búsqueda, ordenamiento, baja lógica de catálogo/proveedores/bodegas y auditoría.

Libro de movimientos: `InventoryMovement` es append-only (sin endpoints de edición o borrado; el modelo rechaza `save` sobre registros existentes y `delete`). Cada movimiento guarda bodega, producto, tipo, dirección, cantidad, costo unitario, saldo posterior, referencia y actor. Los ingresos recalculan el costo promedio ponderado; las salidas usan el costo promedio vigente y fallan con `409` si el saldo es insuficiente. Las correcciones se hacen con movimientos compensatorios.

Compras: `PurchaseOrder` y `PurchaseLine` con estados borrador, pedida, recibida y cancelada. `submit`, `receive` y `cancel` son comandos explícitos, transaccionales e idempotentes; la recepción completa genera movimientos `purchase_receipt`, actualiza el costo de referencia del producto y no admite doble recepción. Solo los borradores se editan y las líneas quedan fijas tras crearse.

Transferencias: `Transfer` y `TransferLine` entre bodegas distintas de la misma empresa. `dispatch` descuenta el origen y fija el costo de cada línea; `complete` ingresa en destino con ese costo; `cancel` compensa el origen si estaba en tránsito y no se permite sobre una transferencia completada. El despacho es atómico: si una línea no tiene stock, no se aplica ninguna.

Conteos y valorización: `Stocktake` y `StocktakeLine` registran cantidades contadas por bodega; `complete` calcula el saldo esperado, guarda la diferencia y genera un movimiento `stocktake` solo cuando difiere. `GET /api/v1/inventory/stock/valuation/` agrupa cantidad y valor por bodega, y `/inventory/stock/` filtra por bodega, producto, bajo punto de recompra y saldo positivo. Los documentos se leen en Django admin y no se editan allí.

Aislamiento y concurrencia: todos los querysets filtran por empresa y los serializers/servicios validan que bodegas, productos, proveedores y líneas pertenezcan al tenant activo. Los saldos se actualizan con `select_for_update` dentro de la transacción y las líneas se procesan ordenadas por producto para reducir bloqueos cruzados. En SQLite la concurrencia real sigue siendo limitada; PostgreSQL es el destino antes de producción. Quedan pendientes: recepciones parciales, devoluciones a proveedor, facturas de compra, conversión de unidades, multi-moneda, exportaciones de reportes y las interfaces web/móvil.

## Estado de Fase 5

Implementado: ventas (`Sale`, `SaleLine`) con líneas de producto o servicio, precio unitario por línea (por defecto el del catálogo), instantánea de nombre/SKU y descuento global. Toda venta nace en borrador; solo los borradores se editan y las líneas quedan fijas tras el alta. Completar una venta exige que los pagos sumen exactamente el total, registra `PaymentRecord` por método (`cash`, `card`, `transfer`, `other`) y descuenta los productos del libro de inventario con movimientos `kind=sale`, guardando el costo promedio ponderado como costo de la línea. La operación es transaccional e idempotente: sin stock suficiente responde `409` sin dejar pagos ni cambios parciales. Anular una venta completada devuelve el stock con movimientos `sale_cancel`, marca los pagos como `refunded` y audita el motivo; una venta en efectivo cuya caja ya cerró no se puede anular.

Caja: `CashSession` por sucursal con apertura, cierre, monto esperado y diferencia. Solo puede existir una caja abierta por sucursal (constraint parcial). Los pagos en efectivo y los gastos en efectivo requieren una caja abierta de la misma sucursal y se serializan contra el cierre con `select_for_update`. Al cerrar se calcula `esperado = apertura + ventas en efectivo − gastos en efectivo` y se guarda el monto contado y la diferencia. Pagos y gastos en efectivo de una caja cerrada se rechazan con `409`; los métodos no efectivos no requieren caja.

Gastos: `Expense` con número, sucursal, categoría, método, referencia y fecha de imputación. Es inmutable salvo su anulación; los gastos en efectivo quedan ligados a la caja y se excluyen del esperado cuando se anulan. Los pagos y gastos se leen en Django admin sin edición.

Informes: `GET /api/v1/reports/sales-summary/` y `GET /api/v1/reports/cash-summary/` aceptan `date_from`, `date_to` y `branch`. El resumen de ventas devuelve cantidad, subtotal, descuentos, total, cobrado, costo, utilidad, margen, ticket promedio, métodos de pago, serie diaria, desglose por sucursal y top de productos/servicios. El resumen de caja devuelve aperturas, ventas y gastos en efectivo, esperado, cierre, diferencia y gastos por categoría/método. Los límites de fecha se interpretan en la zona horaria de la sucursal filtrada o en `America/Santiago`; ventas anuladas y pagos reembolsados no cuentan.

Permisos: `sales.read/write`, `cash.read/manage`, `payments.read`, `expenses.read/write` y `reports.read`. Recepción y gerencia pueden vender y operar caja; contabilidad lee ventas/cajas/pagos, gestiona gastos y accede a informes; inventario y trabajador no acceden al módulo comercial. Los grants allow/deny por membresía y sucursal siguen prevaleciendo sobre el rol; un deny global aplica también cuando la petición incluye una sucursal. Aislamiento: ramas, clientes, bodegas, productos, servicios, cajas y ventas externas se rechazan en escritura y devuelven `404` en lectura. En SQLite la concurrencia real es limitada; PostgreSQL es el destino antes de producción.

Quedan pendientes: notas de crédito y devoluciones parciales por línea, propinas, impuestos y documentos fiscales, descuentos por línea/cupones, pasarelas de pago, movimientos manuales de caja (retiros/ingresos), arqueos por turno/terminal, multi-moneda, exportación de informes, reportes asíncronos, consumo automático de inventario por servicio (`ServiceConsumptionRule`) y las interfaces web/móvil.

## Estado de Fase 6

Implementado: `Plan` (código único, nombre, descripción, precio decimal, moneda, periodo mensual/anual, días de prueba, activo, predeterminado y posición), `PlanFeature` (códigos bookings, customers, catalog, workforce, inventory, sales, reports, branches y workers; `enabled` y `limit_value`), `Subscription` (estados trialing, active, past_due, expired y canceled), `Payment` (efectivo, transferencia, tarjeta u otro; completado o reembolsado) e `Invoice` con número `FAC-000001` por empresa. Los valores y límites son datos editables: no existe lógica por nombre de plan. Un constraint parcial garantiza un solo plan predeterminado y otro una sola suscripción abierta por empresa; las referencias de pago no vacías son únicas por empresa y la secuencia/número de factura también.

Ciclo de vida: el estado efectivo se calcula en cada lectura. La prueba vence en `trial_ends_at`; tras el vencimiento del periodo hay 7 días de gracia en `past_due` y luego `expired`. Cancelar sin `immediate` marca `cancel_at_period_end` y conserva el acceso hasta el final del periodo; la cancelación inmediata fija `ended_at` y corta el acceso. Registrar un pago extiende el periodo desde el fin vigente (o desde ahora si venció), emite la factura, reactiva la suscripción y quita la cancelación programada; repetir la misma referencia devuelve el pago existente. Cambiar de plan no prorratea: aplica el nuevo plan al periodo en curso. `expire` permite a operaciones cerrar una suscripción manualmente. Todas las transiciones son atómicas, bloquean empresa/suscripción/plan y quedan auditadas.

Gating y límites: la autorización tenant evalúa la suscripción después de resolver el permiso. Con suscripción usable, un módulo mapeado a una funcionalidad deshabilitada responde `403`; sin suscripción abierta pero con historial responde `402`; si la empresa nunca tuvo suscripción conserva el acceso heredado para no romper datos locales. Las rutas `subscription.*` siempre siguen disponibles para consultar o pagar. Los límites numéricos (`branches`, `workers`) se validan solo al crear y cuentan registros activos; actualizar no se bloquea. El alta pública de empresa inicia una prueba con el plan predeterminado si existe. El portal público devuelve `404` cuando la suscripción no es usable o el plan no incluye reservas.

API: `/api/v1/plans/` es público y devuelve solo planes activos. `/api/v1/subscription/` (lectura), `/subscription/change-plan/`, `/subscription/cancel/`, `/subscription/resume/`, `/subscription/payments/` y `/subscription/invoices/` operan sobre la empresa del contexto. El panel superadmin vive bajo `/api/v1/saas/`: CRUD de planes con funcionalidades anidadas, listado/alta de suscripciones, comandos `record-payment`, `change-plan`, `cancel`, `resume` y `expire`, lectura global de pagos, facturas y empresas con filtros, cambio de estado de empresa y `/saas/summary/` con empresas por estado, suscripciones por estado efectivo, MRR por moneda, ingresos del mes y pruebas por vencer. Todo el panel exige `is_saas_admin` o superusuario.

Aislamiento: cada consulta tenant filtra por `company` desde el contexto emitido por el servidor; la empresa nunca se acepta desde el cuerpo. Pagos y facturas externos devuelven `404` en lectura. Las acciones superadmin auditan empresa/plan/suscripción afectada y no reutilizan contexto de empresa. Los roles manager y accounting incluyen `subscription.read`; `subscription.manage` queda para propietario/administrador. La suite suma 22 pruebas de facturación (ciclo de vida, gracia, facturas, idempotencia, gating, límites, portal, panel superadmin y aislamiento); el total del backend es 141 pruebas.

Pendientes: pasarela de pago y webhooks, cobro automático/reintentos (dunning), prorrateo al cambiar de plan, impuestos y documentos fiscales, PDF de facturas, recordatorios de vencimiento y tareas programadas para expirar suscripciones, cupones, multi-moneda operativa, historial de cambios de plan y las interfaces web/móvil del panel SaaS.

## Estado de Fase 7

Bootstrap: `GET /api/v1/mobile/bootstrap/` devuelve usuario, empresa activa, membresía/rol, permisos globales efectivos, funcionalidades y límites del plan, módulos habilitados, sucursales, suscripción, estado de facturación y recursos sincronizables. Los permisos se calculan con el rol y los grants globales allow/deny; las restricciones por sucursal se siguen validando en cada petición. Sin suscripción abierta el bootstrap responde igual con `billing_state=inactive` y los módulos apagados, para que la app pueda mostrar el estado y renovar.

Sincronización: `GET /api/v1/mobile/sync/<resource>/?since=<iso>` entrega cambios incrementales por `updated_at` (los movimientos usan `created_at`), orden estable por cursor e `id`, paginación de 50 y `next_since` como nuevo cursor. El registro `SYNC_REGISTRY` declara modelo, serializer, permisos, funcionalidad del plan y relaciones a precargar. Recursos: sucursales, servicios, trabajadores, clientes, reservas, productos, bodegas, saldos y movimientos. Los trabajadores reciben solo sus reservas (`bookings.own.read`). Un recurso desconocido responde `404` y un cursor inválido `400`.

Operaciones offline: `POST /api/v1/mobile/operations/` acepta un lote de hasta 50 operaciones con `client_id` UUID, tipo y payload. Tipos: `booking.create`, `booking.cancel`, `booking.reschedule` e `inventory.movement`. Cada operación se ejecuta con los servicios transaccionales existentes y devuelve `applied`, `conflict` (cupo ocupado, stock insuficiente, reserva desactualizada o estado inválido) o `rejected` (validación, permisos, empresa ajena o facturación). El resultado incluye `http_status` y `data` u `error.detail`. `MobileOperation` registra el resultado por empresa y `client_id`; repetir la misma operación devuelve la respuesta original y reutilizar el `client_id` con otro tipo responde `409`. Las reservas de otra empresa devuelven `404`, los trabajadores solo operan sobre su propio perfil y la reprogramación acepta `expected_start_at` para detectar ediciones concurrentes.

Dispositivos y notificaciones: `DeviceInstallation` es única por empresa, usuario e `installation_id` y guarda plataforma, token push, versión, idioma, actividad y última conexión. `POST /api/v1/mobile/devices/` hace upsert y `DELETE .../<installation_id>/` desactiva. `PushMessage` es el outbox de notificaciones del centro de la app; `GET /api/v1/mobile/notifications/` lista con `unread_count`, `POST .../<id>/read/` marca una y `POST .../read-all/` todas. Las consultas filtran por empresa y usuario; mensajes de otra empresa devuelven `404`. Dispositivos y notificaciones no pasan por el gating de suscripción para no perder el canal de renovación.

Push: crear, confirmar, reprogramar o cancelar una reserva encola mensajes para el trabajador vinculado y para quien la creó; un movimiento de inventario que deja el saldo en o bajo el punto de recompra encola avisos para miembros activos con `inventory.write`. La entrega ocurre en `transaction.on_commit`; sin dispositivos activos con token el mensaje queda `skipped`, con proveedor `console` (desarrollo) queda `sent` en log, y con `AGENDA_PUSH_PROVIDER=webhook|fcm` se envía por HTTP a `AGENDA_PUSH_WEBHOOK_URL` con `AGENDA_PUSH_TOKEN` opcional. Un fallo del proveedor marca `failed` sin romper la transacción de negocio.

App Flutter: `mobile/` implementa el cliente con Material 3 oscuro (negro/rojo), Provider y `AppState`. Cuatro pestañas: Agenda (reservas por día con filtros, alta, detalle, cancelación y reprogramación), Inventario (saldo por producto, filtro bajo mínimo, historial y movimientos de entrada/salida), Alertas (dispositivo, notificaciones con lectura individual o total, cola offline) y Perfil (identidad, empresa, suscripción, módulos, permisos efectivos, sincronización y cierre de sesión). La caché tipada vive en Sembast (IndexedDB en web) y la cola persistente reutiliza los `client_id` del backend. Cada operación se encola primero y el reintento se envía antes de sincronizar recursos, de modo que el saldo o la reserva reflejen el cambio aplicado; los conflictos quedan visibles con mensaje del servidor, reintento y descarte. El dispositivo se registra en el arranque y el acceso tolera sesión vencida, sin conexión y empresa única o múltiple. El backend habilita CORS con `DJANGO_CORS_ORIGINS` (todos los orígenes solo con `DEBUG=true`) y admite la cabecera `X-Tenant-Context` en el preflight.

Aislamiento y verificación: toda consulta móvil filtra por `company` desde el contexto emitido por el servidor; ids externos en payloads se resuelven con el filtro de empresa. La suite móvil suma 37 pruebas (bootstrap, permisos efectivos, sincronización incremental y aislamiento, operaciones idempotentes/conflictos, trabajador propio, dispositivos, centro de notificaciones, push y CORS). La app Flutter suma 23 pruebas (almacén local, cola offline, modelos, acceso, orden de sincronización, marca y tema) y el analizador no reporta problemas. Quedan pendientes: push nativo con credenciales FCM/APNs, build y firma para tiendas, notificaciones de escritorio/web, programación de recordatorios y limpieza de tokens inválidos.

## Estado de Fase 8

Marca blanca: `Company` incorpora `display_name` (nombre visible opcional), `logo`, `primary_color`, `secondary_color` y `theme_mode` (`light` u `dark`, claro por defecto). Los colores se validan como `#RRGGBB`; el `slug` se normaliza a minúsculas, es único entre empresas y rechaza identificadores reservados por la plataforma (`admin`, `api`, `b`, `public`, `static`, entre otros). No se creó una tabla de marca separada: la identidad vive en la empresa y conserva el aislamiento tenant existente. La migración `0005_company_theme_mode` deja en claro las empresas existentes.

API: `GET|PATCH /api/v1/company/branding/` lee o actualiza `display_name`, `slug`, `primary_color`, `secondary_color` y `theme_mode`; la lectura requiere membresía activa y la escritura `company.manage` (propietario/administrador). Un `theme_mode` fuera de `light`/`dark` responde `400`. `POST|DELETE /api/v1/company/branding/logo/` sube o elimina el logo con límite de 2 MB, dimensiones máximas de 4000 × 4000 px y formatos PNG, JPEG o WebP; SVG se rechaza. Cada cambio audita `company.branding_updated`. El bloque de marca (`display_name`, `logo_url`, `primary_color`, `secondary_color`, `theme_mode`, `booking_url`) se propaga a `companies/mine`, al bootstrap móvil, a la lista de empresas del bootstrap y al perfil público.

Página pública: `/b/<slug>/` y `/b/<slug>/reserva/<code>/` renderizan una página Django con la marca de la empresa (logo, favicon, nombre, variables CSS de color y `data-theme` claro u oscuro), formulario por pasos y enlace profundo a una reserva existente. El fondo claro usa blanco, superficies `#F6F6F8`, bordes `#E4E4E9` y texto `#121317`; el oscuro conserva `#090909`/`#151515`/`#252525` y texto blanco. Consume los mismos endpoints públicos de perfil, disponibilidad, alta, detalle y cancelación; no duplica reglas de agenda. El HTML incluye una primera representación de servicios para funcionar sin JavaScript y el JS usa `textContent` para evitar inyección. `AGENDA_PUBLIC_BASE_URL` construye el enlace absoluto y, en desarrollo, los logos se sirven desde `/media/`; en producción deben ir a almacenamiento de objetos.

Flutter: `Branding` normaliza nombre, logo, colores y `theme_mode` desde la empresa activa (claro por defecto); `buildAgendaTheme(branding)` construye un `ColorScheme` claro u oscuro, registra la extensión `AgendaPalette` y fija `scaffoldBackgroundColor`, textos, tarjetas, entradas, navegación y snackbars sobre esa paleta, y `MaterialApp` se reconstruye al cambiar de empresa. Las pantallas leen `context.palette` para fondos, superficies, bordes, texto secundario y contenido, en lugar de colores fijos. El selector de empresa y el perfil muestran logo y nombre visibles; el perfil expone el enlace público con acción de copiado. Los colores de marca se aplican a acentos, indicadores y botones, mientras el rojo semántico se conserva para errores, conflictos y stock bajo.

Editor en la app: el perfil muestra **Editar marca** solo con `company.manage`. La pantalla `BrandingScreen` edita nombre visible, identificador público, colores con presets y fondo Claro/Oscuro, con vista previa en vivo independiente del tema actual de la app; valida formato `#RRGGBB`, longitud y reglas del slug, y advierte con el nuevo enlace cuando el identificador cambia. El logo se elige con `image_picker` y se valida en el cliente (PNG/JPEG/WebP, máximo 2 MB) antes de subirlo. Guardar exige conexión, usa `PATCH /company/branding/` o las rutas de logo, muestra el mensaje del backend si falla y recarga el bootstrap para que el tema y la identidad se actualicen en toda la app. `ApiClient` incorpora `patchMap`, `postMultipart` y `deleteMap`; los tests cubren encabezados, errores de validación, subida multipart y eliminación.

Verificación: 14 pruebas backend de marca y página pública (modelo/API/aislamiento, validación de `theme_mode` y propagación a la página) y 50 pruebas Flutter, incluidas 14 del editor de marca, 4 de `ApiClient` y 2 del acceso desde el perfil; `flutter analyze` no reporta problemas. Quedan pendientes: CDN o almacenamiento de objetos para logos, dominios personalizados con TLS, marca por sucursal y plantillas de correo con la identidad de cada empresa.
