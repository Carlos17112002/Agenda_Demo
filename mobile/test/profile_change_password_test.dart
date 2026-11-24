import 'package:agenda_mobile/core/theme.dart';
import 'package:agenda_mobile/data/api_client.dart';
import 'package:agenda_mobile/data/local_store.dart';
import 'package:agenda_mobile/data/models.dart';
import 'package:agenda_mobile/data/session_store.dart';
import 'package:agenda_mobile/screens/change_password_screen.dart';
import 'package:agenda_mobile/screens/profile_screen.dart';
import 'package:agenda_mobile/state/app_state.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';

Map<String, dynamic> _bootstrap() => {
  'user': {
    'email': 'duena@aurora.cl',
    'first_name': 'Ana',
    'last_name': 'Díaz',
  },
  'company': {
    'id': '1',
    'name': 'Aurora SpA',
    'slug': 'aurora',
    'primary_color': '#E50914',
    'secondary_color': '#8B0000',
    'logo_url': '',
    'booking_url': '',
  },
  'membership': {'role': 'owner', 'role_display': 'Propietaria'},
  'permissions': <String>[],
  'features': <String, dynamic>{},
  'modules': <String, dynamic>{},
  'billing_state': 'usable',
  'branches': <dynamic>[],
  'sync_resources': <dynamic>[],
  'companies': [
    {'id': '1', 'name': 'Aurora SpA', 'display_name': 'Aurora'},
  ],
};

class _PasswordApi extends ApiClient {
  _PasswordApi() : super(baseUrl: 'http://fake');

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

Future<AppState> _readyState() async {
  final state = AppState(
    api: _PasswordApi(),
    store: await LocalStore.memory(),
    sessions: _MemorySessions(),
  )..status = AppStatus.ready;
  state.bootstrap = Bootstrap.fromJson(_bootstrap());
  return state;
}

class _Launcher extends StatelessWidget {
  const _Launcher();

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Column(
        children: [
          const Text('Panel de inicio'),
          ElevatedButton(
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute(
                builder: (_) => const ChangePasswordScreen(voluntary: true),
              ),
            ),
            child: const Text('Abrir cambio'),
          ),
        ],
      ),
    );
  }
}

void main() {
  testWidgets('Perfil abre el cambio de contraseña con botón de volver', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(900, 2600);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.reset);
    final state = await _readyState();
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

    final button = find.text('Cambiar contraseña');
    await tester.ensureVisible(button);
    await tester.pumpAndSettle();
    await tester.tap(button);
    await tester.pumpAndSettle();

    expect(find.byType(ChangePasswordScreen), findsOneWidget);
    expect(find.text('CAMBIAR CONTRASEÑA'), findsOneWidget);
    expect(find.byType(BackButton), findsOneWidget);
  });

  testWidgets('en modo voluntario confirma y vuelve al panel', (tester) async {
    final state = await _readyState();
    await tester.pumpWidget(
      ChangeNotifierProvider<AppState>.value(
        value: state,
        child: MaterialApp(
          theme: buildAgendaTheme(),
          home: const _Launcher(),
        ),
      ),
    );

    await tester.tap(find.text('Abrir cambio'));
    await tester.pumpAndSettle();

    await tester.enterText(
      find.widgetWithText(TextFormField, 'Contraseña actual'),
      'Vieja-Clave-123!',
    );
    await tester.enterText(
      find.widgetWithText(TextFormField, 'Nueva contraseña'),
      'Nueva-Clave-456!',
    );
    await tester.enterText(
      find.widgetWithText(TextFormField, 'Repetir contraseña'),
      'Nueva-Clave-456!',
    );
    await tester.tap(find.text('ACTUALIZAR CONTRASEÑA'));
    await tester.pumpAndSettle();

    expect(find.text('Contraseña actualizada'), findsOneWidget);
    await tester.tap(find.text('Listo'));
    await tester.pumpAndSettle();

    expect(find.text('Panel de inicio'), findsOneWidget);
    expect(find.byType(ChangePasswordScreen), findsNothing);
  });
}
