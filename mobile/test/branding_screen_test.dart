import 'dart:typed_data';

import 'package:agenda_mobile/core/theme.dart';
import 'package:agenda_mobile/data/api_client.dart';
import 'package:agenda_mobile/data/models.dart';
import 'package:agenda_mobile/screens/branding_screen.dart';
import 'package:agenda_mobile/state/app_state.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';

class _FakeAppState extends AppState {
  _FakeAppState() : super(api: ApiClient(baseUrl: 'http://fake'));

  Map<String, dynamic>? saved;
  List<int>? uploadedBytes;
  String? uploadedName;
  int removeCalls = 0;
  bool saveResult = true;
  bool uploadResult = true;
  bool removeResult = true;

  @override
  Future<bool> updateBranding({
    required String displayName,
    required String slug,
    required String primaryColor,
    required String secondaryColor,
    required bool darkMode,
  }) async {
    saved = {
      'display_name': displayName,
      'slug': slug,
      'primary_color': primaryColor,
      'secondary_color': secondaryColor,
      'theme_mode': darkMode ? 'dark' : 'light',
    };
    if (!saveResult) errorMessage = 'Color válido solo en el servidor.';
    notifyListeners();
    return saveResult;
  }

  @override
  Future<bool> uploadLogo({
    required List<int> bytes,
    required String filename,
  }) async {
    uploadedBytes = bytes;
    uploadedName = filename;
    if (!uploadResult) errorMessage = 'El servidor rechazó el logo.';
    notifyListeners();
    return uploadResult;
  }

  @override
  Future<bool> removeLogo() async {
    removeCalls++;
    if (!removeResult) errorMessage = 'No se pudo quitar el logo.';
    notifyListeners();
    return removeResult;
  }
}

Map<String, dynamic> _bootstrap({
  List<String> permissions = const ['company.manage'],
  String logoUrl = '',
  String themeMode = 'light',
}) => {
  'user': {'email': 'duena@aurora.cl'},
  'company': {
    'id': '1',
    'name': 'Aurora SpA',
    'display_name': 'Aurora',
    'slug': 'aurora',
    'primary_color': '#E50914',
    'secondary_color': '#8B0000',
    'theme_mode': themeMode,
    'logo_url': logoUrl,
    'booking_url': 'http://localhost:8000/b/aurora/',
  },
  'membership': {'role': 'owner'},
  'permissions': permissions,
  'features': <String, dynamic>{},
  'modules': <String, dynamic>{},
  'billing_state': 'active',
  'branches': <dynamic>[],
  'sync_resources': <dynamic>[],
  'companies': [
    {'id': '1', 'name': 'Aurora SpA', 'display_name': 'Aurora'},
  ],
};

Future<_FakeAppState> _pumpScreen(
  WidgetTester tester, {
  List<String> permissions = const ['company.manage'],
  String logoUrl = '',
  String themeMode = 'light',
  LogoPicker? pickLogo,
}) async {
  tester.view.physicalSize = const Size(900, 2200);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.reset);
  final state = _FakeAppState()..status = AppStatus.ready;
  state.bootstrap = Bootstrap.fromJson(
    _bootstrap(
      permissions: permissions,
      logoUrl: logoUrl,
      themeMode: themeMode,
    ),
  );
  await tester.pumpWidget(
    ChangeNotifierProvider<AppState>.value(
      value: state,
      child: MaterialApp(
        theme: buildAgendaTheme(),
        home: BrandingScreen(pickLogo: pickLogo),
      ),
    ),
  );
  await tester.pumpAndSettle();
  return state;
}

