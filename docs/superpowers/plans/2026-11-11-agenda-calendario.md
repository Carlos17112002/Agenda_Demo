# Calendario Semana/Día/Lista Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Agregar a Flutter las vistas Semana, Día y Lista con eje horario, filtros por sucursal y trabajador, y alta de reserva desde un hueco; sincronizar los horarios de trabajo para que el calendario funcione offline.

**Architecture:** El backend agrega `working-hours` a la sincronización móvil con permisos de agenda y filtro por trabajador. Flutter calcula la semana y el rango horario con funciones puras en `core/calendar.dart`, renderiza la grilla con `Stack`/`Positioned` y usa la zona IANA de la sucursal. La web conserva sus vistas Día/Semana; su extensión con eje horario y alta desde hueco queda en la tarea 19B del plan web, que consume los mismos datos.

**Tech Stack:** Django 6 + DRF, sembast, Flutter 3 (Material 3), `timezone` 0.10, `flutter_test`; React 18 + TypeScript para la contraparte web.

**Spec:** `docs/superpowers/specs/2026-11-11-agenda-calendario-design.md`

## Global Constraints

- Aislamiento por empresa: toda consulta y toda escritura se filtra por `company`; ninguna empresa puede leer, modificar ni eliminar datos de otra.
- La base de datos sigue siendo SQLite local; no se introduce PostgreSQL en este plan.
- Las reservas se guardan en UTC; toda lectura de calendario se muestra en la zona IANA de la sucursal (`branches[].timezone`, por defecto `America/Santiago`).
- El servidor es la autoridad de disponibilidad y conflictos; el cliente no bloquea huecos.
- La UI es en español, con contraste AA, objetivos táctiles de al menos 44 × 44 px y soporte claro/oscuro.
- No se agregan paquetes de calendario externos; la grilla se implementa con widgets estándar.
- No se modifican la duración de las reservas ni el motor de disponibilidad.
- Todo commit requiere autorización explícita de Carlos; los pasos de commit de este plan quedan condicionados.
- Verificación Flutter: `flutter analyze` y `flutter test`. Verificación backend: pruebas dirigidas del módulo móvil.

---

## Estructura de archivos

```text
backend/apps/mobile/sync.py                       recurso working-hours
backend/apps/mobile/resources.py                  whitelist de sync
backend/apps/mobile/views.py                      permiso y filtro por trabajador
backend/apps/mobile/tests/test_sync.py            pruebas del recurso

mobile/pubspec.yaml                               dependencia timezone
mobile/lib/main.dart                              initializeTimeZones
mobile/lib/core/calendar.dart                     semana, zona, rango, slots (nuevo)
mobile/lib/core/formatters.dart                   formato en zona de sucursal
mobile/lib/data/models.dart                       WorkingHoursRecord y getters
mobile/lib/state/app_state.dart                   workingHours y branchTimezone
mobile/lib/widgets/calendar_grid.dart             grilla, eje y tarjetas (nuevo)
mobile/lib/widgets/week_calendar.dart             vista Semana (nuevo)
mobile/lib/widgets/day_calendar.dart              vista Día (nuevo)
mobile/lib/screens/agenda_screen.dart             vistas, filtros y alta desde hueco

mobile/test/models_calendar_test.dart             modelos
mobile/test/app_state_calendar_test.dart          caché por empresa
mobile/test/calendar_test.dart                    funciones puras y DST
mobile/test/calendar_widgets_test.dart            grilla, Semana y Día
mobile/test/agenda_calendar_screen_test.dart      pantalla y cambio de vista
```

La web no se modifica en este plan: su trabajo está en la tarea 19B de
`docs/superpowers/plans/2026-11-11-web-admin-operador.md`, que usa el mismo
recurso `working-hours`, la misma zona de sucursal y el mismo rango 08:00–20:00
como respaldo.

---

### Task 1: Recurso de sincronización `working-hours`

**Files:**
- Modify: `backend/apps/mobile/sync.py`
- Modify: `backend/apps/mobile/resources.py`
- Modify: `backend/apps/mobile/views.py`
- Test: `backend/apps/mobile/tests/test_sync.py`

**Interfaces:**
- Consumes: `apps.workforce.models.WorkingHours`, `apps.workforce.serializers.WorkingHoursSerializer`.
- Produces: `GET /api/v1/mobile/sync/working-hours/` con `results`, `next_since`, `next`; el recurso aparece en `bootstrap.sync_resources` cuando la empresa tiene la feature `bookings` y el usuario tiene `bookings.read` o `bookings.own.read`.

- [ ] **Step 1: Escribir las pruebas del recurso**

En `backend/apps/mobile/tests/test_sync.py`, cambiar el import de fechas:

```python
from datetime import time, timedelta
```

Agregar `WorkingHours` al import de workforce:

```python
from apps.workforce.models import WorkerProfile, WorkingHours
```

Agregar al final del archivo:

```python
class MobileWorkingHoursSyncTests(BillingScenarioMixin, TestCase):
    def setUp(self):
        self.build_billing_scenario(slug="mobile-hours")
        self.branch = Branch.objects.create(company=self.company, name="Centro", code="CEN")
        self.worker = WorkerProfile.objects.create(
            company=self.company, first_name="Luis", last_name="Soto",
        )
        self.hours = WorkingHours.objects.create(
            company=self.company, worker=self.worker, branch=self.branch,
            weekday=0, start_time=time(9, 0), end_time=time(18, 0),
        )

    def test_bootstrap_advertises_working_hours(self):
        response = self.client.get("/api/v1/mobile/bootstrap/")

        self.assertEqual(response.status_code, 200, getattr(response, "data", None))
        self.assertIn("working-hours", response.data["sync_resources"])

    def test_sync_returns_company_working_hours(self):
        response = self.client.get("/api/v1/mobile/sync/working-hours/")

        self.assertEqual(response.status_code, 200, getattr(response, "data", None))
        self.assertEqual(response.data["resource"], "working-hours")
        self.assertEqual(len(response.data["results"]), 1)
        row = response.data["results"][0]
        self.assertEqual(row["id"], str(self.hours.id))
        self.assertEqual(row["weekday"], 0)
        self.assertEqual(row["start_time"], "09:00:00")
        self.assertEqual(row["end_time"], "18:00:00")
        self.assertIn("next_since", response.data)

    def test_worker_sync_only_returns_own_working_hours(self):
        client, membership, _ = self.role_client(
            Membership.Role.WORKER, "worker-hours@example.com",
        )
        own_worker = WorkerProfile.objects.create(
            company=self.company, membership=membership,
            first_name="Wanda", last_name="Propia",
        )
        own = WorkingHours.objects.create(
            company=self.company, worker=own_worker, branch=self.branch,
            weekday=1, start_time=time(10, 0), end_time=time(16, 0),
        )

        response = client.get("/api/v1/mobile/sync/working-hours/")

        self.assertEqual(response.status_code, 200, getattr(response, "data", None))
        self.assertEqual(
            [row["id"] for row in response.data["results"]], [str(own.id)],
        )

    def test_inventory_role_cannot_sync_working_hours(self):
        client, _, _ = self.role_client(
            Membership.Role.INVENTORY, "inventory-hours@example.com",
        )

        response = client.get("/api/v1/mobile/sync/working-hours/")

        self.assertEqual(response.status_code, 403)

    def test_working_hours_are_scoped_by_company(self):
        from apps.tenancy.tests.utils import make_company

        other = make_company("mobile-hours-other", "Horas Otra")
        other_branch = Branch.objects.create(company=other, name="Otra", code="OTR")
        other_worker = WorkerProfile.objects.create(
            company=other, first_name="Otro", last_name="Trabajador",
        )
        WorkingHours.objects.create(
            company=other, worker=other_worker, branch=other_branch,
            weekday=0, start_time=time(8, 0), end_time=time(12, 0),
        )

        response = self.client.get("/api/v1/mobile/sync/working-hours/")

        self.assertEqual(response.status_code, 200, getattr(response, "data", None))
        self.assertEqual(
            [row["id"] for row in response.data["results"]], [str(self.hours.id)],
        )
```

- [ ] **Step 2: Ejecutar las pruebas y ver el fallo**

```bash
cd backend
python manage.py test apps.mobile.tests.test_sync.MobileWorkingHoursSyncTests -v 2
```

Expected: FAIL con 404 en `working-hours` y fallo del bootstrap porque el recurso no está registrado.

- [ ] **Step 3: Registrar el recurso**

En `backend/apps/mobile/sync.py`, importar el modelo y el serializer:

```python
from apps.workforce.models import WorkerProfile, WorkingHours
from apps.workforce.serializers import WorkerProfileSerializer, WorkingHoursSerializer
```

Agregar la entrada al final de `SYNC_REGISTRY`:

```python
    "working-hours": SyncResource(
        WorkingHours, WorkingHoursSerializer,
        ("bookings.read", "bookings.own.read"), feature="bookings",
        select_related=("worker", "branch"),
    ),
```

En `backend/apps/mobile/resources.py`, agregar:

```python
    "working-hours": {
        "permissions": ("bookings.read", "bookings.own.read"),
        "feature": "bookings",
    },
```

Se usan permisos de agenda, no `workforce.read`, porque el calendario depende
de la feature `bookings` y debe funcionar aunque el plan no incluya el módulo
de equipo completo.

- [ ] **Step 4: Especializar permiso y filtro para trabajadores**

En `backend/apps/mobile/views.py`, reemplazar el método
`get_required_tenant_permission` por:

```python
    def get_required_tenant_permission(self):
        resource = self.kwargs.get("resource")
        config = SYNC_REGISTRY.get(resource)
        if config is None:
            return "branches.read"
        membership = self._membership()
        if (resource in {"bookings", "working-hours"} and membership
                and membership.role == Membership.Role.WORKER):
            return "bookings.own.read"
        return config.permissions[0]
```

En `get`, después del filtro de reservas, agregar:

```python
        if (resource == "working-hours" and membership
                and membership.role == Membership.Role.WORKER):
            queryset = queryset.filter(worker__membership=membership)
```

- [ ] **Step 5: Ejecutar las pruebas y verificar**

```bash
cd backend
python manage.py test apps.mobile.tests.test_sync -v 2
```

Expected: PASS, incluida la regresión de reservas, stock y permisos.

- [ ] **Step 6: Commit (requiere autorización explícita de Carlos)**

```bash
git add backend/apps/mobile/sync.py backend/apps/mobile/resources.py backend/apps/mobile/views.py backend/apps/mobile/tests/test_sync.py
git commit -m "feat(mobile): sync working hours for the offline calendar"
```

---

