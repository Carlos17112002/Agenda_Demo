# Calendario de agenda — especificación de diseño

- Fecha: 2026-11-11
- Estado: aprobado en conversación, pendiente de plan de implementación
- Clientes: `mobile/` (Semana, Día y Lista) y `web/` (Día y Semana)
- Complementa: `docs/superpowers/specs/2026-11-11-web-admin-operador-design.md`
- Plan: `docs/superpowers/plans/2026-11-11-agenda-calendario.md`

## 1. Contexto y objetivo

La agenda actual muestra reservas como una lista agrupada por día. Eso sirve para
revisar pendientes, pero no permite ver la ocupación real de la semana ni detectar
huecos de un vistazo. El operador necesita una vista de calendario con días y horas,
similar a la agenda de escritorio, también en el teléfono.

El objetivo es agregar a Flutter las vistas **Semana**, **Día** y **Lista**, y
completar la vista semanal de la web con eje horario. Las reservas se muestran en la
zona horaria de la sucursal, el rango de horas sale del horario de atención y se puede
crear una reserva tocando un hueco libre.

## 2. Decisiones aprobadas

| Tema | Decisión |
| --- | --- |
| Vistas Flutter | Semana, Día y Lista |
| Vistas web | Día y Semana (sin Lista) |
| Rango horario | Primera–última hora de atención de la sucursal; respaldo 08:00–20:00 |
| Interacciones | Detalle al tocar, crear desde hueco, filtro por sucursal y por trabajador |
| Zona horaria | La de la sucursal seleccionada; las reservas se guardan en UTC |
| Datos | Reservas por rango, horarios de trabajo y sucursales |
| Offline | Lectura desde caché; creación/cancelación/reprogramación usan la cola existente |

## 3. Alcance

### Incluido

1. Vista Semana en Flutter: 7 columnas de día, eje horario, desplazamiento horizontal.
2. Vista Día en Flutter: columnas por trabajador con eje horario.
3. Vista Lista: la agrupación actual por día, con filtros de sucursal y trabajador.
4. Filtros por sucursal y trabajador en las tres vistas.
5. Navegación anterior/siguiente/hoy y selección de fecha.
6. Detalle de reserva al tocar una tarjeta.
7. Crear reserva desde un hueco: abre el formulario con fecha, hora y sucursal
   preseleccionadas; si la columna es de un trabajador, también lo preselecciona.
8. Rango horario calculado desde `working-hours` y respaldo 08:00–20:00.
9. Zona horaria por sucursal con manejo de horario de verano.
10. Recurso de sincronización `working-hours` para que el calendario funcione offline.
11. Extensión de la web: eje horario en la vista semanal, rango desde horarios y alta
    desde hueco.
12. Pruebas unitarias, de widget, de integración y end-to-end.

### Fuera de alcance

- Arrastrar y soltar reservas para reprogramar.
- Redimensionar reservas desde el calendario.
- Vista mensual o anual.
- Disponibilidad offline calculada en el dispositivo.
- Notificaciones en tiempo real o WebSocket.
- Edición de horarios desde el calendario.
- Cambios al motor de disponibilidad o a la duración de las reservas.
- Lista en la web.

## 4. Vistas e interacciones

### 4.1 Semana (Flutter)

Estructura:

```text
┌──────────────────────────────────────────────────────────────┐
│ Agenda   [Semana] [Día] [Lista]        ◀  Hoy  ▶   Sucursal ▾ │
│ Responsable ▾                                                  │
├──────┬────────┬────────┬────────┬────────┬────────┬────────┬───┤
│ Hora │ Lun 10 │ Mar 11 │ Mié 12 │ Jue 13 │ Vie 14 │ Sáb 15 │Dom│
├──────┼────────┼────────┼────────┼────────┼────────┼────────┼───┤
│ 08   │        │ ██████ │        │        │ ██████ │        │   │
│ 09   │ ██████ │        │ ██████ │        │        │        │   │
│ ...  │        │        │        │        │        │        │   │
└──────┴────────┴────────┴────────┴────────┴────────┴────────┴───┘
```

