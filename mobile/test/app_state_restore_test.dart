import 'package:agenda_mobile/data/api_client.dart';
import 'package:agenda_mobile/data/local_store.dart';
import 'package:agenda_mobile/data/session_store.dart';
import 'package:agenda_mobile/state/app_state.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';

const _staleCompanyId = 'borrada';

Map<String, dynamic> _bootstrapPayload({
  String companyId = 'c1',
  String companyName = 'Empresa Activa',
  List<Map<String, dynamic>> companies = const [],
}) => {
  'user': {
    'email': 'operadora@example.com',
    'first_name': 'Operadora',
    'is_saas_admin': true,
  },
  'company': {'id': companyId, 'name': companyName, 'slug': companyName},
  'membership': {'role': 'owner'},
  'permissions': <String>[],
  'features': <String, dynamic>{},
  'modules': <String, dynamic>{},
  'billing_state': 'legacy',
  'branches': <dynamic>[],
  'sync_resources': <dynamic>[],
  'companies': companies,
};

class _StaleCompanyApi extends ApiClient {
  _StaleCompanyApi({
    required this.companies,
    this.serverOffline = false,
  }) : super(baseUrl: 'http://fake');

  final List<Map<String, dynamic>> companies;
  final bool serverOffline;
  final List<String> calls = [];

  @override
  Future<Map<String, dynamic>> getMap(
    String path, {
    Map<String, String>? query,
  }) async {
    calls.add('GET $path');
    if (serverOffline) {
      throw ApiException(0, 'No se pudo conectar con el servidor.');
    }
    if (path == '/api/v1/mobile/bootstrap/') {
      if (tenantContextId == 'stale') {
        throw ApiException(403, 'Selecciona una empresa a la que tengas acceso.');
      }
      return _bootstrapPayload(
        companyId: '${companies.first['id']}',
        companyName: '${companies.first['name']}',
        companies: companies,
      );
    }
    if (path == '/api/v1/mobile/notifications/') {
      return {
        'results': <dynamic>[],
        'unread_count': 0,
      };
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
      if (company == _staleCompanyId) {
        throw ApiException(400, 'Invalid pk: la empresa no existe.');
      }
      tenantContextId = 'fresh';
      return {'id': 'fresh', 'company': company};
    }
    if (path == '/api/v1/mobile/operations/') {
      return {'results': <dynamic>[]};
    }
    return <String, dynamic>{};
  }

  @override
  Future<List<Map<String, dynamic>>> getList(
    String path, {
    Map<String, String>? query,
  }) async {
    calls.add('GET $path');
    if (path == '/api/v1/companies/mine/') return companies;
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

SessionSnapshot _staleSession() => SessionSnapshot(
  baseUrl: 'http://fake',
  accessToken: 'access',
  refreshToken: 'refresh',
  contextId: 'stale',
  companyId: _staleCompanyId,
  companyName: 'Empresa Borrada',
);

Future<AppState> _restore(_StaleCompanyApi api, _MemorySessions sessions) async {
  final store = await LocalStore.memory();
  await store.saveMeta(
    'bootstrap:$_staleCompanyId',
    _bootstrapPayload(companyId: _staleCompanyId, companyName: 'Empresa Borrada'),
  );
  return AppState(api: api, store: store, sessions: sessions);
}

void main() {
  test(
    'recreates the context with the accessible company when the saved one is gone',
    () async {
      final api = _StaleCompanyApi(
        companies: [
          {'id': 'c1', 'name': 'Empresa Activa', 'slug': 'empresa-activa'},
        ],
      );
      final sessions = _MemorySessions(_staleSession());
      final state = await _restore(api, sessions);

      await state.bootstrapApp();

      expect(state.status, AppStatus.ready);
      expect(state.offline, isFalse);
      expect(state.syncMessage, isNull);
      expect(state.bootstrap?.companyName, 'Empresa Activa');
      expect(api.tenantContextId, 'fresh');
      expect(sessions.snapshot?.contextId, 'fresh');
      expect(sessions.snapshot?.companyId, 'c1');
    },
  );

  test('returns to the company chooser when the saved company is gone', () async {
    final api = _StaleCompanyApi(
      companies: [
        {'id': 'c1', 'name': 'Empresa Activa', 'slug': 'empresa-activa'},
        {'id': 'c2', 'name': 'Otra Empresa', 'slug': 'otra-empresa'},
      ],
    );
    final sessions = _MemorySessions(_staleSession());
    final state = await _restore(api, sessions);

    await state.bootstrapApp();

    expect(state.status, AppStatus.chooseCompany);
    expect(state.offline, isFalse);
    expect(state.syncMessage, isNull);
    expect(api.tenantContextId, isNull);
    expect(sessions.snapshot?.companyId, isNull);
    expect(sessions.snapshot?.contextId, isNull);
    expect(sessions.snapshot?.isSaasAdmin, isTrue);
  });

  test('keeps the offline notice when the server is unreachable', () async {
    final api = _StaleCompanyApi(
      companies: [
        {'id': 'c1', 'name': 'Empresa Activa', 'slug': 'empresa-activa'},
      ],
      serverOffline: true,
    );
    final sessions = _MemorySessions(_staleSession());
    final state = await _restore(api, sessions);

    await state.bootstrapApp();

    expect(state.status, AppStatus.ready);
    expect(state.offline, isTrue);
    expect(state.syncMessage, 'Sin conexión: mostrando datos guardados.');
  });

  test('saving a session without a company clears the stale keys', () async {
    final storage = _FakeSecureStorage();
    final store = SessionStore(storage: storage);
    await store.save(_staleSession());

    await store.save(
      SessionSnapshot(
        baseUrl: 'http://fake',
        accessToken: 'access',
        refreshToken: 'refresh',
      ),
    );

    final loaded = await store.load();
    expect(loaded?.contextId, isNull);
    expect(loaded?.companyId, isNull);
    expect(loaded?.companyName, isNull);
    expect(loaded?.isSaasAdmin, isFalse);
  });
}

class _FakeSecureStorage extends FlutterSecureStorage {
  final Map<String, String> values = {};

  @override
  Future<String?> read({
    required String key,
    AppleOptions? iOptions,
    AndroidOptions? aOptions,
    LinuxOptions? lOptions,
    WebOptions? webOptions,
    AppleOptions? mOptions,
    WindowsOptions? wOptions,
  }) async => values[key];

  @override
  Future<void> write({
    required String key,
    required String? value,
    AppleOptions? iOptions,
    AndroidOptions? aOptions,
    LinuxOptions? lOptions,
    WebOptions? webOptions,
    AppleOptions? mOptions,
    WindowsOptions? wOptions,
  }) async {
    if (value == null) {
      values.remove(key);
    } else {
      values[key] = value;
    }
  }

  @override
  Future<void> deleteAll({
    AppleOptions? iOptions,
    AndroidOptions? aOptions,
    LinuxOptions? lOptions,
    WebOptions? webOptions,
    AppleOptions? mOptions,
    WindowsOptions? wOptions,
  }) async {
    values.clear();
  }
}