### Task 2: Modelos Flutter y estado por empresa

**Files:**
- Modify: `mobile/lib/data/models.dart`
- Modify: `mobile/lib/state/app_state.dart`
- Test: `mobile/test/models_calendar_test.dart`
- Test: `mobile/test/app_state_calendar_test.dart`

**Interfaces:**
- Consumes: caché sembast ya separada por empresa.
- Produces:
  - `WorkingHoursRecord` con `id`, `workerId`, `branchId`, `weekday`, `startMinutes`, `endMinutes`.
  - `BookingRecord.branchId`, `BookingRecord.workerId`.
  - `WorkerRecord.branchIds`, `WorkerRecord.colorHex`.
  - `AppState.workingHours` y `AppState.branchTimezone(String? branchId)`.

- [ ] **Step 1: Escribir las pruebas de modelos**

`mobile/test/models_calendar_test.dart`:

```dart
import 'package:agenda_mobile/data/models.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('WorkingHoursRecord convierte horas a minutos', () {
    final record = WorkingHoursRecord({
      'id': 'hours-1',
      'worker': 'worker-1',
      'branch': 'branch-1',
      'weekday': 2,
      'start_time': '09:15:00',
      'end_time': '18:30:00',
    });

    expect(record.weekday, 2);
    expect(record.workerId, 'worker-1');
    expect(record.branchId, 'branch-1');
    expect(record.startMinutes, 555);
    expect(record.endMinutes, 1110);
  });

  test('WorkingHoursRecord acepta horas sin segundos', () {
    final record = WorkingHoursRecord({
      'start_time': '08:00',
      'end_time': '00:00',
    });

    expect(record.startMinutes, 480);
    expect(record.endMinutes, 0);
  });

  test('BookingRecord expone sucursal y trabajador', () {
    final booking = BookingRecord({
      'branch': 'branch-1',
      'worker': 'worker-1',
      'start_at': '2026-11-12T13:00:00Z',
    });

    expect(booking.branchId, 'branch-1');
    expect(booking.workerId, 'worker-1');
  });

  test('WorkerRecord expone sucursales y color', () {
    final worker = WorkerRecord({
      'branches': ['branch-1', 'branch-2'],
      'color': '#10B981',
    });

    expect(worker.branchIds, ['branch-1', 'branch-2']);
    expect(worker.colorHex, '#10B981');
  });
}
```

- [ ] **Step 2: Ejecutar las pruebas y ver el fallo**

```bash
cd mobile
flutter test test/models_calendar_test.dart
```

Expected: FAIL porque `WorkingHoursRecord`, `branchId`, `workerId`, `branchIds` y `colorHex` no existen.

- [ ] **Step 3: Implementar los modelos**

En `mobile/lib/data/models.dart`, agregar getters a `BookingRecord`:

```dart
  String get branchId => (raw['branch'] ?? '').toString();
  String get workerId => (raw['worker'] ?? '').toString();
```

En `WorkerRecord`, agregar:

```dart
  List<String> get branchIds =>
      (raw['branches'] as List? ?? const []).map((value) => '$value').toList();

  String get colorHex => (raw['color'] ?? '').toString();
```

Agregar la clase al final del archivo, antes de `OutboxItem`:

```dart
class WorkingHoursRecord {
  WorkingHoursRecord(this.raw);

  final Map<String, dynamic> raw;

  String get id => (raw['id'] ?? '').toString();
  String get workerId => (raw['worker'] ?? '').toString();
  String get branchId => (raw['branch'] ?? '').toString();
  int get weekday => int.tryParse('${raw['weekday']}') ?? 0;
  int get startMinutes => _minutes(raw['start_time']);
  int get endMinutes => _minutes(raw['end_time']);

  static int _minutes(dynamic value) {
    final parts = (value ?? '00:00').toString().split(':');
    final hour = int.tryParse(parts.isNotEmpty ? parts[0] : '') ?? 0;
    final minute = int.tryParse(parts.length > 1 ? parts[1] : '') ?? 0;
    return hour * 60 + minute;
  }
}
```

- [ ] **Step 4: Escribir la prueba de estado y caché**

`mobile/test/app_state_calendar_test.dart`:

```dart
import 'package:agenda_mobile/data/api_client.dart';
import 'package:agenda_mobile/data/local_store.dart';
import 'package:agenda_mobile/data/session_store.dart';
import 'package:agenda_mobile/state/app_state.dart';
import 'package:flutter_test/flutter_test.dart';

class _CalendarApi extends ApiClient {
  _CalendarApi() : super(baseUrl: 'http://fake');

  @override
  Future<Map<String, dynamic>> getMap(
    String path, {
    Map<String, String>? query,
  }) async {
    if (path == '/api/v1/mobile/bootstrap/') {
      return {
        'user': {'email': 'owner@example.com', 'is_saas_admin': false},
        'company': {'id': 'a', 'name': 'Empresa A'},
        'membership': {'role': 'owner'},
        'permissions': ['bookings.read', 'bookings.write'],
        'features': {'bookings': true},
        'modules': {'agenda': true},
        'billing_state': 'legacy',
        'branches': [
          {'id': 'branch-a', 'name': 'Centro', 'timezone': 'America/Santiago'},
        ],
        'sync_resources': <String>[],
        'server_time': '2026-11-11T12:00:00Z',
        'companies': [
          {'id': 'a', 'name': 'Empresa A'},
        ],
      };
    }
    if (path == '/api/v1/mobile/notifications/') {
      return {'results': <dynamic>[], 'unread_count': 0};
    }
    return {'results': <dynamic>[], 'next_since': null, 'next': null};
  }

  @override
  Future<Map<String, dynamic>> postMap(
    String path, {
    Object? body,
    bool authenticated = true,
  }) async {
    if (path == '/api/v1/tenant-contexts/') {
      tenantContextId = 'ctx-a';
      return {'id': 'ctx-a', 'company': 'a'};
    }
    return <String, dynamic>{};
  }

  @override
  Future<List<Map<String, dynamic>>> getList(
    String path, {
    Map<String, String>? query,
  }) async {
    if (path == '/api/v1/companies/mine/') {
      return [
        {'id': 'a', 'name': 'Empresa A'},
      ];
    }
    return const [];
  }
}

class _Sessions extends SessionStore {
  @override
  Future<SessionSnapshot?> load() async => SessionSnapshot(
    baseUrl: 'http://fake',
    accessToken: 'access',
    refreshToken: 'refresh',
    companyId: 'a',
    companyName: 'Empresa A',
  );

  @override
  Future<void> save(SessionSnapshot value) async {}

  @override
  Future<void> clear() async {}
}

void main() {
  test('las horas de trabajo salen de la caché de la empresa activa', () async {
    final store = await LocalStore.memory();
    await store.mergeCache('working-hours', [
      {
        'id': 'hours-a',
        'worker': 'worker-a',
        'branch': 'branch-a',
        'weekday': 0,
        'start_time': '09:00:00',
        'end_time': '18:00:00',
      },
    ], companyId: 'a');
    await store.mergeCache('working-hours', [
      {
        'id': 'hours-b',
        'worker': 'worker-b',
        'branch': 'branch-b',
        'weekday': 0,
        'start_time': '08:00:00',
        'end_time': '12:00:00',
      },
    ], companyId: 'b');

    final state = AppState(
      api: _CalendarApi(),
      store: store,
      sessions: _Sessions(),
    );
    await state.bootstrapApp();

    expect(state.workingHours.map((record) => record.id), ['hours-a']);
    expect(state.branchTimezone('branch-a'), 'America/Santiago');
    expect(state.branchTimezone(null), 'America/Santiago');
  });
}
```

- [ ] **Step 5: Ejecutar la prueba de estado y ver el fallo**

```bash
cd mobile
flutter test test/app_state_calendar_test.dart
```

Expected: FAIL porque `AppState.workingHours` no existe.

- [ ] **Step 6: Implementar el estado**

En `mobile/lib/state/app_state.dart`, agregar después del getter `customers`:

```dart
  List<WorkingHoursRecord> get workingHours =>
      cached('working-hours').map(WorkingHoursRecord.new).toList();

  String branchTimezone(String? branchId) {
    final branches = bootstrap?.branches ?? const <Map<String, dynamic>>[];
    for (final branch in branches) {
      if ('${branch['id']}' == branchId) {
        final zone = (branch['timezone'] ?? '').toString();
        if (zone.isNotEmpty) return zone;
      }
    }
    for (final branch in branches) {
      final zone = (branch['timezone'] ?? '').toString();
      if (zone.isNotEmpty) return zone;
    }
    return 'America/Santiago';
  }
```

Agregar `'working-hours'` a la lista de recursos de `_loadCachedData`:

```dart
      for (final resource in const [
        'bookings',
        'services',
        'workers',
        'customers',
        'products',
        'warehouses',
        'stock',
        'branches',
        'working-hours',
      ]) {
```

Si el plan `docs/superpowers/plans/2026-11-11-inventario-objetos-archivos.md` ya se
aplicó, conserva también `'categories'`, `'suppliers'` y `'documents'` en esa lista;
no elimines recursos existentes.

- [ ] **Step 7: Ejecutar las pruebas y verificar**

```bash
cd mobile
flutter test test/models_calendar_test.dart test/app_state_calendar_test.dart test/app_state_cache_test.dart
```

Expected: PASS.

- [ ] **Step 8: Commit (requiere autorización explícita de Carlos)**

```bash
git add mobile/lib/data/models.dart mobile/lib/state/app_state.dart mobile/test/models_calendar_test.dart mobile/test/app_state_calendar_test.dart
git commit -m "feat(mobile): expose working hours and branch timezone in app state"
```

---

### Task 3: Zona horaria, semana y rango horario

**Files:**
- Modify: `mobile/pubspec.yaml`
- Modify: `mobile/lib/main.dart`
- Modify: `mobile/lib/core/formatters.dart`
- Create: `mobile/lib/core/calendar.dart`
- Test: `mobile/test/calendar_test.dart`

**Interfaces:**
- Consumes: `WorkingHoursRecord`, `BookingRecord`.
- Produces:
  - `CalendarView { week, day, list }`.
  - `startOfWeek`, `weekDays`, `sameDay`, `backendWeekday`.
  - `HourRange`, `hourRangeFor`, `localInZone`, `zonedDateTime`.
  - `bookingsForDay`, `topFor`, `heightFor`, `slotStartForOffset`.
  - `weekDayLabel`, `longDayLabel`, `weekRangeLabel`.
  - `formatTimeIn`, `formatDateIn`, `friendlyDayIn`.