- La semana empieza el lunes y termina el domingo, calculada en la zona de la sucursal.
- El eje horario queda fijo a la izquierda; los 7 días se desplazan horizontalmente.
- Cada hora mide 64 px; cada día mide 160 px de ancho.
- Las reservas se posicionan por hora y duración; una reserva de 30 minutos mide 32 px
  y una de 60 minutos 64 px. Altura mínima 28 px para que el texto sea legible.
- Una reserva que cruza dos días se recorta al día visible; el detalle muestra el
  rango completo.
- Reservas solapadas del mismo día se dibujan una al lado de la otra si hay espacio;
  si no, se apilan con un desplazamiento horizontal de 8 px y borde de color.
- El encabezado de cada día muestra el nombre corto y el número; el día actual se
  resalta con el color primario.
- Un día sin horario de atención muestra el rótulo `Cerrado` sobre la columna, pero
  conserva la grilla de respaldo para ver reservas excepcionales.

### 4.2 Día (Flutter)

- Una columna por trabajador activo de la sucursal seleccionada.
- Si hay filtro de trabajador, se muestra solo esa columna.
- Si no hay trabajadores sincronizados, una columna `Agenda` con todas las reservas.
- Eje horario fijo a la izquierda; columnas desplazables horizontalmente.
- Cada columna tiene 200 px de ancho y el mismo alto por hora que la semana.
- La cabecera muestra nombre y color del trabajador.
- Un trabajador sin horario ese día muestra `Sin horario` bajo su nombre.
- El rango horario del día se calcula con los horarios de los trabajadores visibles;
  si no hay datos, 08:00–20:00.

### 4.3 Lista (Flutter)

- Conserva la agrupación por día y las tarjetas actuales.
- Filtros rápidos `Próximas`, `Hoy`, `Todas`, más sucursal y trabajador.
- El agrupamiento usa la fecha local de la sucursal, no la del dispositivo.
- Es la vista de respaldo cuando no hay datos de horario o el espacio es reducido.

### 4.4 Filtros

- **Sucursal**: obligatoria. Por defecto la primera sucursal activa del bootstrap. Si el
  usuario cambia de sucursal, se recalculan rango, días y reservas.
- **Trabajador**: opcional. `Todos` por defecto. Si el rol es trabajador, queda fijo en
  su propio perfil y no se muestra el selector.
- El filtro de trabajador también filtra el rango horario: se usan sus turnos.
- Los filtros se conservan al cambiar de vista dentro de la sesión.
- Cambiar de empresa reinicia filtros, fecha y vista a los valores por defecto.

### 4.5 Navegación temporal

- Botones `◀` y `▶`: en Semana avanza 7 días; en Día avanza 1 día; en Lista no se
  muestran (la lista usa sus filtros).
- `Hoy` vuelve a la fecha actual en la zona de la sucursal.
- El título muestra el rango: `10–16 de noviembre` o `miércoles 12 de noviembre`.
- La fecha se conserva al cambiar entre Semana y Día.

### 4.6 Detalle y creación desde hueco

- Tocar una tarjeta abre el detalle existente (`_BookingDetailSheet`) con acciones de
  cancelar y reprogramar según permisos.
- Tocar un espacio vacío de la grilla calcula la hora con el desplazamiento vertical,
  redondea a bloques de 15 minutos y abre el formulario de creación con:
  - sucursal seleccionada;
  - fecha del día tocado;
  - hora calculada;
  - trabajador de la columna, si aplica.
- El formulario es el mismo `_CreateBookingSheet`; el usuario elige servicio y cliente.
- Si está sin conexión, la reserva se encola como `booking.create` y aparece al
  sincronizar. El servidor sigue siendo la autoridad y puede devolver conflicto; el
  conflicto se muestra desde la cola como hoy.
- Si está en línea, el flujo actual no consulta disponibilidad en móvil: el servidor
  valida al crear. La web sí usa disponibilidad antes de enviar.

## 5. Tiempo y rango horario

### 5.1 Zona horaria

- Las reservas llegan en UTC (`start_at`, `end_at`) y se convierten a la zona IANA de la
  sucursal (`branches[].timezone`, por defecto `America/Santiago`).
- La semana y el día se calculan en esa zona, no en la del dispositivo.
- Se usa el paquete `timezone` con `initializeTimeZones()`. Las conversiones se hacen
  con `TZDateTime.from(utc, location)` y `TZDateTime(location, y, m, d, h, min)`.
