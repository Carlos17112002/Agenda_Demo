import 'package:agenda_mobile/core/theme.dart';
import 'package:agenda_mobile/data/api_client.dart';
import 'package:agenda_mobile/data/models.dart';
import 'package:agenda_mobile/screens/company_screen.dart';
import 'package:agenda_mobile/screens/create_company_screen.dart';
import 'package:agenda_mobile/state/app_state.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';

class _FakeAppState extends AppState {
  _FakeAppState({this.result}) : super(api: ApiClient(baseUrl: 'http://fake'));

  CompanyCreationResult? result;
  Map<String, dynamic>? submitted;

  @override
  Future<void> loadPlans() async {
    plans = [
      PlanOption(
        code: 'phone-default',
        name: 'Plan Base',
        price: 0,
        currency: 'CLP',
        billingPeriod: 'monthly',
        trialDays: 7,
        isDefault: true,
      ),
      PlanOption(
        code: 'phone-pro',
        name: 'Plan Pro',
        price: 19990,
        currency: 'CLP',
        billingPeriod: 'monthly',
        trialDays: 14,
        isDefault: false,
      ),
    ];
    notifyListeners();
  }

  @override
  Future<CompanyCreationResult?> createCompany({
    required String companyName,
    required String slug,
    required String email,
    String firstName = '',
    String? planCode,
    int? trialDays,
  }) async {
    submitted = {
      'company_name': companyName,
      'slug': slug,
      'email': email,
      'first_name': firstName,
      'plan': ?planCode,
      'trial_days': ?trialDays,
    };
    if (result == null) {
      errorMessage = 'Este identificador de empresa ya está ocupado.';
      notifyListeners();
      return null;
    }
    return result;
  }
}

Map<String, dynamic> _bootstrap({bool saasAdmin = true}) => {
  'user': {
    'email': 'operadora@example.com',
    'first_name': 'Operadora',
    'is_saas_admin': saasAdmin,
  },
  'company': {
    'id': '1',
    'name': 'Aurora SpA',
    'display_name': 'Aurora',
    'slug': 'aurora',
    'primary_color': '#E50914',
    'secondary_color': '#8B0000',
  },
  'membership': {'role': 'owner'},
  'permissions': ['company.manage'],
  'features': <String, dynamic>{},
  'modules': <String, dynamic>{},
  'billing_state': 'active',
  'branches': <dynamic>[],
  'sync_resources': <dynamic>[],
  'companies': [
    {'id': '1', 'name': 'Aurora SpA', 'slug': 'aurora'},
    {'id': '2', 'name': 'Otra', 'slug': 'otra'},
  ],
};

_FakeAppState _readyState({
  bool saasAdmin = true,
  CompanyCreationResult? result,
}) {
  final state = _FakeAppState(result: result)..status = AppStatus.ready;
  final data = _bootstrap(saasAdmin: saasAdmin);
  state.bootstrap = Bootstrap.fromJson(data);
  state.isSaasAdmin = saasAdmin;
  state.companies = (data['companies'] as List).cast<Map<String, dynamic>>();
  return state;
}

Future<void> _pump(WidgetTester tester, Widget home, AppState state) async {
  tester.view.physicalSize = const Size(900, 2200);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.reset);
  await tester.pumpWidget(
    ChangeNotifierProvider<AppState>.value(
      value: state,
      child: MaterialApp(theme: buildAgendaTheme(), home: home),
    ),
  );
  await tester.pumpAndSettle();
}

CompanyCreationResult _result() => CompanyCreationResult(
  companyId: 'nueva-1',
  companyName: 'Peluquería Llamada',
  slug: 'peluqueria-llamada',
  ownerEmail: 'duena@example.com',
  temporaryPassword: 'Temporal-2026!',
  bookingUrl: 'http://fake/b/peluqueria-llamada/',
  planName: 'Plan Pro',
  trialEndsAt: DateTime.utc(2026, 12, 11),
);