- [ ] **Step 1: Agregar la dependencia y escribir las pruebas**

En `mobile/pubspec.yaml`, dentro de `dependencies`, agregar:

```yaml
  timezone: ^0.10.0
```

`mobile/test/calendar_test.dart`:

```dart
import 'package:agenda_mobile/core/calendar.dart';
import 'package:agenda_mobile/core/formatters.dart';
import 'package:agenda_mobile/data/models.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:timezone/data/latest.dart' as tzdata;

void main() {
  setUpAll(tzdata.initializeTimeZones);

  test('startOfWeek devuelve el lunes', () {
    expect(startOfWeek(DateTime(2026, 11, 15)), DateTime(2026, 11, 9));
    expect(startOfWeek(DateTime(2026, 11, 9)), DateTime(2026, 11, 9));
  });

  test('weekDays devuelve siete días consecutivos', () {
    final days = weekDays(DateTime(2026, 11, 12));

    expect(days, hasLength(7));
    expect(days.first, DateTime(2026, 11, 9));
    expect(days.last, DateTime(2026, 11, 15));
  });

  test('hourRangeFor usa 08:00–20:00 sin turnos', () {
    final range = hourRangeFor(
      shifts: const [],
      days: [DateTime(2026, 11, 9)],
    );

    expect(range.firstHour, 8);
    expect(range.lastHour, 20);
  });

  test('hourRangeFor usa los turnos de la sucursal y del trabajador', () {
    final shifts = [
      WorkingHoursRecord({
        'worker': 'w1',
        'branch': 'b1',
        'weekday': 0,
        'start_time': '09:00:00',
        'end_time': '18:00:00',
      }),
      WorkingHoursRecord({
        'worker': 'w2',
        'branch': 'b1',
        'weekday': 0,
        'start_time': '07:00:00',
        'end_time': '22:00:00',
      }),
    ];
    final day = [DateTime(2026, 11, 9)];

    final all = hourRangeFor(shifts: shifts, days: day, branchId: 'b1');
    final only = hourRangeFor(
      shifts: shifts,
      days: day,
      branchId: 'b1',
      workerId: 'w1',
    );

    expect(all.firstHour, 7);
    expect(all.lastHour, 22);
    expect(only.firstHour, 9);
    expect(only.lastHour, 18);
  });

  test('hourRangeFor trata el término a las 00:00 como 24', () {
    final range = hourRangeFor(
      shifts: [
        WorkingHoursRecord({
          'worker': 'w1',
          'branch': 'b1',
          'weekday': 0,
          'start_time': '18:00:00',
          'end_time': '00:00:00',
        }),
      ],
      days: [DateTime(2026, 11, 9)],
      branchId: 'b1',
    );

    expect(range.firstHour, 18);
    expect(range.lastHour, 24);
  });

  test('hourRangeFor garantiza al menos dos horas', () {
    final range = hourRangeFor(
      shifts: [
        WorkingHoursRecord({
          'worker': 'w1',
          'branch': 'b1',
          'weekday': 0,
          'start_time': '10:00:00',
          'end_time': '11:00:00',
        }),
      ],
      days: [DateTime(2026, 11, 9)],
      branchId: 'b1',
    );

    expect(range.firstHour, 10);
    expect(range.lastHour, 12);
  });

  test('localInZone aplica el cambio de horario de verano', () {
    final local = localInZone(
      DateTime.utc(2026, 9, 6, 4, 30),
      'America/Santiago',
    );
    final utc = zonedDateTime(
      'America/Santiago',
      DateTime(2026, 9, 6, 1, 30),
    ).toUtc();

    expect(local.year, 2026);
    expect(local.month, 9);
    expect(local.day, 6);
    expect(local.hour, 1);
    expect(local.minute, 30);
    expect(utc, DateTime.utc(2026, 9, 6, 4, 30));
  });

  test('bookingsForDay agrupa por día de la sucursal', () {
    final bookings = [
      BookingRecord({
        'id': 'b1',
        'start_at': '2026-11-12T02:00:00Z',
        'end_at': '2026-11-12T03:00:00Z',
      }),
    ];

    final localDay = bookingsForDay(
      bookings,
      DateTime(2026, 11, 11),
      'America/Santiago',
    );
    final utcDay = bookingsForDay(
      bookings,
      DateTime(2026, 11, 12),
      'America/Santiago',
    );

    expect(localDay.map((booking) => booking.id), ['b1']);
    expect(utcDay, isEmpty);
  });

  test('slotStartForOffset redondea a 15 minutos', () {
    const range = HourRange(8, 20);
    final day = DateTime(2026, 11, 12);

    expect(slotStartForOffset(day, range, 0), DateTime(2026, 11, 12, 8));
    expect(slotStartForOffset(day, range, 64), DateTime(2026, 11, 12, 9));
    expect(slotStartForOffset(day, range, 100), DateTime(2026, 11, 12, 9, 30));
  });

  test('formatTimeIn y formatDateIn usan la zona de la sucursal', () {
    final instant = DateTime.parse('2026-11-12T02:00:00Z');

    expect(formatTimeIn(instant, 'America/Santiago'), '23:00');
    expect(formatDateIn(instant, 'America/Santiago'), '11/11/2026');
  });
}
```

- [ ] **Step 2: Ejecutar las pruebas y ver el fallo**

```bash
cd mobile
flutter pub get
flutter test test/calendar_test.dart
```

Expected: FAIL porque `core/calendar.dart` no existe.

- [ ] **Step 3: Implementar las funciones puras**

`mobile/lib/core/calendar.dart`:

```dart
import 'package:timezone/timezone.dart' as tz;

import '../data/models.dart';

enum CalendarView { week, day, list }

const double calendarHourHeight = 64;
const int calendarSlotStepMinutes = 15;

const _weekdayShort = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom'];
const _weekdayLong = [
  'lunes',
  'martes',
  'miércoles',
  'jueves',
  'viernes',
  'sábado',
  'domingo',
];
const _monthNames = [
  'enero',
  'febrero',
  'marzo',
  'abril',
  'mayo',
  'junio',
  'julio',
  'agosto',
  'septiembre',
  'octubre',
  'noviembre',
  'diciembre',
];

DateTime startOfWeek(DateTime date) {
  final day = DateTime(date.year, date.month, date.day);
  return day.subtract(Duration(days: day.weekday - DateTime.monday));
}

List<DateTime> weekDays(DateTime anchor) {
  final start = startOfWeek(anchor);
  return List.generate(
    7,
    (index) => DateTime(start.year, start.month, start.day + index),
  );
}

bool sameDay(DateTime a, DateTime b) =>
    a.year == b.year && a.month == b.month && a.day == b.day;

int backendWeekday(DateTime date) => date.weekday - 1;

String weekDayLabel(DateTime date) =>
    '${_weekdayShort[backendWeekday(date)]} ${date.day.toString().padLeft(2, '0')}';

String longDayLabel(DateTime date) =>
    '${_weekdayLong[backendWeekday(date)]} ${date.day} de ${_monthNames[date.month - 1]}';

String weekRangeLabel(DateTime first, DateTime last) {
  if (first.month == last.month) {
    return '${first.day}–${last.day} de ${_monthNames[first.month - 1]}';
  }
  return '${first.day} de ${_monthNames[first.month - 1]} – '
      '${last.day} de ${_monthNames[last.month - 1]}';
}

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
}) {
  final weekdays = days.map(backendWeekday).toSet();
  final relevant = shifts.where(
    (shift) =>
        weekdays.contains(shift.weekday) &&
        (workerId == null || shift.workerId == workerId) &&
        (branchId == null || shift.branchId == branchId),
  );
  if (relevant.isEmpty) return const HourRange(8, 20);

  var firstMinute = 24 * 60;
  var lastMinute = 0;
  for (final shift in relevant) {
    if (shift.startMinutes < firstMinute) firstMinute = shift.startMinutes;
    final end = shift.endMinutes == 0 ? 24 * 60 : shift.endMinutes;
    if (end > lastMinute) lastMinute = end;
  }

  var firstHour = (firstMinute ~/ 60).clamp(0, 24).toInt();
  var lastHour = (lastMinute / 60).ceil().clamp(0, 24).toInt();
  if (lastHour - firstHour < 2) {
    lastHour = (firstHour + 2).clamp(0, 24).toInt();
    if (lastHour - firstHour < 2) {
      firstHour = (lastHour - 2).clamp(0, 24).toInt();
    }
  }
  if (lastHour <= firstHour) return const HourRange(8, 20);
  return HourRange(firstHour, lastHour);
}

tz.Location calendarLocation(String timeZone) {
  try {
    return tz.getLocation(timeZone);
  } on tz.LocationNotFoundException {
    return tz.getLocation('America/Santiago');
  }
}

DateTime localInZone(DateTime instant, String timeZone) =>
    tz.TZDateTime.from(instant.toUtc(), calendarLocation(timeZone));

DateTime zonedDateTime(String timeZone, DateTime localParts) =>
    tz.TZDateTime(
      calendarLocation(timeZone),
      localParts.year,
      localParts.month,
      localParts.day,
      localParts.hour,
      localParts.minute,
    );

List<BookingRecord> bookingsForDay(
  List<BookingRecord> bookings,
  DateTime day,
  String timeZone,
) {
  final result = bookings.where((booking) {
    final start = booking.startAt;
    if (start == null) return false;
    return sameDay(localInZone(start, timeZone), day);
  }).toList();
  result.sort((a, b) => a.startAt!.compareTo(b.startAt!));
  return result;
}

double topFor(DateTime start, DateTime day, HourRange range) {
  final minutes =
      (start.hour * 60 + start.minute) - range.firstHour * 60;
  final clamped = minutes.clamp(0, range.hours * 60);
  return clamped / 60 * calendarHourHeight;
}

double heightFor(DateTime start, DateTime end, {double minimum = 28}) {
  final height = end.difference(start).inMinutes / 60 * calendarHourHeight;
  return height < minimum ? minimum : height;
}

DateTime slotStartForOffset(
  DateTime day,
  HourRange range,
  double offset, {
  int stepMinutes = calendarSlotStepMinutes,
}) {
  final rawMinutes = range.firstHour * 60 + (offset / calendarHourHeight * 60).floor();
  final stepped = (rawMinutes ~/ stepMinutes) * stepMinutes;
  final minimum = range.firstHour * 60;
  final maximum = range.lastHour * 60 - stepMinutes;
  final clamped = stepped.clamp(minimum, maximum).toInt();
  return DateTime(
    day.year,
    day.month,
    day.day,
    clamped ~/ 60,
    clamped % 60,
  );
}
```