- El horario de verano se resuelve con la base IANA; no se hacen sumas fijas de horas.
- La web ya tiene helpers de fecha/zona en `web/src/lib/dates.ts`; se reutilizan y se
  extienden para el eje horario.

### 5.2 Rango de horas

Entrada: turnos (`working-hours`) de la sucursal, filtrados por trabajador si hay uno.

Algoritmo:

1. Si no hay turnos: `firstHour = 8`, `lastHour = 20`.
2. Para cada turno del rango visible, tomar `start_time` y `end_time`.
3. `firstHour = floor(min(start))`.
4. `lastHour = ceil(max(end))`; si `end_time` es `00:00`, vale 24.
5. Acotar a `0..24`.
6. Si `lastHour - firstHour < 2`, ampliar a 2 horas sin salir de `0..24`.
7. Si el resultado queda invertido o vacío, usar 08:00–20:00.

- En Semana se calcula un solo rango con todos los turnos de los 7 días visibles, para
  que las filas queden alineadas.
- En Día se calcula con los turnos del día y de los trabajadores visibles.
- Los turnos se identifican por `weekday` del backend: 0 = lunes, 6 = domingo.
- Un turno que termina a las 00:00 se muestra hasta las 24 del mismo día.

### 5.3 Precisión visual

- Altura por hora: 64 px.
- Paso de creación: 15 minutos, igual que `BOOKING_SLOT_STEP_MINUTES` del backend.
- Posición vertical: `(minutosDesdePrimeraHora / 60) * 64`.
- Altura: `max(28, (duraciónMinutos / 60) * 64)`.
- La hora se muestra en formato 24 h (`08:00`, `13:30`).

## 6. Datos y API

### 6.1 Reservas

Se reutiliza:

```text
GET /api/v1/bookings/?branch=&worker=&date_from=&date_to=&page=&ordering=start_at
```

- Semana: `date_from` = lunes, `date_to` = domingo, en la zona de la sucursal.
- Día: `date_from` = `date_to` = día seleccionado.
- El servidor ya filtra por empresa y por trabajador cuando el rol es trabajador.
- La app sigue sincronizando reservas por `updated_at`; el calendario usa la caché y
  refresca al abrir y al deslizar.

### 6.2 Horarios de trabajo

Se agrega el recurso de sincronización `working-hours`:

```text
GET /api/v1/mobile/sync/working-hours/?since=<cursor>
```

- Modelo: `apps.workforce.models.WorkingHours`.
- Serializer: `WorkingHoursSerializer` existente.
- Permisos aceptados: `bookings.read` o `bookings.own.read`.
- Feature: `bookings` (el calendario depende de la agenda).
- Un usuario con rol trabajador recibe solo sus propios turnos
  (`worker__membership=membership`), igual que la regla de reservas.
- Se agrega a `SYNC_REGISTRY` y a `SYNC_RESOURCES`.
- `MobileSyncView` especializa el permiso y el filtro para este recurso.

El permiso no puede ser `workforce.read`: `HasTenantPermission` aplica
`enforce_tenant_billing` con el prefijo del permiso y, por tanto, un permiso
`workforce.*` exigiría la feature de plan `workforce`. El calendario debe
funcionar en planes que incluyen agenda pero no la gestión completa de equipo,
así que se usan permisos de `bookings`, cuya feature es `bookings`. El filtro por
trabajador mantiene el aislamiento: el rol `worker` solo sincroniza sus turnos.

No se agregan endpoints nuevos de horarios: la API CRUD ya existe y la web la usa.

### 6.3 Sucursales

- `bootstrap.branches` ya incluye `id`, `name`, `code` y `timezone`.
- Flutter usa esa lista para el selector y para la zona horaria.
- No se requiere un recurso nuevo.

### 6.4 Disponibilidad

- La creación móvil mantiene el flujo actual: formulario + cola de operaciones.
- La web consulta `GET /api/v1/bookings/availability/` antes de crear y al abrir el
  diálogo desde un hueco.
- El calendario no reserva ni bloquea huecos en el cliente.

## 7. Arquitectura Flutter

### 7.1 Archivos nuevos

