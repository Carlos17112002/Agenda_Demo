import 'package:agenda_mobile/data/models.dart';
import 'package:flutter_test/flutter_test.dart';

Map<String, dynamic> _payload({bool mustChange = true}) => {
      'user': {'email': 'persona@example.com', 'must_change_password': mustChange},
      'company': {'id': 'c1', 'name': 'Demo'},
      'membership': {
        'role': 'reception',
        'default_branch': {'id': 'branch-2', 'name': 'Centro'},
      },
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

void main() {
  test('expone el flag de cambio de clave', () {
    final bootstrap = Bootstrap.fromJson(_payload());
    expect(bootstrap.mustChangePassword, isTrue);
  });

  test('expone el local predeterminado', () {
    final bootstrap = Bootstrap.fromJson(_payload());
    expect(bootstrap.defaultBranchId, 'branch-2');
    expect(bootstrap.defaultBranch?['name'], 'Centro');
  });

  test('sin local predeterminado devuelve null', () {
    final payload = _payload();
    payload['membership'] = {'role': 'owner'};
    expect(Bootstrap.fromJson(payload).defaultBranchId, isNull);
  });
}
