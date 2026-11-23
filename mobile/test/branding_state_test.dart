import 'package:agenda_mobile/data/api_client.dart';
import 'package:agenda_mobile/data/local_store.dart';
import 'package:agenda_mobile/data/models.dart';
import 'package:agenda_mobile/state/app_state.dart';
import 'package:flutter_test/flutter_test.dart';

class _BrandingApi extends ApiClient {
  _BrandingApi(this.bootstrapData) : super(baseUrl: 'http://fake');

  Map<String, dynamic> bootstrapData;
  final List<String> calls = [];
  Map<String, dynamic>? patchBody;
  List<int>? uploadedBytes;
  String? uploadedFilename;
  bool rejectPatch = false;

  @override
  Future<Map<String, dynamic>> getMap(
    String path, {
    Map<String, String>? query,
  }) async {
    calls.add('GET $path');
    if (path == '/api/v1/mobile/bootstrap/') return bootstrapData;
    return const {};
  }

  @override
  Future<Map<String, dynamic>> patchMap(
    String path, {
    Object? body,
    bool authenticated = true,
  }) async {
    calls.add('PATCH $path');
    patchBody = (body as Map).map((key, value) => MapEntry('$key', value));
    if (rejectPatch) {
      throw ApiException(400, 'Usa un color hexadecimal con formato #RRGGBB.');
    }
    final company = (bootstrapData['company'] as Map).cast<String, dynamic>();
    company.addAll(patchBody!);
    bootstrapData = {
      ...bootstrapData,
      'company': company,
      'companies': [
        for (final item in bootstrapData['companies'] as List)
          {...(item as Map).cast<String, dynamic>(), ...patchBody!},
      ],
    };
    return const {};
  }

  @override
  Future<Map<String, dynamic>> postMultipart(
    String path, {
    required String field,
    required List<int> bytes,
    required String filename,
    bool retry = true,
  }) async {
    calls.add('POST $path');
    uploadedBytes = bytes;
    uploadedFilename = filename;
    final company = (bootstrapData['company'] as Map).cast<String, dynamic>();
    bootstrapData = {
      ...bootstrapData,
      'company': {...company, 'logo_url': 'http://fake/media/logo.png'},
    };
    return const {};
  }

  @override
  Future<Map<String, dynamic>> deleteMap(String path) async {
    calls.add('DELETE $path');
    final company = (bootstrapData['company'] as Map).cast<String, dynamic>();
    bootstrapData = {
      ...bootstrapData,
      'company': {...company, 'logo_url': ''},
    };
    return const {};
  }
}

Map<String, dynamic> _bootstrap({String logoUrl = ''}) => {
  'user': {'email': 'duena@aurora.cl'},
  'company': {
    'id': '1',
    'name': 'Aurora SpA',
    'display_name': 'Aurora',
    'primary_color': '#E50914',
    'secondary_color': '#8B0000',
    'logo_url': logoUrl,
  },
  'membership': {'role': 'owner'},
  'permissions': ['company.manage'],
  'features': <String, dynamic>{},
  'modules': <String, dynamic>{},
  'billing_state': 'active',
  'branches': <dynamic>[],
  'sync_resources': <dynamic>[],
  'companies': [
    {'id': '1', 'name': 'Aurora SpA', 'display_name': 'Aurora'},
  ],
};

Future<AppState> _readyState(_BrandingApi api) async {
  final state = AppState(api: api, store: await LocalStore.memory());
  state.status = AppStatus.ready;
  state.bootstrap = Bootstrap.fromJson(_bootstrap());
  return state;
}

void main() {
  test('updateBranding saves the form and reloads the theme', () async {
    final api = _BrandingApi(_bootstrap());
    final state = await _readyState(api);

    final saved = await state.updateBranding(
      displayName: 'Aurora Pro',
      slug: 'aurora-pro',
      primaryColor: '#112233',
      secondaryColor: '#445566',
      darkMode: true,
    );

    expect(saved, isTrue);
    expect(api.patchBody, {
      'display_name': 'Aurora Pro',
      'slug': 'aurora-pro',
      'primary_color': '#112233',
      'secondary_color': '#445566',
      'theme_mode': 'dark',
    });
    expect(api.calls, [
      'PATCH /api/v1/company/branding/',
      'GET /api/v1/mobile/bootstrap/',
    ]);
    expect(state.bootstrap!.companyName, 'Aurora Pro');
    expect(state.bootstrap!.company['theme_mode'], 'dark');
    expect(state.companies.first['display_name'], 'Aurora Pro');
    expect(state.companies.first['theme_mode'], 'dark');
    expect(state.busy, isFalse);
  });

  test(
    'updateBranding shows the backend message and keeps the theme',
    () async {
      final api = _BrandingApi(_bootstrap())..rejectPatch = true;
      final state = await _readyState(api);

      final saved = await state.updateBranding(
        displayName: 'Aurora',
        slug: 'aurora',
        primaryColor: 'rojo',
        secondaryColor: '#8B0000',
        darkMode: false,
      );

      expect(saved, isFalse);
      expect(
        state.errorMessage,
        'Usa un color hexadecimal con formato #RRGGBB.',
      );
      expect(state.bootstrap!.companyName, 'Aurora');
      expect(api.calls, ['PATCH /api/v1/company/branding/']);
      expect(state.busy, isFalse);
    },
  );

  test('uploadLogo sends the bytes and reloads the bootstrap', () async {
    final api = _BrandingApi(_bootstrap());
    final state = await _readyState(api);

    final saved = await state.uploadLogo(
      bytes: [137, 80, 78, 71],
      filename: 'logo.png',
    );

    expect(saved, isTrue);
    expect(api.uploadedBytes, [137, 80, 78, 71]);
    expect(api.uploadedFilename, 'logo.png');
    expect(api.calls, [
      'POST /api/v1/company/branding/logo/',
      'GET /api/v1/mobile/bootstrap/',
    ]);
    expect(state.bootstrap!.branding.hasLogo, isTrue);
    expect(state.busy, isFalse);
  });

  test('removeLogo clears the company logo', () async {
    final api = _BrandingApi(_bootstrap(logoUrl: 'http://fake/media/logo.png'));
    final state = await _readyState(api);

    final removed = await state.removeLogo();

    expect(removed, isTrue);
    expect(api.calls, [
      'DELETE /api/v1/company/branding/logo/',
      'GET /api/v1/mobile/bootstrap/',
    ]);
    expect(state.bootstrap!.branding.hasLogo, isFalse);
    expect(state.busy, isFalse);
  });
}