- [ ] **Step 4: Inicializar la base de zonas horarias**

`mobile/lib/main.dart`:

```dart
import 'package:flutter/material.dart';
import 'package:timezone/data/latest.dart' as tzdata;

import 'app.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  tzdata.initializeTimeZones();
  runApp(const AgendaApp());
}
```

- [ ] **Step 5: Agregar formato por zona de sucursal**

En `mobile/lib/core/formatters.dart`, agregar el import:

```dart
import 'calendar.dart';
```

Agregar al final:

```dart
String formatTimeIn(DateTime value, String timeZone) {
  final local = localInZone(value, timeZone);
  return '${twoDigits(local.hour)}:${twoDigits(local.minute)}';
}

String formatDateIn(DateTime value, String timeZone) {
  final local = localInZone(value, timeZone);
  return '${twoDigits(local.day)}/${twoDigits(local.month)}/${local.year}';
}

String friendlyDayIn(DateTime value, String timeZone) {
  final local = localInZone(value, timeZone);
  final now = localInZone(DateTime.now().toUtc(), timeZone);
  final day = DateTime(local.year, local.month, local.day);
  final today = DateTime(now.year, now.month, now.day);
  final difference = day.difference(today).inDays;
  if (difference == 0) return 'Hoy';
  if (difference == 1) return 'Mañana';
  if (difference == -1) return 'Ayer';
  const weekdays = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom'];
  return '${weekdays[local.weekday - 1]} ${twoDigits(local.day)}/${twoDigits(local.month)}';
}
```

- [ ] **Step 6: Ejecutar las pruebas y verificar**

```bash
cd mobile
flutter test test/calendar_test.dart
flutter analyze
```

Expected: PASS y sin errores de análisis.

- [ ] **Step 7: Commit (requiere autorización explícita de Carlos)**

```bash
git add mobile/pubspec.yaml mobile/pubspec.lock mobile/lib/main.dart mobile/lib/core/calendar.dart mobile/lib/core/formatters.dart mobile/test/calendar_test.dart
git commit -m "feat(mobile): add branch-timezone calendar helpers"
```

---

### Task 4: Grilla compartida con eje horario

**Files:**
- Create: `mobile/lib/widgets/calendar_grid.dart`
- Test: `mobile/test/calendar_widgets_test.dart`

**Interfaces:**
- Consumes: `CalendarColumn`, `HourRange`, `BookingRecord`, `localInZone`, `topFor`, `heightFor`, `slotStartForOffset`.
- Produces:
  - `CalendarGrid({columns, range, bookings, timeZone, onSelectBooking, onSelectSlot, columnWidth, headerHeight})`.
  - `CalendarColumn({day, title, subtitle, workerId, color})`.
  - `workerColor(String hex)` para las vistas.
  - Claves `calendar-slot-<índice>` y `calendar-booking-<id>` para pruebas.

- [ ] **Step 1: Escribir la prueba de la grilla**

`mobile/test/calendar_widgets_test.dart`:

```dart
import 'package:agenda_mobile/core/calendar.dart';
import 'package:agenda_mobile/core/theme.dart';
import 'package:agenda_mobile/data/models.dart';
import 'package:agenda_mobile/widgets/calendar_grid.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:timezone/data/latest.dart' as tzdata;

BookingRecord _booking({
  String id = 'booking-1',
  String start = '2026-11-09T12:00:00Z',
  String end = '2026-11-09T12:30:00Z',
  String worker = 'worker-1',
}) {
  return BookingRecord({
    'id': id,
    'branch': 'branch-1',
    'worker': worker,
    'worker_name': 'Paula Rojas',
    'service_name': 'Corte',
    'customer_name': 'Ana Díaz',
    'status': 'scheduled',
    'start_at': start,
    'end_at': end,
    'public_code': 'ABC123',
  });
}

Widget _host(Widget child) {
  return MaterialApp(
    theme: buildAgendaTheme(),
    home: Scaffold(body: SizedBox(width: 900, height: 700, child: child)),
  );
}

void main() {
  setUpAll(tzdata.initializeTimeZones);

  testWidgets('la grilla dibuja eje, siete columnas y una reserva', (
    tester,
  ) async {
    await tester.pumpWidget(
      _host(
        CalendarGrid(
          columns: [
            for (var index = 0; index < 7; index++)
              CalendarColumn(
                day: DateTime(2026, 11, 9 + index),
                title: 'Día ${index + 1}',
              ),
          ],
          range: const HourRange(8, 20),
          bookings: [_booking()],
          timeZone: 'America/Santiago',
          onSelectBooking: (_) {},
          onSelectSlot: (_, _, _) {},
        ),
      ),
    );

    expect(find.text('08:00'), findsOneWidget);
    expect(find.text('20:00'), findsOneWidget);
    expect(find.text('Día 1'), findsOneWidget);
    expect(find.text('Día 7'), findsOneWidget);
    expect(find.textContaining('Corte'), findsOneWidget);
  });

  testWidgets('tocar una tarjeta abre el detalle', (tester) async {
    BookingRecord? selected;
    await tester.pumpWidget(
      _host(
        CalendarGrid(
          columns: [
            CalendarColumn(
              day: DateTime(2026, 11, 9),
              title: 'Lun 09',
            ),
          ],
          range: const HourRange(8, 20),
          bookings: [_booking()],
          timeZone: 'America/Santiago',
          onSelectBooking: (booking) => selected = booking,
          onSelectSlot: (_, _, _) {},
        ),
      ),
    );

    await tester.tap(find.byKey(const Key('calendar-booking-booking-1')));

    expect(selected?.id, 'booking-1');
  });

  testWidgets('tocar un hueco devuelve la hora redondeada', (tester) async {
    DateTime? selectedDay;
    DateTime? selectedStart;
    await tester.pumpWidget(
      _host(
        CalendarGrid(
          columns: [
            CalendarColumn(
              day: DateTime(2026, 11, 9),
              title: 'Lun 09',
              workerId: 'worker-1',
            ),
          ],
          range: const HourRange(8, 20),
          bookings: const [],
          timeZone: 'America/Santiago',
          onSelectBooking: (_) {},
          onSelectSlot: (day, start, workerId) {
            selectedDay = day;
            selectedStart = start;
            expect(workerId, 'worker-1');
          },
        ),
      ),
    );

    final slot = find.byKey(const Key('calendar-slot-0'));
    final topLeft = tester.getTopLeft(slot);
    await tester.tapAt(topLeft + const Offset(80, 64));

    expect(selectedDay, DateTime(2026, 11, 9));
    expect(selectedStart, DateTime(2026, 11, 9, 9));
  });
}
```

- [ ] **Step 2: Ejecutar la prueba y ver el fallo**

```bash
cd mobile
flutter test test/calendar_widgets_test.dart
```

Expected: FAIL porque `calendar_grid.dart` no existe.

- [ ] **Step 3: Implementar la grilla**

`mobile/lib/widgets/calendar_grid.dart`:

