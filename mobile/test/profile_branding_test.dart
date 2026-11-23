import 'package:agenda_mobile/core/theme.dart';
import 'package:agenda_mobile/data/api_client.dart';
import 'package:agenda_mobile/data/models.dart';
import 'package:agenda_mobile/screens/branding_screen.dart';
import 'package:agenda_mobile/screens/profile_screen.dart';
import 'package:agenda_mobile/state/app_state.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';

Map<String, dynamic> _bootstrap(List<String> permissions) => {
  'user': {
    'email': 'duena@aurora.cl',
    'first_name': 'Ana',
    'last_name': 'Díaz',
  },
  'company': {
    'id': '1',
    'name': 'Aurora SpA',
    'display_name': 'Aurora',
    'slug': 'aurora',
    'primary_color': '#E50914',
    'secondary_color': '#8B0000',
    'logo_url': '',
    'booking_url': 'http://localhost:8000/b/aurora/',
  },
  'membership': {'role': 'owner', 'role_display': 'Propietaria'},
  'permissions': permissions,
  'features': <String, dynamic>{},
  'modules': <String, dynamic>{},
  'billing_state': 'usable',
  'branches': <dynamic>[],
  'sync_resources': <dynamic>[],
  'companies': [
    {'id': '1', 'name': 'Aurora SpA', 'display_name': 'Aurora'},
  ],
};

Future<AppState> _pumpProfile(
  WidgetTester tester,
  List<String> permissions,
) async {
  tester.view.physicalSize = const Size(900, 2400);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.reset);
  final state = AppState(api: ApiClient(baseUrl: 'http://fake'))
    ..status = AppStatus.ready;
  state.bootstrap = Bootstrap.fromJson(_bootstrap(permissions));
  await tester.pumpWidget(
    ChangeNotifierProvider<AppState>.value(
      value: state,
      child: MaterialApp(
        theme: buildAgendaTheme(),
        home: const ProfileScreen(),
      ),
    ),
  );
  await tester.pumpAndSettle();
  return state;
}

void main() {
  testWidgets('hides the branding editor without company.manage', (
    tester,
  ) async {
    await _pumpProfile(tester, const ['bookings.read']);

    expect(find.text('Editar marca'), findsNothing);
  });

  testWidgets('opens the branding editor with company.manage', (tester) async {
    await _pumpProfile(tester, const ['company.manage']);

    final button = find.text('Editar marca');
    await tester.ensureVisible(button);
    await tester.pumpAndSettle();
    await tester.tap(button);
    await tester.pumpAndSettle();

    expect(find.byType(BrandingScreen), findsOneWidget);
    expect(find.text('Marca de empresa'), findsOneWidget);
  });
}
