import 'dart:convert';

import 'package:agenda_mobile/data/api_client.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  test('patchMap sends JSON with authentication and tenant headers', () async {
    late http.Request captured;
    final client = MockClient((request) async {
      captured = request;
      return http.Response(
        jsonEncode({'display_name': 'Aurora'}),
        200,
        headers: {'content-type': 'application/json'},
      );
    });
    final api = ApiClient(baseUrl: 'http://fake', client: client)
      ..accessToken = 'access'
      ..tenantContextId = 'ctx';

    final data = await api.patchMap(
      '/api/v1/company/branding/',
      body: {'display_name': 'Aurora'},
    );

    expect(data['display_name'], 'Aurora');
    expect(captured.method, 'PATCH');
    expect(captured.headers['Authorization'], 'Bearer access');
    expect(captured.headers['X-Tenant-Context'], 'ctx');
    expect(jsonDecode(captured.body), {'display_name': 'Aurora'});
  });

  test('patchMap surfaces the first server validation message', () async {
    final client = MockClient((request) async {
      return http.Response(
        jsonEncode({
          'primary_color': ['Usa un color hexadecimal con formato #RRGGBB.'],
        }),
        400,
        headers: {'content-type': 'application/json'},
      );
    });
    final api = ApiClient(baseUrl: 'http://fake', client: client);

    await expectLater(
      api.patchMap(
        '/api/v1/company/branding/',
        body: {'primary_color': 'rojo'},
      ),
      throwsA(
        isA<ApiException>()
            .having((error) => error.statusCode, 'status', 400)
            .having(
              (error) => error.message,
              'message',
              'Usa un color hexadecimal con formato #RRGGBB.',
            ),
      ),
    );
  });

  test('postMultipart uploads the logo with auth and tenant headers', () async {
    late http.Request captured;
    final client = MockClient((request) async {
      captured = request;
      return http.Response(
        jsonEncode({'logo_url': 'http://fake/media/company-logos/logo.png'}),
        200,
        headers: {'content-type': 'application/json'},
      );
    });
    final api = ApiClient(baseUrl: 'http://fake', client: client)
      ..accessToken = 'access'
      ..tenantContextId = 'ctx';

    final data = await api.postMultipart(
      '/api/v1/company/branding/logo/',
      field: 'logo',
      bytes: [137, 80, 78, 71],
      filename: 'logo.png',
    );

    expect(data['logo_url'], contains('logo.png'));
    expect(captured.method, 'POST');
    expect(captured.headers['Authorization'], 'Bearer access');
    expect(captured.headers['X-Tenant-Context'], 'ctx');
    expect(
      captured.headers['content-type'],
      startsWith('multipart/form-data; boundary='),
    );
    final body = latin1.decode(captured.bodyBytes);
    expect(body, contains('name="logo"'));
    expect(body, contains('filename="logo.png"'));
  });

  test('deleteMap sends DELETE and returns the branding payload', () async {
    late http.Request captured;
    final client = MockClient((request) async {
      captured = request;
      return http.Response(
        jsonEncode({'logo_url': ''}),
        200,
        headers: {'content-type': 'application/json'},
      );
    });
    final api = ApiClient(baseUrl: 'http://fake', client: client)
      ..accessToken = 'access'
      ..tenantContextId = 'ctx';

    final data = await api.deleteMap('/api/v1/company/branding/logo/');

    expect(data['logo_url'], '');
    expect(captured.method, 'DELETE');
    expect(captured.headers['Authorization'], 'Bearer access');
    expect(captured.headers['X-Tenant-Context'], 'ctx');
  });
}