void main() {
  testWidgets('company chooser shows create action only for saas admins', (
    tester,
  ) async {
    await _pump(tester, const CompanyScreen(), _readyState());
    expect(find.byKey(const Key('create-company-open')), findsOneWidget);

    await _pump(tester, const CompanyScreen(), _readyState(saasAdmin: false));
    expect(find.byKey(const Key('create-company-open')), findsNothing);
  });

  testWidgets('saas admin opens the create company form', (tester) async {
    await _pump(tester, const CompanyScreen(), _readyState());

    await tester.tap(find.byKey(const Key('create-company-open')));
    await tester.pumpAndSettle();

    expect(find.byType(CreateCompanyScreen), findsOneWidget);
    expect(find.text('NUEVA EMPRESA'), findsOneWidget);
  });

  testWidgets('auto generates the slug and submits the form', (tester) async {
    final state = _readyState(result: _result());
    await _pump(tester, const CreateCompanyScreen(), state);

    await tester.enterText(
      find.byKey(const Key('create-company-name')),
      'Peluquería Llamada',
    );
    await tester.pumpAndSettle();
    expect(
      tester
          .widget<TextFormField>(find.byKey(const Key('create-company-slug')))
          .controller!
          .text,
      'peluqueria-llamada',
    );
    await tester.enterText(
      find.byKey(const Key('create-company-email')),
      'duena@example.com',
    );
    await tester.tap(find.byKey(const Key('create-company-submit')));
    await tester.pumpAndSettle();

    expect(state.submitted, {
      'company_name': 'Peluquería Llamada',
      'slug': 'peluqueria-llamada',
      'email': 'duena@example.com',
      'first_name': '',
      'plan': 'phone-default',
      'trial_days': 7,
    });
    expect(find.byKey(const Key('create-company-success')), findsOneWidget);
    expect(find.text('duena@example.com'), findsOneWidget);
    expect(find.text('Temporal-2026!'), findsOneWidget);
    expect(find.text('Plan Pro'), findsOneWidget);
  });

  testWidgets('lets the operator pick a plan and adjust the trial days', (
    tester,
  ) async {
    final state = _readyState(result: _result());
    await _pump(tester, const CreateCompanyScreen(), state);

    expect(
      tester
          .widget<TextFormField>(find.byKey(const Key('create-company-trial-days')))
          .controller!
          .text,
      '7',
    );

    await tester.tap(find.byKey(const Key('create-company-plan')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Plan Pro').last);
    await tester.pumpAndSettle();

    expect(
      tester
          .widget<TextFormField>(find.byKey(const Key('create-company-trial-days')))
          .controller!
          .text,
      '14',
    );

    await tester.enterText(
      find.byKey(const Key('create-company-name')),
      'Peluquería Llamada',
    );
    await tester.enterText(
      find.byKey(const Key('create-company-email')),
      'duena@example.com',
    );
    await tester.enterText(
      find.byKey(const Key('create-company-trial-days')),
      '30',
    );
    await tester.tap(find.byKey(const Key('create-company-submit')));
    await tester.pumpAndSettle();

    expect(state.submitted, {
      'company_name': 'Peluquería Llamada',
      'slug': 'peluqueria-llamada',
      'email': 'duena@example.com',
      'first_name': '',
      'plan': 'phone-pro',
      'trial_days': 30,
    });
  });

  testWidgets('blocks the submit until the required fields are valid', (
    tester,
  ) async {
    final state = _readyState(result: _result());
    await _pump(tester, const CreateCompanyScreen(), state);

    await tester.tap(find.byKey(const Key('create-company-submit')));
    await tester.pumpAndSettle();

    expect(find.text('Escribe el nombre comercial.'), findsOneWidget);
    expect(find.text('Escribe un correo válido.'), findsOneWidget);
    expect(state.submitted, isNull);
  });
}
