import 'package:agenda_mobile/data/api_client.dart';
import 'package:agenda_mobile/data/local_store.dart';
import 'package:agenda_mobile/data/models.dart';
import 'package:agenda_mobile/state/app_state.dart';
import 'package:flutter_test/flutter_test.dart';

class _RecordingApi extends ApiClient {
  _RecordingApi() : super(baseUrl: 'http://fake');

  final List<String> calls = [];

  @override
  Future<Map<String, dynamic>> getMap(
    String path, {
    Map<String, String>? query,
  }) async {
    calls.add('GET $path');
    if (path.contains('/mobile/notifications/')) {
      return {
        'results': <dynamic>[],
        'unread_count': 0,
      };
    }
    return {
      'results': <dynamic>[],
      'next_since': null,
      'next': null,
    };
  }

  @override
  Future<Map<String, dynamic>> postMap(
    String path, {
    Object? body,
    bool authenticated = true,
  }) async {
    calls.add('POST $path');
    final operations = (body as Map)['operations'] as List;
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
}

void main() {
  test('refreshAll applies queued operations before syncing resources', () async {
    final store = await LocalStore.memory();
    final api = _RecordingApi();
    final state = AppState(api: api, store: store);
    state.status = AppStatus.ready;
    state.activeCompanyId = 'c1';
    state.outbox.companyId = 'c1';
    state.bootstrap = Bootstrap.fromJson({
      'sync_resources': ['products'],
    });
    await state.outbox.enqueue('inventory.movement', {'product': 'p1'});

    await state.refreshAll();

    expect(api.calls.first, 'POST /api/v1/mobile/operations/');
    expect(api.calls, contains('GET /api/v1/mobile/sync/products/'));
    expect(await state.outbox.all(), isEmpty);
  });
}