```text
mobile/lib/core/calendar.dart          funciones puras de semana, día y rango
mobile/lib/widgets/calendar_grid.dart  grilla compartida, eje y posicionamiento
mobile/lib/widgets/week_calendar.dart  vista Semana
mobile/lib/widgets/day_calendar.dart   vista Día
```

`agenda_screen.dart` orquesta vistas, filtros y acciones; no contiene geometría.

### 7.2 Funciones puras

```dart
enum CalendarView { week, day, list }

const double calendarHourHeight = 64;
const int calendarSlotStepMinutes = 15;

DateTime startOfWeek(DateTime date);          // lunes 00:00 en la zona dada
List<DateTime> weekDays(DateTime anchor);     // 7 días
bool sameDay(DateTime a, DateTime b);
int backendWeekday(DateTime date);            // lunes=0 ... domingo=6
String weekDayLabel(DateTime date);           // Lun 09
String longDayLabel(DateTime date);           // lunes 9 de noviembre
String weekRangeLabel(DateTime first, DateTime last); // 9–15 de noviembre

class HourRange {
  const HourRange(this.firstHour, this.lastHour);
  final int firstHour;
  final int lastHour;
  int get hours => lastHour - firstHour;
  double get height => hours * calendarHourHeight;
}

HourRange hourRangeFor({
  required List<WorkingHoursRecord> shifts,
  required List<DateTime> days,
  String? workerId,
  String? branchId,
});

DateTime localInZone(DateTime instant, String timeZone);
DateTime zonedDateTime(String timeZone, DateTime localParts);
List<BookingRecord> bookingsForDay(
  List<BookingRecord> bookings, DateTime day, String timeZone,
);
double topFor(DateTime start, DateTime day, HourRange range);
double heightFor(DateTime start, DateTime end, {double minimum = 28});
DateTime slotStartForOffset(
  DateTime day,
  HourRange range,
  double offset, {
  int stepMinutes = calendarSlotStepMinutes,
});
```

`hourRangeFor` implementa el algoritmo de 5.2. `bookingsForDay` compara año, mes y día
en la zona de la sucursal. `slotStartForOffset` convierte el desplazamiento vertical
en una hora local, redondea hacia abajo al paso de 15 minutos y la acota al rango
visible.

### 7.3 Modelos y estado

- `WorkingHoursRecord`: `id`, `worker`, `branch`, `weekday`, `startMinutes`,
  `endMinutes`.
- `BookingRecord` expone `branchId` y `workerId`; `WorkerRecord` expone `branchIds`
  y `colorHex`.
- `ProductRecord` y `DocumentRecord` se amplían en el plan de inventario; este plan no
  los toca salvo lo necesario para compilar.
- `AppState` agrega:
  - `workingHours` desde la caché `working-hours`;
  - `_loadCachedData` incluye `working-hours`;
  - `branchTimezone(String? branchId)` que busca en `bootstrap.branches`, usa la
    primera zona disponible como respaldo y termina en `America/Santiago`.
- `formatters.dart` agrega `formatTimeIn(value, timeZone)`,
  `formatDateIn(value, timeZone)` y `friendlyDayIn(value, timeZone)` para que la
  lista y las tarjetas usen la zona de la sucursal y no la del dispositivo.
- La caché ya está separada por empresa; no se crea una nueva.
- `main.dart` inicializa `timezone/data/latest.dart`.

### 7.4 Widgets

`CalendarGrid`:

- Recibe días, rango, columnas, constructor de tarjetas, callback de hueco.
- Dibuja el eje de horas fijo y una capa desplazable con líneas y tarjetas.
- Usa `Stack` y `Positioned`; no usa paquetes de calendario externos.
- Mantiene el eje sincronizado verticalmente con las columnas.
- Respeta `SafeArea`, `textScaleFactor` y modo claro/oscuro.
- Cada tarjeta tiene semántica `Reserva de <servicio> con <trabajador>, <hora>`.

`WeekCalendar`:

- Encabezado de 7 días, resaltado del día actual.
- Columnas de 160 px, eje de 56 px.
- Callback `onSelectSlot(DateTime day, DateTime localStart, String? workerId)`.
- Callback `onSelectBooking(BookingRecord)`.

