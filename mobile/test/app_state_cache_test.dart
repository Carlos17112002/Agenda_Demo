import 'package:agenda_mobile/data/api_client.dart';
import 'package:agenda_mobile/data/local_store.dart';
import 'package:agenda_mobile/data/session_store.dart';
import 'package:agenda_mobile/state/app_state.dart';
import 'package:flutter_test/flutter_test.dart';

const _companies = [
  {'id': 'a', 'name': 'Empresa A'},
  {'id': 'b', 'name': 'Empresa B'},
];

Map<String, dynamic> _bootstrap(String companyId) => {
  'user': {'email': 'operadora@example.com', 'is_saas_admin': false},
  'company': {
    'id': companyId,
    'name': companyId == 'a' ? 'Empresa A' : 'Empresa B',
  },
  'membership': {'role': 'owner'},
  'permissions': <String>[],
  'features': <String, dynamic>{},
  'modules': <String, dynamic>{},
  'billing_state': 'legacy',
  'branches': <dynamic>[],
  'sync_resources': ['bookings'],
  'server_time': '2026-01-01T00:00:00Z',
  'companies': _companies,
};

class _CompanySwitchApi extends ApiClient {
  _CompanySwitchApi({this.rejectOperations = false})
    : super(baseUrl: 'http://fake');

  final bool rejectOperations;
  final Map<String, String> _companyByContext = {};
  final List<String> calls = [];
  int _sequence = 0;

  String? get _companyId => _companyByContext[tenantContextId];

  int countCalls(String call) => calls.where((entry) => entry == call).length;

  @override
  Future<Map<String, dynamic>> getMap(
    String path, {
    Map<String, String>? query,
  }) async {
    calls.add('GET $path');
    if (path == '/api/v1/mobile/bootstrap/') {
      final companyId = _companyId;
      if (companyId == null) {
        throw ApiException(403, 'Selecciona una empresa a la que tengas acceso.');
      }
      return _bootstrap(companyId);
    }
    if (path == '/api/v1/mobile/sync/bookings/') {
      return {
        'results': _companyId == 'a'
            ? [
                {
                  'id': 'booking-a',
                  'start_at': '2026-01-02T10:00:00Z',
                  'end_at': '2026-01-02T11:00:00Z',
                  'status': 'scheduled',
                  'service_name': 'Corte',
                },
              ]
            : <dynamic>[],
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
    calls.add('POST $path');
    if (path == '/api/v1/tenant-contexts/') {
      final company = '${(body as Map)['company']}';
      final context = 'ctx-$company-${_sequence++}';
      _companyByContext[context] = company;
      tenantContextId = context;
      return {'id': context, 'company': company};
    }
    if (path == '/api/v1/mobile/operations/') {
      final operations = (body as Map)['operations'] as List? ?? [];
      return {
        'results': [
          for (final operation in operations)
            {
              'client_id': (operation as Map)['client_id'],
              'status': rejectOperations ? 'conflict' : 'applied',
              if (rejectOperations) 'error': 'No corresponde a esta empresa.',
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
    calls.add('GET $path');
    if (path == '/api/v1/companies/mine/') return _companies;
    return const [];
  }
}

class _MemorySessions extends SessionStore {
  _MemorySessions(this.snapshot);

  SessionSnapshot? snapshot;

  @override
  Future<SessionSnapshot?> load() async => snapshot;

  @override
  Future<void> save(SessionSnapshot value) async => snapshot = value;

  @override
  Future<void> clear() async => snapshot = null;
}

SessionSnapshot _session(String companyId) => SessionSnapshot(
  baseUrl: 'http://fake',
  accessToken: 'access',
  refreshToken: 'refresh',
  companyId: companyId,
  companyName: companyId == 'a' ? 'Empresa A' : 'Empresa B',
);

void main() {
  test('selecting another company switches the tenant context', () async {
    final store = await LocalStore.memory();
    final api = _CompanySwitchApi();
    final sessions = _MemorySessions(_session('a'));
    final state = AppState(api: api, store: store, sessions: sessions);

    await state.bootstrapApp();
    expect(state.bootstrap?.companyName, 'Empresa A');

    await state.switchCompany();
    await state.selectCompany({'id': 'b', 'name': 'Empresa B'});

    expect(state.status, AppStatus.ready);
    expect(state.bootstrap?.companyName, 'Empresa B');
    expect(api.tenantContextId, startsWith('ctx-b-'));
    expect(sessions.snapshot?.companyId, 'b');
  });

  test('switching company hides the previous company bookings', () async {
    final store = await LocalStore.memory();
    final api = _CompanySwitchApi();
    final state = AppState(
      api: api,
      store: store,
      sessions: _MemorySessions(_session('a')),
    );

    await state.bootstrapApp();
    expect(state.bookings, hasLength(1));

    await state.switchCompany();
    await state.selectCompany({'id': 'b', 'name': 'Empresa B'});

    expect(state.status, AppStatus.ready);
    expect(state.bookings, isEmpty);
  });

  test('a restart with another company ignores the cached bookings', () async {
    final store = await LocalStore.memory();
    final first = AppState(
      api: _CompanySwitchApi(),
      store: store,
      sessions: _MemorySessions(_session('a')),
    );
    await first.bootstrapApp();
    expect(first.bookings, hasLength(1));

    final second = AppState(
      api: _CompanySwitchApi(),
      store: store,
      sessions: _MemorySessions(_session('b')),
    );
    await second.bootstrapApp();

    expect(second.status, AppStatus.ready);
    expect(second.bookings, isEmpty);
  });

  test('pending operations are not shown or flushed under another company', () async {
    final store = await LocalStore.memory();
    final api = _CompanySwitchApi(rejectOperations: true);
    final state = AppState(
      api: api,
      store: store,
      sessions: _MemorySessions(_session('a')),
    );

    await state.bootstrapApp();
    await state.outbox.enqueue('booking.create', {'service': 's1'});

    await state.switchCompany();
    await state.selectCompany({'id': 'b', 'name': 'Empresa B'});

    expect(state.outboxItems, isEmpty);
    expect(api.countCalls('POST /api/v1/mobile/operations/'), 0);
  });
}
