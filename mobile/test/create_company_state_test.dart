import 'package:agenda_mobile/data/api_client.dart';
import 'package:agenda_mobile/data/local_store.dart';
import 'package:agenda_mobile/data/session_store.dart';
import 'package:agenda_mobile/state/app_state.dart';
import 'package:flutter_test/flutter_test.dart';

class _CompanyApi extends ApiClient {
  _CompanyApi() : super(baseUrl: 'http://fake');

  final List<String> calls = [];
  Map<String, dynamic>? body;
  bool reject = false;

  @override
  Future<Map<String, dynamic>> postMap(
    String path, {
    Object? body,
    bool authenticated = true,
  }) async {
    calls.add('POST $path');
    this.body = (body as Map).map((key, value) => MapEntry('$key', value));
    if (reject) {
      throw ApiException(400, 'Este identificador de empresa ya está ocupado.');
    }
    return {
      'company_id': 'nueva-1',
      'company_name': 'Peluquería Llamada',
      'slug': 'peluqueria-llamada',
      'owner_email': 'duena@example.com',
      'temporary_password': 'Temporal-2026!',
      'booking_url': 'http://fake/b/peluqueria-llamada/',
      'subscription': {
        'status': 'trialing',
        'trial_ends_at': '2026-12-11T10:00:00Z',
        'plan': {'code': 'phone-pro', 'name': 'Plan Pro', 'trial_days': 14},
      },
    };
  }

  @override
  Future<Map<String, dynamic>> login(String email, String password) async {
    calls.add('LOGIN');
    accessToken = 'access-token';
    refreshToken = 'refresh-token';
    return {
      'access': accessToken,
      'refresh': refreshToken,
      'user': {
        'id': 'u1',
        'email': email,
        'first_name': 'Operadora',
        'last_name': '',
        'is_saas_admin': true,
      },
    };
  }

  @override
  Future<List<Map<String, dynamic>>> getList(
    String path, {
    Map<String, String>? query,
  }) async {
    calls.add('GET $path');
    if (path == '/api/v1/plans/') {
      return [
        {
          'code': 'phone-default',
          'name': 'Plan Base',
          'price': '0.00',
          'currency': 'CLP',
          'billing_period': 'monthly',
          'trial_days': 7,
          'is_default': true,
        },
        {
          'code': 'phone-pro',
          'name': 'Plan Pro',
          'price': '19990.00',
          'currency': 'CLP',
          'billing_period': 'monthly',
          'trial_days': 14,
          'is_default': false,
        },
      ];
    }
    return [
      {'id': 'a', 'name': 'Empresa A', 'slug': 'empresa-a'},
      {'id': 'b', 'name': 'Empresa B', 'slug': 'empresa-b'},
    ];
  }
}

class _MemorySessions extends SessionStore {
  SessionSnapshot? saved;

  @override
  Future<SessionSnapshot?> load() async => null;

  @override
  Future<void> save(SessionSnapshot snapshot) async => saved = snapshot;

  @override
  Future<void> clear() async => saved = null;
}

Future<AppState> _state(_CompanyApi api) async {
  return AppState(
    api: api,
    store: await LocalStore.memory(),
    sessions: _MemorySessions(),
  );
}

void main() {
  test(
    'createCompany sends the operator payload and returns credentials',
    () async {
      final api = _CompanyApi();
      final state = await _state(api);

      final result = await state.createCompany(
        companyName: 'Peluquería Llamada',
        slug: 'peluqueria-llamada',
        email: 'duena@example.com',
        firstName: 'María',
        planCode: 'phone-pro',
        trialDays: 30,
      );

      expect(api.calls, ['POST /api/v1/saas/companies/']);
      expect(api.body, {
        'company_name': 'Peluquería Llamada',
        'slug': 'peluqueria-llamada',
        'email': 'duena@example.com',
        'first_name': 'María',
        'plan': 'phone-pro',
        'trial_days': 30,
      });
      expect(result, isNotNull);
      expect(result!.companyName, 'Peluquería Llamada');
      expect(result.ownerEmail, 'duena@example.com');
      expect(result.temporaryPassword, 'Temporal-2026!');
      expect(result.bookingUrl, 'http://fake/b/peluqueria-llamada/');
      expect(result.planName, 'Plan Pro');
      expect(result.trialEndsAt, isNotNull);
      expect(state.errorMessage, isNull);
      expect(state.busy, isFalse);
    },
  );

  test('loadPlans exposes the public plans and the default one', () async {
    final api = _CompanyApi();
    final state = await _state(api);

    await state.loadPlans();

    expect(api.calls, ['GET /api/v1/plans/']);
    expect(state.plans.map((plan) => plan.code), ['phone-default', 'phone-pro']);
    expect(state.plans.first.isDefault, isTrue);
    expect(state.plans.first.trialDays, 7);
    expect(state.plans.last.priceLabel, 'CLP 19990/mes');
  });

  test('createCompany surfaces the backend message and returns null', () async {
    final api = _CompanyApi()..reject = true;
    final state = await _state(api);

    final result = await state.createCompany(
      companyName: 'Peluquería Llamada',
      slug: 'peluqueria-llamada',
      email: 'duena@example.com',
    );

    expect(result, isNull);
    expect(
      state.errorMessage,
      'Este identificador de empresa ya está ocupado.',
    );
    expect(state.busy, isFalse);
  });

  test('login exposes the saas admin flag before choosing a company', () async {
    final api = _CompanyApi();
    final state = await _state(api);

    await state.login(
      baseUrl: 'http://fake',
      email: 'operadora@example.com',
      password: 'Correct-Horse-Battery-983!',
    );

    expect(state.isSaasAdmin, isTrue);
    expect(state.status, AppStatus.chooseCompany);
  });
}