```dart
import 'package:flutter/material.dart';

import '../core/calendar.dart';
import '../core/formatters.dart';
import '../core/theme.dart';
import '../data/models.dart';

const double calendarAxisWidth = 56;

class CalendarColumn {
  const CalendarColumn({
    required this.day,
    required this.title,
    this.subtitle = '',
    this.workerId,
    this.color,
  });

  final DateTime day;
  final String title;
  final String subtitle;
  final String? workerId;
  final Color? color;
}

Color? workerColor(String hex) {
  final match = RegExp(r'^#([0-9A-Fa-f]{6})$').firstMatch(hex);
  if (match == null) return null;
  return Color(int.parse('FF${match.group(1)}', radix: 16));
}

class CalendarGrid extends StatelessWidget {
  const CalendarGrid({
    super.key,
    required this.columns,
    required this.range,
    required this.bookings,
    required this.timeZone,
    required this.onSelectBooking,
    required this.onSelectSlot,
    this.columnWidth = 160,
    this.headerHeight = 56,
  });

  final List<CalendarColumn> columns;
  final HourRange range;
  final List<BookingRecord> bookings;
  final String timeZone;
  final ValueChanged<BookingRecord> onSelectBooking;
  final void Function(DateTime day, DateTime localStart, String? workerId)
  onSelectSlot;
  final double columnWidth;
  final double headerHeight;

  @override
  Widget build(BuildContext context) {
    final palette = context.palette;
    final gridHeight = range.height;

    return SingleChildScrollView(
      physics: const AlwaysScrollableScrollPhysics(),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: calendarAxisWidth,
            child: Column(
              children: [
                SizedBox(height: headerHeight),
                SizedBox(
                  height: gridHeight,
                  child: Stack(
                    children: [
                      for (
                        var hour = range.firstHour;
                        hour < range.lastHour;
                        hour++
                      )
                        Positioned(
                          top:
                              (hour - range.firstHour) * calendarHourHeight,
                          right: 8,
                          child: Text(
                            '${twoDigits(hour)}:00',
                            style: TextStyle(
                              fontSize: 11,
                              color: palette.muted,
                            ),
                          ),
                        ),
                    ],
                  ),
                ),
              ],
            ),
          ),
          Expanded(
            child: SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              child: SizedBox(
                width: columns.length * columnWidth,
                child: Column(
                  children: [
                    SizedBox(
                      height: headerHeight,
                      child: Row(
                        children: [
                          for (final column in columns)
                            SizedBox(
                              width: columnWidth,
                              child: _ColumnHeader(
                                column: column,
                                timeZone: timeZone,
                              ),
                            ),
                        ],
                      ),
                    ),
                    SizedBox(
                      height: gridHeight,
                      child: Stack(
                        children: [
                          Row(
                            children: [
                              for (
                                var index = 0;
                                index < columns.length;
                                index++
                              )
                                SizedBox(
                                  width: columnWidth,
                                  child: GestureDetector(
                                    key: Key('calendar-slot-$index'),
                                    behavior: HitTestBehavior.opaque,
                                    onTapUp: (details) => onSelectSlot(
                                      columns[index].day,
                                      slotStartForOffset(
                                        columns[index].day,
                                        range,
                                        details.localPosition.dy,
                                      ),
                                      columns[index].workerId,
                                    ),
                                    child: _ColumnBackground(
                                      height: gridHeight,
                                      range: range,
                                    ),
                                  ),
                                ),
                            ],
                          ),
                          for (
                            var index = 0;
                            index < columns.length;
                            index++
                          )
                            ..._cardsFor(context, columns[index], index),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  List<Widget> _cardsFor(
    BuildContext context,
    CalendarColumn column,
    int index,
  ) {
    final dayBookings = bookings.where((booking) {
      final start = booking.startAt;
      if (start == null) return false;
      if (column.workerId != null && booking.workerId != column.workerId) {
        return false;
      }
      return sameDay(localInZone(start, timeZone), column.day);
    }).toList()..sort((a, b) => a.startAt!.compareTo(b.startAt!));

    final cards = <Widget>[];
    for (var position = 0; position < dayBookings.length; position++) {
      final booking = dayBookings[position];
      final start = booking.startAt!;
      final end = booking.endAt ?? start.add(const Duration(minutes: 30));
      final localStart = localInZone(start, timeZone);
      final localEnd = localInZone(end, timeZone);
      final windowStart = DateTime(
        column.day.year,
        column.day.month,
        column.day.day,
        range.firstHour,
      );
      final windowEnd = DateTime(
        column.day.year,
        column.day.month,
        column.day.day,
        range.lastHour,
      );
      final visibleStart = localStart.isBefore(windowStart)
          ? windowStart
          : localStart;
      final visibleEnd = localEnd.isAfter(windowEnd) ? windowEnd : localEnd;
      if (!visibleEnd.isAfter(visibleStart)) continue;

      final lanes = dayBookings
          .take(position)
          .where((other) {
            final otherEnd = other.endAt ?? other.startAt!;
            return otherEnd.isAfter(start);
          })
          .length
          .clamp(0, 2)
          .toInt();
      final left = index * columnWidth + 4 + lanes * 8;
      final width = (columnWidth - 8 - lanes * 8)
          .clamp(48.0, columnWidth)
          .toDouble();

      cards.add(
        Positioned(
          left: left,
          top: topFor(visibleStart, column.day, range),
          width: width,
          height: heightFor(visibleStart, visibleEnd),
          child: _BookingChip(
            key: Key('calendar-booking-${booking.id}'),
            booking: booking,
            timeZone: timeZone,
            onTap: () => onSelectBooking(booking),
          ),
        ),
      );
    }
    return cards;
  }
}

class _ColumnHeader extends StatelessWidget {
  const _ColumnHeader({required this.column, required this.timeZone});

  final CalendarColumn column;
  final String timeZone;

  @override
  Widget build(BuildContext context) {
    final palette = context.palette;
    final isToday = sameDay(
      localInZone(DateTime.now().toUtc(), timeZone),
      column.day,
    );
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 6, horizontal: 6),
      decoration: BoxDecoration(
        border: Border(
          left: BorderSide(color: palette.border),
          bottom: BorderSide(color: palette.border),
        ),
      ),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Text(
            column.title,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w800,
              color: isToday
                  ? Theme.of(context).colorScheme.primary
                  : palette.onSurface,
            ),
          ),
          if (column.subtitle.isNotEmpty)
            Text(
              column.subtitle,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: TextStyle(fontSize: 10, color: palette.muted),
            ),
        ],
      ),
    );
  }
}

class _ColumnBackground extends StatelessWidget {
  const _ColumnBackground({required this.height, required this.range});

  final double height;
  final HourRange range;

  @override
  Widget build(BuildContext context) {
    final palette = context.palette;
    return Container(
      height: height,
      decoration: BoxDecoration(
        border: Border(
          left: BorderSide(color: palette.border),
          bottom: BorderSide(color: palette.border),
        ),
      ),
      child: Stack(
        children: [
          for (var hour = range.firstHour; hour < range.lastHour; hour++)
            Positioned(
              top: (hour - range.firstHour) * calendarHourHeight,
              left: 0,
              right: 0,
              child: Container(
                height: 1,
                color: palette.border.withValues(alpha: 0.6),
              ),
            ),
        ],
      ),
    );
  }
}

class _BookingChip extends StatelessWidget {
  const _BookingChip({
    super.key,
    required this.booking,
    required this.timeZone,
    required this.onTap,
  });

  final BookingRecord booking;
  final String timeZone;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final palette = context.palette;
    final scheme = Theme.of(context).colorScheme;
    final start = booking.startAt!;
    final tone = switch (booking.status) {
      'confirmed' => scheme.primary,
      'canceled' || 'no_show' => scheme.error,
      _ => scheme.secondary,
    };
    final label =
        'Reserva de ${booking.serviceName} con ${booking.workerName}, '
        '${formatTimeIn(start, timeZone)}';

    return Semantics(
      button: true,
      label: label,
      child: GestureDetector(
        behavior: HitTestBehavior.opaque,
        onTap: onTap,
        child: Container(
          padding: const EdgeInsets.all(4),
          decoration: BoxDecoration(
            color: tone.withValues(alpha: 0.16),
            borderRadius: BorderRadius.circular(6),
            border: Border(left: BorderSide(color: tone, width: 3)),
          ),
          child: ClipRect(
            child: LayoutBuilder(
              builder: (context, constraints) {
                final showCustomer = constraints.maxHeight >= 44;
                return Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      '${formatTimeIn(start, timeZone)} ${booking.serviceName}',
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(
                        fontSize: 10,
                        fontWeight: FontWeight.w700,
                        color: palette.onSurface,
                      ),
                    ),
                    if (showCustomer)
                      Text(
                        booking.customerName,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(
                          fontSize: 9.5,
                          color: palette.muted,
                        ),
                      ),
                  ],
                );
              },
            ),
          ),
        ),
      ),
    );
  }
}
```

- [ ] **Step 4: Ejecutar la prueba y verificar**

```bash
cd mobile
flutter test test/calendar_widgets_test.dart
flutter analyze
```

Expected: PASS. Si el toque del hueco no cae dentro de la columna, ajustar
`topLeft + Offset(80, 64)` a `Offset(80, 65)` (el borde superior consume 1 px).

- [ ] **Step 5: Commit (requiere autorización explícita de Carlos)**

```bash
git add mobile/lib/widgets/calendar_grid.dart mobile/test/calendar_widgets_test.dart
git commit -m "feat(mobile): add shared calendar grid with hour axis"
```

---

### Task 5: Vistas Semana y Día

**Files:**
- Create: `mobile/lib/widgets/week_calendar.dart`
- Create: `mobile/lib/widgets/day_calendar.dart`
- Modify: `mobile/test/calendar_widgets_test.dart`

**Interfaces:**
- Consumes: `CalendarGrid`, `CalendarColumn`, `workerColor`, `hourRangeFor`, `weekDays`.
- Produces:
  - `WeekCalendar({anchor, timeZone, bookings, shifts, branchId, workerId, onSelectBooking, onSelectSlot})`.
  - `DayCalendar({day, timeZone, bookings, shifts, branchId, workers, workerId, onSelectBooking, onSelectSlot})`.

- [ ] **Step 1: Agregar las pruebas de Semana y Día**

En `mobile/test/calendar_widgets_test.dart`, agregar imports:

```dart
import 'package:agenda_mobile/widgets/day_calendar.dart';
import 'package:agenda_mobile/widgets/week_calendar.dart';
```

Agregar al final de `main`:

```dart
  testWidgets('Semana muestra siete días y marca los cerrados', (
    tester,
  ) async {
    await tester.pumpWidget(
      _host(
        WeekCalendar(
          anchor: DateTime(2026, 11, 9),
          timeZone: 'America/Santiago',
          bookings: [_booking()],
          shifts: [
            WorkingHoursRecord({
              'worker': 'worker-1',
              'branch': 'branch-1',
              'weekday': 0,
              'start_time': '09:00:00',
              'end_time': '18:00:00',
            }),
          ],
          branchId: 'branch-1',
          workerId: null,
          onSelectBooking: (_) {},
          onSelectSlot: (_, _, _) {},
        ),
      ),
    );

    expect(find.text('Lun 09'), findsOneWidget);
    expect(find.text('Dom 15'), findsOneWidget);
    expect(find.text('Cerrado'), findsNWidgets(6));
    expect(find.text('08:00'), findsOneWidget);
  });

  testWidgets('Día muestra una columna por trabajador', (tester) async {
    await tester.pumpWidget(
      _host(
        DayCalendar(
          day: DateTime(2026, 11, 9),
          timeZone: 'America/Santiago',
          bookings: const [],
          shifts: const [],
          branchId: 'branch-1',
          workers: [
            WorkerRecord({
              'id': 'worker-1',
              'first_name': 'Paula',
              'last_name': 'Rojas',
              'branches': ['branch-1'],
              'color': '#10B981',
            }),
            WorkerRecord({
              'id': 'worker-2',
              'first_name': 'Diego',
              'last_name': 'Soto',
              'branches': ['branch-1'],
            }),
          ],
          workerId: null,
          onSelectBooking: (_) {},
          onSelectSlot: (_, _, _) {},
        ),
      ),
    );

    expect(find.text('Paula Rojas'), findsOneWidget);
    expect(find.text('Diego Soto'), findsOneWidget);
    expect(find.text('Sin horario'), findsNWidgets(2));
  });
```

- [ ] **Step 2: Ejecutar las pruebas y ver el fallo**

```bash
cd mobile
flutter test test/calendar_widgets_test.dart
```

Expected: FAIL porque `week_calendar.dart` y `day_calendar.dart` no existen.

- [ ] **Step 3: Implementar la vista Semana**

`mobile/lib/widgets/week_calendar.dart`:

```dart
import 'package:flutter/material.dart';

import '../core/calendar.dart';
import '../data/models.dart';
import 'calendar_grid.dart';

class WeekCalendar extends StatelessWidget {
  const WeekCalendar({
    super.key,
    required this.anchor,
    required this.timeZone,
    required this.bookings,
    required this.shifts,
    required this.branchId,
    required this.workerId,
    required this.onSelectBooking,
    required this.onSelectSlot,
  });

  final DateTime anchor;
  final String timeZone;
  final List<BookingRecord> bookings;
  final List<WorkingHoursRecord> shifts;
  final String branchId;
  final String? workerId;
  final ValueChanged<BookingRecord> onSelectBooking;
  final void Function(DateTime day, DateTime localStart, String? workerId)
  onSelectSlot;

  @override
  Widget build(BuildContext context) {
    final days = weekDays(anchor);
    final range = hourRangeFor(
      shifts: shifts,
      days: days,
      workerId: workerId,
      branchId: branchId,
    );

    return CalendarGrid(
      columns: [
        for (final day in days)
          CalendarColumn(
            day: day,
            title: weekDayLabel(day),
            subtitle: shifts.any(
              (shift) =>
                  shift.branchId == branchId &&
                  shift.weekday == backendWeekday(day) &&
                  (workerId == null || shift.workerId == workerId),
            )
                ? ''
                : 'Cerrado',
          ),
      ],
      range: range,
      bookings: bookings,
      timeZone: timeZone,
      onSelectBooking: onSelectBooking,
      onSelectSlot: onSelectSlot,
    );
  }
}
```

