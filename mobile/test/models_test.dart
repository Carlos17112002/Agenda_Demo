import 'package:agenda_mobile/data/models.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

Map<String, dynamic> _bootstrapJson() => {
  'server_time': '2026-11-11T12:00:00Z',
  'user': {
    'id': 'u1',
    'email': 'ana@demo.cl',
    'first_name': 'Ana',
    'last_name': 'Díaz',
  },
  'company': {'id': 'c1', 'name': 'Estudio Rojo', 'slug': 'estudio-rojo'},
  'membership': {'role': 'worker', 'role_display': 'Trabajador'},
  'worker': {'id': 'w1', 'name': 'Ana Díaz'},
  'permissions': ['bookings.own.read', 'catalog.read'],
  'features': {'bookings': true, 'inventory': false},
  'modules': {'agenda': true, 'inventory': false, 'customers': false},
  'billing_state': 'usable',
  'subscription': {
    'plan': {'code': 'pro', 'name': 'Pro'},
    'effective_status': 'active',
    'days_remaining': 12,
  },
  'branches': [
    {'id': 'b1', 'name': 'Centro', 'timezone': 'America/Santiago'},
  ],
  'companies': [
    {'id': 'c1', 'name': 'Estudio Rojo'},
    {'id': 'c2', 'name': 'Otra Empresa'},
  ],
  'sync_resources': ['branches', 'bookings'],
};

void main() {
  test('Bootstrap exposes identity, permissions and modules', () {
    final bootstrap = Bootstrap.fromJson(_bootstrapJson());

    expect(bootstrap.userName, 'Ana Díaz');
    expect(bootstrap.companyName, 'Estudio Rojo');
    expect(bootstrap.role, 'Trabajador');
    expect(bootstrap.workerId, 'w1');
    expect(bootstrap.workerName, 'Ana Díaz');
    expect(bootstrap.permissions, contains('bookings.own.read'));
    expect(bootstrap.moduleEnabled('agenda'), isTrue);
    expect(bootstrap.moduleEnabled('inventory'), isFalse);
    expect(bootstrap.billingState, 'usable');
    expect(bootstrap.syncResources, ['branches', 'bookings']);
    expect(bootstrap.branches.single['timezone'], 'America/Santiago');
  });

  test('Bootstrap roundtrip keeps companies and worker', () {
    final bootstrap = Bootstrap.fromJson(_bootstrapJson());

    final restored = Bootstrap.fromJson(bootstrap.toJson());

    expect(restored.companies, hasLength(2));
    expect(restored.companies.last['name'], 'Otra Empresa');
    expect(restored.workerName, 'Ana Díaz');
    expect(restored.hasSubscription, isTrue);
  });

  test('Bootstrap tolerates missing optional sections', () {
    final bootstrap = Bootstrap.fromJson({
      'user': {'email': 'sin@empresa.cl'},
      'company': {},
      'membership': {},
    });

    expect(bootstrap.userName, 'sin@empresa.cl');
    expect(bootstrap.permissions, isEmpty);
    expect(bootstrap.branches, isEmpty);
    expect(bootstrap.moduleEnabled('agenda'), isFalse);
    expect(bootstrap.hasSubscription, isFalse);
  });

  test('Bootstrap exposes white-label branding and booking url', () {
    final json = _bootstrapJson();
    json['company'] = {
      'id': 'c1',
      'name': 'Estudio Rojo SpA',
      'display_name': 'Estudio Rojo',
      'slug': 'estudio-rojo',
      'primary_color': '#10B981',
      'secondary_color': '#047857',
      'logo_url': 'http://127.0.0.1:8000/media/company-logos/estudio-rojo.png',
      'booking_url': 'http://127.0.0.1:8000/b/estudio-rojo/',
    };

    final bootstrap = Bootstrap.fromJson(json);

    expect(bootstrap.companyName, 'Estudio Rojo');
    expect(bootstrap.branding.primary, const Color(0xFF10B981));
    expect(bootstrap.branding.secondary, const Color(0xFF047857));
    expect(bootstrap.branding.hasLogo, isTrue);
    expect(
      bootstrap.companyBookingUrl,
      'http://127.0.0.1:8000/b/estudio-rojo/',
    );
  });

  test('StockRow detects low stock against the product reorder point', () {
    final product = ProductRecord({
      'id': 'p1',
      'name': 'Shampoo',
      'reorder_point': '5.000',
    });
    final row = StockRow({
      'product': 'p1',
      'quantity': '4.000',
      'warehouse_name': 'Bodega',
    }, product);

    expect(row.lowStock, isTrue);
    expect(row.quantity, 4);
  });
}