`DayCalendar`:

- Encabezado por trabajador, columnas de 200 px.
- Si no hay trabajadores, una sola columna con todas las reservas.
- Los mismos callbacks.

### 7.5 Pantalla

`AgendaScreen` agrega estado local:

```dart
CalendarView _view = CalendarView.week;
DateTime? _anchor;          // nulo = hoy en la zona de la sucursal
String? _branchId;
String? _workerFilter;
```

- `_anchor` nulo significa hoy; se resuelve en cada `build` con la zona de la
  sucursal. Al cambiar de sucursal se vuelve a nulo para no conservar un día
  calculado en otra zona.
- Inicializa `_branchId` con la primera sucursal del bootstrap y `_workerFilter` con el
  trabajador propio si el rol es trabajador.
- Barra superior: `SegmentedButton` Semana/Día/Lista, navegación temporal y filtros.
- Mantiene las métricas y el `SyncBanner` actuales solo en Lista; en Semana y Día el
  espacio se dedica a la grilla.
- El FAB `Reservar` se conserva y abre el formulario sin hueco preseleccionado.
- Al cambiar de empresa o sucursal, limpia la selección de trabajador si ya no
  pertenece a la sucursal.

### 7.6 Offline

- Semana, Día y Lista leen de la caché existente y de `working-hours`.
- Sin conexión: se muestra el banner actual y los datos guardados; no hay cálculo de
  disponibilidad.
- Crear, cancelar y reprogramar siguen usando `queueOperation` y el outbox actual.
- Al sincronizar, el calendario se reconstruye con los datos nuevos.
- La caché está separada por empresa; cambiar de empresa nunca muestra turnos ni
  reservas de la anterior.

## 8. Web: Día y Semana con eje horario

La web ya tiene `AgendaCalendar` con vista Día (eje horario por trabajador) y Semana
(solo tarjetas). Se extiende:

1. La vista Semana usa una grilla con eje horario y 7 columnas, igual que Flutter.
2. El rango se calcula con los horarios de la sucursal; si no hay, 08:00–20:00.
3. Se consultan los horarios con `GET /api/v1/working-hours/?branch=<id>` paginando
   todas las páginas (el límite es 50).
4. Tocar un hueco abre `BookingCreateDialog` con `initialSlot`
   (`{date, time, workerId?}`).
5. El diálogo preselecciona fecha y hora; si el hueco viene de la columna de un
   trabajador (vista Día), también lo preselecciona. Al elegir servicio consulta
   disponibilidad y exige un slot ofrecido.
6. La vista Día conserva su comportamiento y también acepta clic en hueco.
7. Sin Lista.

En la web el eje usa 64 px por hora. Los huecos se ofrecen cada 30 minutos en un
rango de hasta 16 horas y cada 60 minutos en rangos mayores, para que cada objetivo
conserva al menos 32 px de alto. Una semana sin horarios usa 08:00–20:00 y muestra un
aviso cuando la consulta de horarios falla.

La web no cambia su modelo de sesión ni su caché; las claves de consulta siguen
incluyendo `companyId`.

## 9. Accesibilidad y responsive

- Flutter: objetivos táctiles de al menos 44 × 44 px; contraste AA; texto escalable;
  las tarjetas no dependen solo del color para indicar estado (incluyen etiqueta).
- El eje horario y los encabezados usan semántica de encabezado.
- En modo oscuro, las líneas de hora y las tarjetas usan tokens del tema, no colores
  fijos.
- Web: grilla navegable con teclado; cada hueco es un botón con nombre accesible
  (`Crear reserva el <día> a las 09:00`); foco visible; scroll horizontal con
  encabezado y eje fijos.
- 1280 px: semana completa visible. 768 px: scroll horizontal y filtros en una línea
  que se envuelve.
- Flutter: en pantallas angostas la semana se desplaza horizontalmente; el eje queda
  fijo. No se comprime el ancho de los días.

## 10. Pruebas

### Backend

- `working-hours` aparece en bootstrap para manager y owner con feature `bookings`.
- Un trabajador recibe solo sus turnos y puede sincronizarlos con
  `bookings.own.read`.
