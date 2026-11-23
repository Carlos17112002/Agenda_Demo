import 'package:agenda_mobile/core/theme.dart';
import 'package:agenda_mobile/data/local_store.dart';
import 'package:agenda_mobile/screens/login_screen.dart';
import 'package:agenda_mobile/state/app_state.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';

void main() {
  testWidgets('login screen asks for server, email and password', (
    tester,
  ) async {
    final store = await LocalStore.memory();
    final app = AppState(store: store);

    await tester.pumpWidget(
      ChangeNotifierProvider.value(
        value: app,
        child: MaterialApp(
          theme: buildAgendaTheme(),
          home: const LoginScreen(),
        ),
      ),
    );

    expect(find.text('Servidor'), findsOneWidget);
    expect(find.text('Correo'), findsOneWidget);
    expect(find.text('Contraseña'), findsOneWidget);
    expect(find.text('ENTRAR'), findsOneWidget);

    await tester.tap(find.text('ENTRAR'));
    await tester.pump();

    expect(find.text('Indica la URL del servidor'), findsNothing);
    expect(find.text('Ingresa un correo válido'), findsOneWidget);
  });
}