Future<void> _tap(WidgetTester tester, String key) async {
  final finder = find.byKey(Key(key));
  await tester.ensureVisible(finder);
  await tester.pumpAndSettle();
  await tester.tap(finder);
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('blocks the editor without company.manage', (tester) async {
    await _pumpScreen(tester, permissions: const ['bookings.read']);

    expect(
      find.text('No tienes permiso para editar la marca.'),
      findsOneWidget,
    );
    expect(find.byKey(const Key('branding-save')), findsNothing);
  });

  testWidgets('loads the current branding into the form', (tester) async {
    await _pumpScreen(tester);

    expect(
      tester
          .widget<TextFormField>(find.byKey(const Key('branding-name')))
          .controller!
          .text,
      'Aurora',
    );
    expect(
      tester
          .widget<TextFormField>(find.byKey(const Key('branding-slug')))
          .controller!
          .text,
      'aurora',
    );
    expect(
      tester
          .widget<TextFormField>(find.byKey(const Key('branding-primary')))
          .controller!
          .text,
      '#E50914',
    );
    expect(
      tester
          .widget<TextFormField>(find.byKey(const Key('branding-secondary')))
          .controller!
          .text,
      '#8B0000',
    );
  });

  testWidgets('rejects an invalid hex color before calling the API', (
    tester,
  ) async {
    final state = await _pumpScreen(tester);

    await tester.enterText(find.byKey(const Key('branding-primary')), 'rojo');
    await _tap(tester, 'branding-save');

    expect(
      find.text('Usa un color hexadecimal con formato #RRGGBB.'),
      findsOneWidget,
    );
    expect(state.saved, isNull);
  });

  testWidgets('rejects an invalid slug before calling the API', (tester) async {
    final state = await _pumpScreen(tester);

    await tester.enterText(
      find.byKey(const Key('branding-slug')),
      'aurora pro',
    );
    await _tap(tester, 'branding-save');

    expect(
      find.text('Usa letras, números, guiones o guiones bajos (máximo 100).'),
      findsOneWidget,
    );
    expect(state.saved, isNull);
  });

  testWidgets('warns that changing the slug moves the public link', (
    tester,
  ) async {
    await _pumpScreen(tester);

    expect(find.textContaining('El enlace público cambiará'), findsNothing);

    await tester.enterText(
      find.byKey(const Key('branding-slug')),
      'nueva-marca',
    );
    await tester.pumpAndSettle();

    expect(find.textContaining('/b/nueva-marca/'), findsOneWidget);
  });

  testWidgets('saves the branding and confirms it', (tester) async {
    final state = await _pumpScreen(tester);

    await tester.enterText(
      find.byKey(const Key('branding-name')),
      'Aurora Pro',
    );
    await _tap(tester, 'branding-save');

    expect(state.saved, {
      'display_name': 'Aurora Pro',
      'slug': 'aurora',
      'primary_color': '#E50914',
      'secondary_color': '#8B0000',
      'theme_mode': 'light',
    });
    expect(find.text('Marca actualizada.'), findsOneWidget);
  });

  testWidgets('previews and saves a dark background', (tester) async {
    final state = await _pumpScreen(tester);

    BoxDecoration preview() =>
        tester.widget<Container>(find.byKey(const Key('branding-preview'))).decoration!
            as BoxDecoration;

    expect(preview().color, const Color(0xFFFFFFFF));

    await _tap(tester, 'branding-theme-dark');

    expect(preview().color, const Color(0xFF0E0E10));

    await _tap(tester, 'branding-save');

    expect(state.saved?['theme_mode'], 'dark');
  });

  testWidgets('loads the saved dark background from the company', (
    tester,
  ) async {
    final state = await _pumpScreen(tester, themeMode: 'dark');

    final decoration =
        tester.widget<Container>(find.byKey(const Key('branding-preview'))).decoration!
            as BoxDecoration;
    expect(decoration.color, const Color(0xFF0E0E10));

    await _tap(tester, 'branding-save');

    expect(state.saved?['theme_mode'], 'dark');
  });

  testWidgets('normalizes the slug to lowercase before saving', (tester) async {
    final state = await _pumpScreen(tester);

    await tester.enterText(
      find.byKey(const Key('branding-slug')),
      'Aurora-Pro',
    );
    await _tap(tester, 'branding-save');

    expect(state.saved?['slug'], 'aurora-pro');
  });

  testWidgets('shows the server message when the save fails', (tester) async {
    final state = await _pumpScreen(tester);
    state.saveResult = false;

    await _tap(tester, 'branding-save');

    expect(find.text('Color válido solo en el servidor.'), findsOneWidget);
    expect(find.text('Marca actualizada.'), findsNothing);
  });

  testWidgets('uploads the picked logo bytes', (tester) async {
    final state = await _pumpScreen(
      tester,
      pickLogo: () async =>
          PickedLogo(bytes: const [137, 80, 78, 71], filename: 'logo.png'),
    );

    expect(find.byKey(const Key('branding-remove-logo')), findsNothing);

    await _tap(tester, 'branding-upload');

    expect(state.uploadedBytes, [137, 80, 78, 71]);
    expect(state.uploadedName, 'logo.png');
    expect(find.text('Logo actualizado.'), findsOneWidget);
  });

  testWidgets('rejects an unsupported logo format before uploading', (
    tester,
  ) async {
    final state = await _pumpScreen(
      tester,
      pickLogo: () async =>
          PickedLogo(bytes: const [71, 73, 70], filename: 'logo.gif'),
    );

    await _tap(tester, 'branding-upload');

    expect(find.text('Sube un logo PNG, JPEG o WebP.'), findsOneWidget);
    expect(state.uploadedBytes, isNull);
  });

  testWidgets('rejects a logo over 2 MB before uploading', (tester) async {
    final state = await _pumpScreen(
      tester,
      pickLogo: () async => PickedLogo(
        bytes: Uint8List(2 * 1024 * 1024 + 1),
        filename: 'logo.png',
      ),
    );

    await _tap(tester, 'branding-upload');

    expect(find.text('El logo no puede superar 2 MB.'), findsOneWidget);
    expect(state.uploadedBytes, isNull);
  });

  testWidgets('removes the logo when the company already has one', (
    tester,
  ) async {
    final state = await _pumpScreen(
      tester,
      logoUrl: 'http://localhost:8000/media/company-logos/logo.png',
    );

    await _tap(tester, 'branding-remove-logo');

    expect(state.removeCalls, 1);
    expect(find.text('Logo eliminado.'), findsOneWidget);
  });
}