- [ ] **Step 4: Implementar la vista Día**

`mobile/lib/widgets/day_calendar.dart`:

```dart
import 'package:flutter/material.dart';

import '../core/calendar.dart';
import '../data/models.dart';
import 'calendar_grid.dart';

class DayCalendar extends StatelessWidget {
  const DayCalendar({
    super.key,
    required this.day,
    required this.timeZone,
    required this.bookings,
    required this.shifts,
    required this.branchId,
    required this.workers,
    required this.workerId,
    required this.onSelectBooking,
    required this.onSelectSlot,
  });

  final DateTime day;
  final String timeZone;
  final List<BookingRecord> bookings;
  final List<WorkingHoursRecord> shifts;
  final String branchId;
  final List<WorkerRecord> workers;
  final String? workerId;
  final ValueChanged<BookingRecord> onSelectBooking;
  final void Function(DateTime day, DateTime localStart, String? workerId)
  onSelectSlot;

  @override
  Widget build(BuildContext context) {
    final visibleWorkers = workers
        .where(
          (worker) =>
              workerId == null ||
              worker.id == workerId,
        )
        .where(
          (worker) =>
              worker.branchIds.isEmpty ||
              worker.branchIds.contains(branchId),
        )
        .toList();

    final visibleIds = visibleWorkers.map((worker) => worker.id).toSet();
    final visibleShifts = visibleWorkers.isEmpty
        ? shifts
        : shifts
              .where((shift) => visibleIds.contains(shift.workerId))
              .toList();

    final range = hourRangeFor(
      shifts: visibleShifts,
      days: [day],
      workerId: workerId,
      branchId: branchId,
    );

    final columns = visibleWorkers.isEmpty
        ? [
            CalendarColumn(
              day: day,
              title: 'Agenda',
              subtitle: 'Todas las reservas',
            ),
          ]
        : [
            for (final worker in visibleWorkers)
              CalendarColumn(
                day: day,
                title: worker.name,
                subtitle: visibleShifts.any(
                  (shift) =>
                      shift.workerId == worker.id &&
                      shift.weekday == backendWeekday(day),
                )
                    ? ''
                    : 'Sin horario',
                workerId: worker.id,
                color: workerColor(worker.colorHex),
              ),
          ];

    return CalendarGrid(
      columns: columns,
      range: range,
      bookings: bookings,
      timeZone: timeZone,
      onSelectBooking: onSelectBooking,
      onSelectSlot: onSelectSlot,
      columnWidth: 200,
    );
  }
}
```

- [ ] **Step 5: Ejecutar las pruebas y verificar**

```bash
cd mobile
flutter test test/calendar_widgets_test.dart
flutter analyze
```

Expected: PASS. Si `find.text('Cerrado')` no encuentra 6, revisar que la semana
de prueba tenga turno solo el lunes y que `backendWeekday` esté alineado con
el backend (lunes = 0).

- [ ] **Step 6: Commit (requiere autorización explícita de Carlos)**

```bash
git add mobile/lib/widgets/week_calendar.dart mobile/lib/widgets/day_calendar.dart mobile/test/calendar_widgets_test.dart
git commit -m "feat(mobile): add week and day calendar views"
```

---

### Task 6: Pantalla de agenda con vistas, filtros y alta desde hueco

**Files:**
- Modify: `mobile/lib/screens/agenda_screen.dart`
- Test: `mobile/test/agenda_calendar_screen_test.dart`

**Interfaces:**
- Consumes: `WeekCalendar`, `DayCalendar`, `CalendarView`, `weekDays`, `weekRangeLabel`, `longDayLabel`, `zonedDateTime`, `formatTimeIn`, `friendlyDayIn`, `AppState.workingHours`, `AppState.branchTimezone`.
- Produces: `AgendaScreen` con vistas Semana/Día/Lista, filtros de sucursal y trabajador, navegación temporal y creación desde un hueco. `_CreateBookingSheet` acepta `initialDay`, `initialTime`, `initialBranchId`, `initialWorkerId` y convierte la hora usando la zona de la sucursal.

- [ ] **Step 1: Escribir la prueba de pantalla**

`mobile/test/agenda_calendar_screen_test.dart`:

```dart
import 'package:agenda_mobile/core/theme.dart';
import 'package:agenda_mobile/data/api_client.dart';
import 'package:agenda_mobile/data/local_store.dart';
import 'package:agenda_mobile/data/session_store.dart';
import 'package:agenda_mobile/screens/agenda_screen.dart';
import 'package:agenda_mobile/state/app_state.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';
import 'package:timezone/data/latest.dart' as tzdata;
import 'package:timezone/timezone.dart' as tz;

class _AgendaApi extends ApiClient {
  _AgendaApi(this.bookingStart) : super(baseUrl: 'http://fake');

  final String bookingStart;

  @override
  Future<Map<String, dynamic>> getMap(
    String path, {
    Map<String, String>? query,
  }) async {
    if (path == '/api/v1/mobile/bootstrap/') {
      return {
        'user': {'email': 'owner@example.com', 'is_saas_admin': false},
        'company': {'id': 'a', 'name': 'Empresa A'},
        'membership': {'role': 'owner'},
        'permissions': ['bookings.read', 'bookings.write'],
        'features': {'bookings': true},
        'modules': {'agenda': true},
        'billing_state': 'legacy',
        'branches': [
          {'id': 'branch-1', 'name': 'Centro', 'timezone': 'America/Santiago'},
        ],
        'sync_resources': ['bookings', 'workers', 'working-hours'],
        'server_time': '2026-11-11T12:00:00Z',
        'companies': [
          {'id': 'a', 'name': 'Empresa A'},
        ],
        'worker': {'id': 'worker-1', 'name': 'Paula Rojas'},
      };
    }
    if (path == '/api/v1/mobile/sync/bookings/') {
      return {
        'results': [
          {
            'id': 'booking-1',
            'branch': 'branch-1',
            'worker': 'worker-1',
            'worker_name': 'Paula Rojas',
            'service_name': 'Corte',
            'customer_name': 'Ana Díaz',
            'status': 'scheduled',
            'start_at': bookingStart,
            'end_at': bookingStart,
            'public_code': 'ABC123',
          },
        ],
        'next_since': null,
        'next': null,
      };
    }
    if (path == '/api/v1/mobile/sync/workers/') {
      return {
        'results': [
          {
            'id': 'worker-1',
            'first_name': 'Paula',
            'last_name': 'Rojas',
            'branches': ['branch-1'],
            'color': '#10B981',
            'active': true,
          },
        ],
        'next_since': null,
        'next': null,
      };
    }
    if (path == '/api/v1/mobile/sync/working-hours/') {
      return {
        'results': [
          {
            'id': 'hours-1',
            'worker': 'worker-1',
            'branch': 'branch-1',
            'weekday': 0,
            'start_time': '09:00:00',
            'end_time': '18:00:00',
          },
        ],
        'next_since': null,
        'next': null,
      };
    }
    if (path == '/api/v1/mobile/notifications/') {
      return {'results': <dynamic>[], 'unread_count': 0};
    }
    return {'results': <dynamic>[], 'next_since': null, 'next': null};
  }

  @override
  Future<Map<String, dynamic>> postMap(
    String path, {
    Object? body,
    bool authenticated = true,
  }) async {
    if (path == '/api/v1/tenant-contexts/') {
      tenantContextId = 'ctx-a';
      return {'id': 'ctx-a', 'company': 'a'};
    }
    if (path == '/api/v1/mobile/operations/') {
      final operations = (body as Map)['operations'] as List? ?? [];
      return {
        'results': [
          for (final operation in operations)
            {
              'client_id': (operation as Map)['client_id'],
              'status': 'applied',
            },
        ],
      };
    }
    return <String, dynamic>{};
  }

  @override
  Future<List<Map<String, dynamic>>> getList(
    String path, {
    Map<String, String>? query,
  }) async {
    if (path == '/api/v1/companies/mine/') {
      return [
        {'id': 'a', 'name': 'Empresa A'},
      ];
    }
    return const [];
  }
}

class _Sessions extends SessionStore {
  @override
  Future<SessionSnapshot?> load() async => SessionSnapshot(
    baseUrl: 'http://fake',
    accessToken: 'access',
    refreshToken: 'refresh',
    companyId: 'a',
    companyName: 'Empresa A',
  );

  @override
  Future<void> save(SessionSnapshot value) async {}

  @override
  Future<void> clear() async {}
}

void main() {
  setUpAll(tzdata.initializeTimeZones);

  testWidgets('la agenda cambia entre Semana, Día y Lista', (tester) async {
    tester.view.physicalSize = const Size(900, 1200);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    final location = tz.getLocation('America/Santiago');
    final today = tz.TZDateTime.now(location);
    final start = tz.TZDateTime(
      location,
      today.year,
      today.month,
      today.day,
      10,
    ).toUtc().toIso8601String();

    final state = AppState(
      api: _AgendaApi(start),
      store: await LocalStore.memory(),
      sessions: _Sessions(),
    );
    await state.bootstrapApp();

    await tester.pumpWidget(
      ChangeNotifierProvider.value(
        value: state,
        child: MaterialApp(
          theme: buildAgendaTheme(),
          home: const AgendaScreen(),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Semana'), findsOneWidget);
    expect(find.text('Día'), findsOneWidget);
    expect(find.text('Lista'), findsOneWidget);
    expect(find.text('Paula Rojas'), findsOneWidget);

    await tester.tap(find.text('Día'));
    await tester.pumpAndSettle();
    expect(find.text('Paula Rojas'), findsOneWidget);

    await tester.tap(find.text('Lista'));
    await tester.pumpAndSettle();
    expect(find.textContaining('Corte'), findsWidgets);
  });
}
```

- [ ] **Step 2: Ejecutar la prueba y ver el fallo**

```bash
cd mobile
flutter test test/agenda_calendar_screen_test.dart
```

Expected: FAIL porque la pantalla no tiene las vistas y la hoja no acepta valores iniciales.

- [ ] **Step 3: Actualizar imports y estado de la pantalla**

En `mobile/lib/screens/agenda_screen.dart`, agregar imports:

```dart
import '../core/calendar.dart';
import '../widgets/day_calendar.dart';
import '../widgets/week_calendar.dart';
```

Reemplazar el estado inicial de `_AgendaScreenState` por:

