import 'package:agenda_mobile/data/branch_selection.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  final branches = [
    {'id': 'a', 'name': 'Centro', 'active': true},
    {'id': 'b', 'name': 'Norte', 'active': false},
  ];

  test('prefiere el local asignado cuando está activo', () {
    expect(initialBranchId(branches, 'a'), 'a');
  });

  test('ignora el local asignado si está inactivo', () {
    expect(initialBranchId(branches, 'b'), 'a');
  });

  test('usa el primer local activo sin preferencia', () {
    expect(initialBranchId(branches, null), 'a');
  });

  test('devuelve null sin locales', () {
    expect(initialBranchId(const [], 'a'), isNull);
  });
}