- Un usuario sin permiso recibe `403`.
- El cursor `since` y la paginación funcionan.
- No se filtran turnos de otra empresa.
- Regresión de sync de reservas y operaciones.

### Flutter

- `startOfWeek` devuelve lunes para cualquier día, incluido domingo.
- `weekDays` devuelve 7 días consecutivos.
- `hourRangeFor`: sin turnos → 8–20; turnos 09:00–18:00 → 9–18; turno que termina a
  las 00:00 → 24; turnos de 10:00–11:00 → rango mínimo de 2 horas; filtro por
  trabajador y sucursal.
- `localInZone` respeta un cambio de horario de verano.
- `bookingsForDay` agrupa por día de la sucursal y no por la fecha UTC.
- `slotStartForOffset` redondea a 15 minutos y acota al rango visible.
- Widget Semana: 7 columnas, posición y altura de una reserva conocida, etiqueta
  `Cerrado`, callback de hueco con la hora redondeada.
- Widget Día: columnas por trabajador, filtro, columna única sin trabajadores.
- Pantalla: cambio de vista conserva fecha y filtros; cambio de sucursal recalcula;
  rol trabajador bloquea el filtro.
- Offline: renderiza desde caché y muestra el banner.
- `flutter analyze` y `flutter test`.

### Web

- `agendaLayout` calcula el rango desde horarios y usa 8–20 como respaldo.
- Semana renderiza eje y 7 columnas; una reserva cae en la hora correcta.
- Clic en hueco abre el diálogo con fecha/hora y, en la vista Día, también el trabajador.
- El diálogo con `initialSlot` consulta disponibilidad y preselecciona el slot.
- Teclado y nombres accesibles en los huecos.
- Vitest, build y lint.

### End-to-end

- Crear una reserva desde un hueco de la semana web y verla en la grilla.
- Cambiar de sucursal y comprobar que el rango y las reservas cambian.
- Flutter: abrir Semana, tocar un hueco, crear, sincronizar y ver la reserva.

## 11. Criterios de aceptación

1. Flutter abre en Semana por defecto con la semana actual, lunes a domingo, en la zona
   de la sucursal.
2. La grilla muestra un eje horario y reservas ubicadas por hora y duración.
3. Día muestra columnas por trabajador; Lista conserva la agrupación y filtros.
4. Cambiar de vista conserva fecha y filtros; `Hoy` vuelve al día actual.
5. El rango horario sale de los turnos; sin turnos usa 08:00–20:00.
6. Tocar una reserva abre el detalle; tocar un hueco abre el formulario con fecha,
   hora y sucursal; si hay columna, también el trabajador.
7. Los filtros de sucursal y trabajador afectan reservas y rango; un trabajador solo
   ve lo suyo.
8. La web muestra la semana con eje horario y permite crear desde un hueco con
   disponibilidad.
9. Sin conexión, Flutter muestra la agenda cacheada y encola las operaciones.
10. Cambiar de empresa no muestra reservas ni turnos de la anterior.
11. Claro/oscuro, 1280/768 web y pantallas angostas Flutter funcionan sin recortes.
12. `flutter analyze`, `flutter test`, Vitest, build, lint y pruebas backend pasan.

## 12. Riesgos y decisiones asumidas

- **Sin paquete de calendario**: la grilla se implementa con `Stack`/`Positioned` para
  controlar el diseño y evitar dependencias pesadas. Más código, menos sorpresas.
- **Semana con scroll horizontal**: en teléfonos no cabe completa; es preferible a
  comprimir columnas y volver ilegible el texto.
- **Horario de atención**: no existe un modelo de horario por sucursal; se deriva de
  los turnos de los trabajadores. Si todos están libres ese día, se usa el respaldo.
- **Turnos que cruzan medianoche**: se muestran hasta las 24 del día de inicio; la
  continuación no se dibuja en el día siguiente en esta versión.
- **Creación móvil sin disponibilidad**: se mantiene el flujo actual y el servidor
  valida. La web sí consulta disponibilidad.
- **Zona horaria**: depende de que `branches[].timezone` sea una zona IANA válida; el
  backend ya la valida.
- **Rendimiento**: se renderizan solo los días visibles y las reservas del rango; no se
  construyen semanas fuera de pantalla.

No quedan decisiones abiertas para esta versión.