```dart
  String _filter = 'Próximas';
  CalendarView _view = CalendarView.week;
  DateTime? _anchor;
  String? _branchId;
  String? _workerFilter;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final app = context.read<AppState>();
    _branchId ??= _firstBranchId(app);
  }

  String? _firstBranchId(AppState app) {
    final branches = app.bootstrap?.branches ?? const [];
    if (branches.isEmpty) return null;
    return '${branches.first['id']}';
  }

  void _moveAnchor(DateTime anchor, int direction) {
    final days = switch (_view) {
      CalendarView.week => 7 * direction,
      CalendarView.day => direction,
      CalendarView.list => 0,
    };
    setState(() {
      _anchor = DateTime(anchor.year, anchor.month, anchor.day + days);
    });
  }
```

- [ ] **Step 4: Reemplazar el método `build`**

Reemplazar el `build` actual de `_AgendaScreenState` por:

```dart
  @override
  Widget build(BuildContext context) {
    final app = context.watch<AppState>();
    final branches =
        app.bootstrap?.branches ?? const <Map<String, dynamic>>[];
    final branchIds = {for (final branch in branches) '${branch['id']}'};
    final branchId = _branchId != null && branchIds.contains(_branchId)
        ? _branchId
        : (branches.isEmpty ? null : '${branches.first['id']}');
    final timeZone = app.branchTimezone(branchId);
    final role = (app.bootstrap?.membership['role'] ?? '').toString();
    final selfWorkerId = app.bootstrap?.workerId;
    final isWorker = role == 'worker' && selfWorkerId != null;
    final workerFilter = isWorker ? selfWorkerId : _workerFilter;
    final branchWorkers = app.workers
        .where(
          (worker) =>
              branchId == null ||
              worker.branchIds.isEmpty ||
              worker.branchIds.contains(branchId),
        )
        .toList();
    final shifts = app.workingHours
        .where((shift) => shift.branchId == branchId)
        .toList();
    final branchBookings = branchId == null
        ? app.bookings
        : app.bookings
              .where((booking) => booking.branchId == branchId)
              .toList();
    final filtered = workerFilter == null
        ? branchBookings
        : branchBookings
              .where((booking) => booking.workerId == workerFilter)
              .toList();
    final today = localInZone(DateTime.now().toUtc(), timeZone);
    final anchor = _anchor ?? DateTime(today.year, today.month, today.day);
    final canWrite =
        app.can('bookings.write') || app.can('bookings.own.write');
    final showCalendar = app.moduleEnabled('agenda');

    return Scaffold(
      floatingActionButton: showCalendar && canWrite
          ? FloatingActionButton.extended(
              onPressed: () => _createBooking(context),
              icon: const Icon(Icons.add_rounded),
              label: const Text('Reservar'),
            )
          : null,
      body: SafeArea(
        child: Column(
          children: [
            ScreenHeader(
              title: 'Agenda',
              subtitle:
                  '${app.bootstrap?.companyName ?? ''} · ${longDayLabel(anchor)}',
              trailing: IconButton(
                tooltip: 'Sincronizar',
                onPressed: app.busy
                    ? null
                    : () => context.read<AppState>().refreshAll(),
                icon: const Icon(Icons.sync_rounded),
              ),
            ),
            const SyncBanner(),
            if (!showCalendar)
              const Expanded(
                child: EmptyState(
                  icon: Icons.lock_outline_rounded,
                  title: 'Agenda no incluida',
                  message:
                      'El plan actual no incluye reservas o tu rol no tiene acceso.',
                ),
              )
            else ...[
              _CalendarToolbar(
                view: _view,
                periodLabel: _view == CalendarView.week
                    ? weekRangeLabel(
                        weekDays(anchor).first,
                        weekDays(anchor).last,
                      )
                    : longDayLabel(anchor),
                branches: branches,
                branchId: branchId,
                onBranchChanged: (value) => setState(() {
                  _branchId = value;
                  _anchor = null;
                  _workerFilter = null;
                }),
                workers: branchWorkers,
                workerId: workerFilter,
                showWorkerFilter: !isWorker,
                onWorkerChanged: (value) =>
                    setState(() => _workerFilter = value),
                onViewChanged: (value) => setState(() => _view = value),
                onPrevious: () => _moveAnchor(anchor, -1),
                onToday: () => setState(
                  () => _anchor = DateTime(today.year, today.month, today.day),
                ),
                onNext: () => _moveAnchor(anchor, 1),
              ),
              Expanded(
                child: RefreshIndicator(
                  color: Theme.of(context).colorScheme.primary,
                  onRefresh: () => context.read<AppState>().refreshAll(),
                  child: _view == CalendarView.list
                      ? _listView(
                          context,
                          filtered,
                          today,
                          timeZone,
                          canWrite,
                        )
                      : Padding(
                          padding: const EdgeInsets.symmetric(horizontal: 12),
                          child: _view == CalendarView.week
                              ? WeekCalendar(
                                  anchor: anchor,
                                  timeZone: timeZone,
                                  bookings: filtered,
                                  shifts: shifts,
                                  branchId: branchId ?? '',
                                  workerId: workerFilter,
                                  onSelectBooking: (booking) =>
                                      _openBooking(context, booking),
                                  onSelectSlot: (day, start, workerId) =>
                                      _createFromSlot(
                                        context,
                                        day,
                                        start,
                                        workerId,
                                        branchId,
                                      ),
                                )
                              : DayCalendar(
                                  day: anchor,
                                  timeZone: timeZone,
                                  bookings: filtered,
                                  shifts: shifts,
                                  branchId: branchId ?? '',
                                  workers: branchWorkers,
                                  workerId: workerFilter,
                                  onSelectBooking: (booking) =>
                                      _openBooking(context, booking),
                                  onSelectSlot: (day, start, workerId) =>
                                      _createFromSlot(
                                        context,
                                        day,
                                        start,
                                        workerId,
                                        branchId,
                                      ),
                                ),
                        ),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
```

- [ ] **Step 5: Implementar la vista Lista y la barra de filtros**

Agregar dentro de `_AgendaScreenState`, después de `build`:

```dart
  Widget _listView(
    BuildContext context,
    List<BookingRecord> bookings,
    DateTime today,
    String timeZone,
    bool canWrite,
  ) {
    final now = DateTime.now().toUtc();
    final visible = switch (_filter) {
      'Hoy' => bookings
          .where(
            (booking) =>
                sameDay(localInZone(booking.startAt!, timeZone), today),
          )
          .toList(),
      'Todas' => bookings,
      _ => bookings
          .where(
            (booking) =>
                booking.startAt!.isAfter(
                  now.subtract(const Duration(hours: 2)),
                ) &&
                booking.isActive,
          )
          .toList(),
    };

    return ListView(
      physics: const AlwaysScrollableScrollPhysics(),
      padding: const EdgeInsets.only(bottom: 120),
      children: [
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 20),
          child: Row(
            children: [
              _Metric(
                value: '${visible.where((b) => b.isActive).length}',
                label: 'ACTIVAS',
              ),
              const SizedBox(width: 10),
              _Metric(
                value:
                    '${bookings.where((b) => b.startAt!.isAfter(now) && b.isActive).length}',
                label: 'PRÓXIMAS',
              ),
              const SizedBox(width: 10),
              _Metric(
                value:
                    '${bookings.where((b) => sameDay(localInZone(b.startAt!, timeZone), today) && b.isActive).length}',
                label: 'HOY',
              ),
            ],
          ),
        ),
        Padding(
          padding: const EdgeInsets.fromLTRB(20, 18, 20, 4),
          child: Wrap(
            spacing: 8,
            children: [
              for (final option in const ['Próximas', 'Hoy', 'Todas'])
                ChoiceChip(
                  label: Text(option),
                  selected: _filter == option,
                  onSelected: (_) => setState(() => _filter = option),
                  selectedColor: Theme.of(context).colorScheme.secondary,
                  backgroundColor: context.palette.surface,
                  side: BorderSide(color: context.palette.border),
                  labelStyle: TextStyle(
                    color: _filter == option
                        ? Theme.of(context).colorScheme.onSecondary
                        : context.palette.muted,
                    fontWeight: FontWeight.w700,
                  ),
                ),
            ],
          ),
        ),
        if (visible.isEmpty)
          EmptyState(
            icon: Icons.event_available_outlined,
            title: 'Sin reservas',
            message:
                'No hay reservas para este filtro. Desliza hacia abajo para sincronizar.',
            action: canWrite
                ? OutlinedButton(
                    onPressed: () => _createBooking(context),
                    child: const Text('Crear reserva'),
                  )
                : null,
          )
        else
          ..._grouped(visible, timeZone),
      ],
    );
  }
```

Agregar al final del archivo, antes de `_Metric`:

```dart
class _CalendarToolbar extends StatelessWidget {
  const _CalendarToolbar({
    required this.view,
    required this.periodLabel,
    required this.branches,
    required this.branchId,
    required this.onBranchChanged,
    required this.workers,
    required this.workerId,
    required this.showWorkerFilter,
    required this.onWorkerChanged,
    required this.onViewChanged,
    required this.onPrevious,
    required this.onToday,
    required this.onNext,
  });

  final CalendarView view;
  final String periodLabel;
  final List<Map<String, dynamic>> branches;
  final String? branchId;
  final ValueChanged<String> onBranchChanged;
  final List<WorkerRecord> workers;
  final String? workerId;
  final bool showWorkerFilter;
  final ValueChanged<String?> onWorkerChanged;
  final ValueChanged<CalendarView> onViewChanged;
  final VoidCallback onPrevious;
  final VoidCallback onToday;
  final VoidCallback onNext;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 4, 20, 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SegmentedButton<CalendarView>(
            segments: const [
              ButtonSegment(
                value: CalendarView.week,
                label: Text('Semana'),
              ),
              ButtonSegment(
                value: CalendarView.day,
                label: Text('Día'),
              ),
              ButtonSegment(
                value: CalendarView.list,
                label: Text('Lista'),
              ),
            ],
            selected: {view},
            onSelectionChanged: (selection) => onViewChanged(selection.first),
            showSelectedIcon: false,
          ),
          if (view != CalendarView.list) ...[
            const SizedBox(height: 4),
            Row(
              children: [
                IconButton(
                  onPressed: onPrevious,
                  tooltip: 'Anterior',
                  icon: const Icon(Icons.chevron_left_rounded),
                ),
                Expanded(
                  child: Text(
                    periodLabel,
                    textAlign: TextAlign.center,
                    style: const TextStyle(fontWeight: FontWeight.w700),
                  ),
                ),
                IconButton(
                  onPressed: onToday,
                  tooltip: 'Hoy',
                  icon: const Icon(Icons.today_rounded),
                ),
                IconButton(
                  onPressed: onNext,
                  tooltip: 'Siguiente',
                  icon: const Icon(Icons.chevron_right_rounded),
                ),
              ],
            ),
          ],
          const SizedBox(height: 8),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              SizedBox(
                width: 190,
                child: DropdownButtonFormField<String>(
                  key: ValueKey('branch-$branchId'),
                  initialValue: branchId,
                  decoration: const InputDecoration(
                    labelText: 'Sucursal',
                    isDense: true,
                  ),
                  items: [
                    for (final branch in branches)
                      DropdownMenuItem(
                        value: '${branch['id']}',
                        child: Text('${branch['name']}'),
                      ),
                  ],
                  onChanged: (value) {
                    if (value != null) onBranchChanged(value);
                  },
                ),
              ),
              if (showWorkerFilter)
                SizedBox(
                  width: 190,
                  child: DropdownButtonFormField<String?>(
                    key: ValueKey('worker-$workerId'),
                    initialValue: workerId,
                    decoration: const InputDecoration(
                      labelText: 'Trabajador',
                      isDense: true,
                    ),
                    items: [
                      const DropdownMenuItem<String?>(
                        value: null,
                        child: Text('Todos'),
                      ),
                      for (final worker in workers)
                        DropdownMenuItem<String?>(
                          value: worker.id,
                          child: Text(worker.name),
                        ),
                    ],
                    onChanged: onWorkerChanged,
                  ),
                ),
            ],
          ),
        ],
      ),
    );
  }
}
```

