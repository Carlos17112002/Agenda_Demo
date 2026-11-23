import 'package:agenda_mobile/data/api_client.dart';
import 'package:agenda_mobile/data/local_store.dart';
import 'package:agenda_mobile/data/session_store.dart';
import 'package:agenda_mobile/state/app_state.dart';
import 'package:flutter_test/flutter_test.dart';

Map<String, dynamic> _bootstrap({bool mustChange = false}) => {
  'user': {'email': 'persona@example.com', 'must_change_password': mustChange},
  'company': {'id': 'c1', 'name': 'Demo'},
  'membership': {'role': 'owner'},
  'permissions': <String>[],
  'features': <String, dynamic>{},
  'modules': <String, dynamic>{},
  'billing_state': 'legacy',
  'subscription': null,
  'branches': <dynamic>[],
  'sync_resources': <dynamic>[],
  'server_time': '',
  'companies': <dynamic>[],
};

class _PasswordApi extends ApiClient {
  _PasswordApi() : super(baseUrl: 'http://fake');

  final List<Map<String, dynamic>> posted = [];

  @override
  Future<Map<String, dynamic>> getMap(
    String path, {
    Map<String, String>? query,
  }) async {
    return _bootstrap();
  }

  @override
  Future<Map<String, dynamic>> postMap(
    String path, {
    Object? body,
    bool authenticated = true,
  }) async {
    posted.add({'path': path, 'body': body});
    return {
      'access': 'new-access',
      'refresh': 'new-refresh',
      'must_change_password': false,
    };
  }
}

class _MemorySessions extends SessionStore {
  SessionSnapshot? snapshot;

  @override
  Future<SessionSnapshot?> load() async => snapshot;

  @override
  Future<void> save(SessionSnapshot value) async => snapshot = value;

  @override
  Future<void> clear() async => snapshot = null;
}

void main() {
  test('cambia la clave, guarda los tokens y limpia el flag', () async {
    final api = _PasswordApi();
    final sessions = _MemorySessions();
    final state = AppState(
      api: api,
      store: await LocalStore.memory(),
      sessions: sessions,
    );

    final ok = await state.changePassword(
      currentPassword: 'Vieja-Clave-123!',
      newPassword: 'Nueva-Clave-456!',
    );

    expect(ok, isTrue);
    expect(api.posted.single['path'], '/api/v1/auth/password/change/');
    expect(
      (api.posted.single['body'] as Map)['new_password'],
      'Nueva-Clave-456!',
    );
    expect(api.accessToken, 'new-access');
    expect(sessions.snapshot?.refreshToken, 'new-refresh');
    expect(state.bootstrap?.mustChangePassword, isFalse);
  });
}
