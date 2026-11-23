import 'dart:convert';

import 'package:http/http.dart' as http;

class ApiException implements Exception {
  ApiException(this.statusCode, this.message);

  final int statusCode;
  final String message;

  bool get unauthorized => statusCode == 401 || statusCode == 403;
  bool get offline => statusCode == 0;

  @override
  String toString() => message;
}

class ApiClient {
  ApiClient({String baseUrl = 'http://127.0.0.1:8000', http.Client? client})
    : _baseUrl = normalizeBaseUrl(baseUrl),
      _client = client ?? http.Client();

  final http.Client _client;
  String _baseUrl;
  String? accessToken;
  String? refreshToken;
  String? tenantContextId;

  String get baseUrl => _baseUrl;
  bool get hasSession => accessToken != null;

  set baseUrl(String value) => _baseUrl = normalizeBaseUrl(value);

  static String normalizeBaseUrl(String value) {
    var normalized = value.trim();
    if (normalized.isEmpty) return 'http://127.0.0.1:8000';
    if (!normalized.startsWith('http://') &&
        !normalized.startsWith('https://')) {
      normalized = 'http://$normalized';
    }
    while (normalized.endsWith('/')) {
      normalized = normalized.substring(0, normalized.length - 1);
    }
    return normalized;
  }

  Map<String, String> _headers({bool authenticated = true}) {
    final headers = <String, String>{
      'Accept': 'application/json',
      'Content-Type': 'application/json',
    };
    if (authenticated && accessToken != null) {
      headers['Authorization'] = 'Bearer $accessToken';
    }
    if (tenantContextId != null) {
      headers['X-Tenant-Context'] = tenantContextId!;
    }
    return headers;
  }

  Uri _uri(String path, [Map<String, String>? query]) {
    final uri = Uri.parse('$_baseUrl$path');
    if (query == null || query.isEmpty) return uri;
    return uri.replace(queryParameters: {...uri.queryParameters, ...query});
  }

  Future<http.Response> _send(
    String method,
    String path, {
    Object? body,
    Map<String, String>? query,
    bool authenticated = true,
    bool retry = true,
  }) async {
    http.Response response;
    try {
      final uri = _uri(path, query);
      final headers = _headers(authenticated: authenticated);
      final encoded = body == null ? null : jsonEncode(body);
      response = switch (method) {
        'GET' => await _client.get(uri, headers: headers),
        'POST' => await _client.post(uri, headers: headers, body: encoded),
        'PATCH' => await _client.patch(uri, headers: headers, body: encoded),
        'DELETE' => await _client.delete(uri, headers: headers, body: encoded),
        _ => throw ArgumentError('Método no soportado: $method'),
      };
    } catch (_) {
      throw ApiException(0, 'No se pudo conectar con el servidor.');
    }
    if (response.statusCode == 401 && retry && refreshToken != null) {
      final refreshed = await _refresh();
      if (refreshed) {
        return _send(
          method,
          path,
          body: body,
          query: query,
          authenticated: authenticated,
          retry: false,
        );
      }
    }
    if (response.statusCode >= 400) {
      throw ApiException(response.statusCode, _errorMessage(response));
    }
    return response;
  }

  Future<bool> _refresh() async {
    try {
      final response = await _client.post(
        _uri('/api/v1/auth/token/refresh/'),
        headers: {
          'Accept': 'application/json',
          'Content-Type': 'application/json',
        },
        body: jsonEncode({'refresh': refreshToken}),
      );
      if (response.statusCode >= 400) return false;
      final data = _decode(response);
      if (data is Map && data['access'] != null) {
        accessToken = data['access'].toString();
        if (data['refresh'] != null) {
          refreshToken = data['refresh'].toString();
        }
        return true;
      }
    } catch (_) {
      return false;
    }
    return false;
  }

  String _errorMessage(http.Response response) {
    try {
      final data = _decode(response);
      if (data is Map) {
        final detail = data['detail'];
        if (detail != null) return detail.toString();
        for (final value in data.values) {
          if (value is List && value.isNotEmpty) return value.first.toString();
          if (value is String && value.isNotEmpty) return value;
        }
      }
    } catch (_) {
      // fallback below
    }
    return 'Error ${response.statusCode} del servidor.';
  }

  dynamic _decode(http.Response response) {
    if (response.body.isEmpty) return null;
    return jsonDecode(utf8.decode(response.bodyBytes));
  }

  Map<String, dynamic> _decodeMap(http.Response response) {
    final data = _decode(response);
    if (data is Map<String, dynamic>) return data;
    if (data is Map) return data.map((k, v) => MapEntry('$k', v));
    return const {};
  }

  Future<Map<String, dynamic>> login(String email, String password) async {
    final response = await _send(
      'POST',
      '/api/v1/auth/token/',
      body: {'email': email.trim(), 'password': password},
      authenticated: false,
      retry: false,
    );
    final data = _decode(response) as Map<String, dynamic>;
    accessToken = data['access']?.toString();
    refreshToken = data['refresh']?.toString();
    return data;
  }

  Future<List<Map<String, dynamic>>> getList(
    String path, {
    Map<String, String>? query,
  }) async {
    final response = await _send('GET', path, query: query);
    final data = _decode(response);
    if (data is List) {
      return data
          .whereType<Map>()
          .map((item) => item.map((k, v) => MapEntry('$k', v)))
          .toList();
    }
    if (data is Map && data['results'] is List) {
      return (data['results'] as List)
          .whereType<Map>()
          .map((item) => item.map((k, v) => MapEntry('$k', v)))
          .toList();
    }
    return const [];
  }

  Future<Map<String, dynamic>> getMap(
    String path, {
    Map<String, String>? query,
  }) async {
    final response = await _send('GET', path, query: query);
    return _decodeMap(response);
  }

  Future<Map<String, dynamic>> postMap(
    String path, {
    Object? body,
    bool authenticated = true,
  }) async {
    final response = await _send(
      'POST',
      path,
      body: body ?? const {},
      authenticated: authenticated,
    );
    return _decodeMap(response);
  }

  Future<Map<String, dynamic>> patchMap(
    String path, {
    Object? body,
    bool authenticated = true,
  }) async {
    final response = await _send(
      'PATCH',
      path,
      body: body ?? const {},
      authenticated: authenticated,
    );
    return _decodeMap(response);
  }

  Future<Map<String, dynamic>> postMultipart(
    String path, {
    required String field,
    required List<int> bytes,
    required String filename,
    bool retry = true,
  }) async {
    http.Response response;
    try {
      final headers = _headers()..remove('Content-Type');
      final request = http.MultipartRequest('POST', _uri(path))
        ..headers.addAll(headers)
        ..files.add(
          http.MultipartFile.fromBytes(field, bytes, filename: filename),
        );
      response = await http.Response.fromStream(await _client.send(request));
    } catch (_) {
      throw ApiException(0, 'No se pudo conectar con el servidor.');
    }
    if (response.statusCode == 401 && retry && refreshToken != null) {
      if (await _refresh()) {
        return postMultipart(
          path,
          field: field,
          bytes: bytes,
          filename: filename,
          retry: false,
        );
      }
    }
    if (response.statusCode >= 400) {
      throw ApiException(response.statusCode, _errorMessage(response));
    }
    return _decodeMap(response);
  }

  Future<Map<String, dynamic>> deleteMap(String path) async {
    final response = await _send('DELETE', path);
    return _decodeMap(response);
  }

  Future<void> delete(String path) async {
    await _send('DELETE', path);
  }
}