- [ ] **Step 6: Ajustar la creación de reservas**

Reemplazar `_createBooking`, `_grouped` y `_BookingCard` para usar la zona de
la sucursal, y agregar `_createFromSlot`.

`_createBooking`:

```dart
  Future<void> _createBooking(BuildContext context) => _openCreateSheet(context);
```

Agregar:

```dart
  Future<void> _createFromSlot(
    BuildContext context,
    DateTime day,
    DateTime localStart,
    String? workerId,
    String? branchId,
  ) {
    final app = context.read<AppState>();
    final role = (app.bootstrap?.membership['role'] ?? '').toString();
    final fallbackWorker = role == 'worker'
        ? app.bootstrap?.workerId
        : _workerFilter;
    return _openCreateSheet(
      context,
      day: day,
      time: TimeOfDay(hour: localStart.hour, minute: localStart.minute),
      branchId: branchId,
      workerId: workerId ?? fallbackWorker,
    );
  }

  Future<void> _openCreateSheet(
    BuildContext context, {
    DateTime? day,
    TimeOfDay? time,
    String? branchId,
    String? workerId,
  }) async {
    final app = context.read<AppState>();
    if (app.services.isEmpty ||
        app.workers.isEmpty ||
        app.customers.isEmpty ||
        (app.bootstrap?.branches.isEmpty ?? true)) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(
            'Sincroniza los catálogos antes de crear una reserva (servicios, profesionales y clientes).',
          ),
        ),
      );
      return;
    }
    final payload = await showModalBottomSheet<Map<String, dynamic>>(
      context: context,
      isScrollControlled: true,
      backgroundColor: context.palette.surface,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      builder: (_) => _CreateBookingSheet(
        initialDay: day,
        initialTime: time,
        initialBranchId: branchId,
        initialWorkerId: workerId,
      ),
    );
    if (payload == null || !context.mounted) return;
    await _queue(context, 'booking.create', payload, title: 'Reserva creada');
  }
```

`_grouped`:

```dart
  List<Widget> _grouped(List<BookingRecord> bookings, String timeZone) {
    final groups = <String, List<BookingRecord>>{};
    for (final booking in bookings) {
      final key = friendlyDayIn(booking.startAt!, timeZone);
      groups.putIfAbsent(key, () => []).add(booking);
    }
    final widgets = <Widget>[];
    for (final entry in groups.entries) {
      widgets.add(SectionLabel(entry.key));
      for (final booking in entry.value) {
        widgets.add(
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 0, 20, 10),
            child: _BookingCard(
              booking: booking,
              timeZone: timeZone,
              onTap: () => _openBooking(context, booking),
            ),
          ),
        );
      }
    }
    return widgets;
  }
```

`_BookingCard`: cambiar constructor y usos de hora:

```dart
class _BookingCard extends StatelessWidget {
  const _BookingCard({
    required this.booking,
    required this.timeZone,
    required this.onTap,
  });

  final BookingRecord booking;
  final String timeZone;
  final VoidCallback onTap;
```

Dentro de `build`, reemplazar:

```dart
                Text(
                  formatTime(booking.startAt!),
                  ...
                ),
                Text(
                  formatTime(booking.endAt ?? booking.startAt!),
                  ...
                ),
```

por:

```dart
                Text(
                  formatTimeIn(booking.startAt!, timeZone),
                  ...
                ),
                Text(
                  formatTimeIn(booking.endAt ?? booking.startAt!, timeZone),
                  ...
                ),
```

- [ ] **Step 7: Extender la hoja de creación**

Reemplazar el constructor y `initState` de `_CreateBookingSheet`:

```dart
class _CreateBookingSheet extends StatefulWidget {
  const _CreateBookingSheet({
    this.initialDay,
    this.initialTime,
    this.initialBranchId,
    this.initialWorkerId,
  });

  final DateTime? initialDay;
  final TimeOfDay? initialTime;
  final String? initialBranchId;
  final String? initialWorkerId;

  @override
  State<_CreateBookingSheet> createState() => _CreateBookingSheetState();
}

class _CreateBookingSheetState extends State<_CreateBookingSheet> {
  final _notes = TextEditingController();
  late DateTime _day;
  late TimeOfDay _time;
  String? _serviceId;
  String? _workerId;
  String? _customerId;
  String? _branchId;
  String? _error;

  @override
  void initState() {
    super.initState();
    final app = context.read<AppState>();
    final now = widget.initialDay ??
        DateTime.now().add(const Duration(days: 1));
    _day = DateTime(now.year, now.month, now.day);
    _time = widget.initialTime ?? const TimeOfDay(hour: 10, minute: 0);
    _serviceId = app.services.isEmpty ? null : app.services.first.id;
    _workerId = widget.initialWorkerId ??
        (app.workers.isEmpty ? null : app.workers.first.id);
    _customerId = app.customers.isEmpty ? null : app.customers.first.id;
    final branches = app.bootstrap?.branches ?? const [];
    _branchId = widget.initialBranchId ??
        (branches.isEmpty ? null : '${branches.first['id']}');
  }
```

Reemplazar la construcción de `start` en `_submit`:

```dart
    final app = context.read<AppState>();
    final zone = app.branchTimezone(_branchId);
    final start = zonedDateTime(
      zone,
      DateTime(
        _day.year,
        _day.month,
        _day.day,
        _time.hour,
        _time.minute,
      ),
    );
```

- [ ] **Step 8: Ejecutar la prueba y verificar**

```bash
cd mobile
flutter test test/agenda_calendar_screen_test.dart test/calendar_widgets_test.dart
flutter analyze
```

Expected: PASS y sin errores. Si `find.text('Paula Rojas')` encuentra dos
widgets (columna y filtro), usar `find.text('Paula Rojas').first` en el toque de
vista Día y mantener `findsWidgets` en la aserción.

- [ ] **Step 9: Commit (requiere autorización explícita de Carlos)**

```bash
git add mobile/lib/screens/agenda_screen.dart mobile/test/agenda_calendar_screen_test.dart
git commit -m "feat(mobile): add week, day and list agenda views with slot booking"
```

---

### Task 7: Verificación completa y handoff web

**Files:**
- No se crean archivos nuevos.
- Verificación de `backend/` y `mobile/`.
- Referencia: `docs/superpowers/plans/2026-11-11-web-admin-operador.md`, tarea 19B.

**Interfaces:**
- Consumes: todo lo anterior.
- Produces: evidencia de pruebas y la lista de validación manual que Carlos puede repetir.

- [ ] **Step 1: Ejecutar la suite backend dirigida**

```bash
cd backend
python manage.py test apps.mobile.tests.test_sync apps.mobile.tests.test_bootstrap apps.mobile.tests.test_operations -v 2
```

Expected: PASS.

- [ ] **Step 2: Ejecutar análisis y pruebas Flutter**

```bash
cd mobile
flutter pub get
flutter analyze
flutter test
```

Expected: `flutter analyze` sin errores y toda la suite PASS.

- [ ] **Step 3: Validación manual con datos locales**

Con el backend local y la app Flutter:

1. Abrir Agenda: debe iniciar en Semana con la semana actual, lunes a domingo,
   en la zona de la sucursal.
2. Verificar que el eje horario coincide con los turnos cargados; si no hay
   turnos, debe mostrar 08:00–20:00.
3. Cambiar a Día: una columna por trabajador activo; `Sin horario` cuando
   corresponda.
4. Cambiar a Lista: la agrupación y las tarjetas existentes siguen funcionando.
5. Tocar una reserva: abre el detalle con cancelar/reprogramar según permisos.
6. Tocar un hueco: abre el formulario con fecha, hora y sucursal; en Día también
   con el trabajador de la columna.
7. Crear una reserva desde el hueco, sincronizar y verla en la grilla.
8. Cambiar de sucursal: se recalculan rango, días y reservas.
9. Con rol trabajador: el selector de trabajador no aparece y solo se ven sus
   reservas y turnos.
10. Activar modo avión: la agenda cacheada se muestra; crear/cancelar quedan en
    la cola y se aplican al reconectar.
11. Cambiar de empresa: no se muestran reservas ni turnos de la empresa
    anterior.
12. Revisar claro/oscuro y una pantalla angosta: el eje queda fijo y los días se
    desplazan horizontalmente sin recortes.

- [ ] **Step 4: Confirmar el handoff web**

Verificar que `docs/superpowers/plans/2026-11-11-web-admin-operador.md` contiene
la tarea 19B con:

- `agendaLayout.hourBounds` calculado desde horarios y respaldo 08:00–20:00.
- Eje horario en la vista Semana con siete columnas.
- `onSelectSlot` en `AgendaCalendar`.
- `BookingCreateDialog` con `initialSlot` y consulta de disponibilidad.
- Pruebas Vitest y E2E de creación desde hueco.

No se modifica la web en este plan.

- [ ] **Step 5: Commit final (requiere autorización explícita de Carlos)**

No hay archivos nuevos que commitear en este paso. Si Carlos autoriza cerrar
la fase:

```bash
git status
```

Expected: solo quedan cambios ya commiteados en las tareas 1–6; cualquier
cambio pendiente se revisa con Carlos antes de commitear.
