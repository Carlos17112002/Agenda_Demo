import 'package:flutter_secure_storage/flutter_secure_storage.dart';

class SessionSnapshot {
  SessionSnapshot({
    required this.baseUrl,
    required this.accessToken,
    required this.refreshToken,
    this.contextId,
    this.companyId,
    this.companyName,
    this.isSaasAdmin = false,
  });

  final String baseUrl;
  final String accessToken;
  final String refreshToken;
  final String? contextId;
  final String? companyId;
  final String? companyName;
  final bool isSaasAdmin;
}

class SessionStore {
  SessionStore({FlutterSecureStorage? storage})
    : _storage = storage ?? const FlutterSecureStorage();

  final FlutterSecureStorage _storage;

  static const _baseUrlKey = 'agenda.base_url';
  static const _accessKey = 'agenda.access';
  static const _refreshKey = 'agenda.refresh';
  static const _contextKey = 'agenda.context';
  static const _companyKey = 'agenda.company';
  static const _companyNameKey = 'agenda.company_name';
  static const _saasAdminKey = 'agenda.saas_admin';

  Future<SessionSnapshot?> load() async {
    final access = await _storage.read(key: _accessKey);
    final refresh = await _storage.read(key: _refreshKey);
    if (access == null || refresh == null) return null;
    return SessionSnapshot(
      baseUrl: await _storage.read(key: _baseUrlKey) ?? 'http://127.0.0.1:8000',
      accessToken: access,
      refreshToken: refresh,
      contextId: await _storage.read(key: _contextKey),
      companyId: await _storage.read(key: _companyKey),
      companyName: await _storage.read(key: _companyNameKey),
      isSaasAdmin: await _storage.read(key: _saasAdminKey) == 'true',
    );
  }

  Future<void> save(SessionSnapshot snapshot) async {
    await _storage.write(key: _baseUrlKey, value: snapshot.baseUrl);
    await _storage.write(key: _accessKey, value: snapshot.accessToken);
    await _storage.write(key: _refreshKey, value: snapshot.refreshToken);
    await _storage.write(key: _contextKey, value: snapshot.contextId);
    await _storage.write(key: _companyKey, value: snapshot.companyId);
    await _storage.write(key: _companyNameKey, value: snapshot.companyName);
    await _storage.write(
      key: _saasAdminKey,
      value: '${snapshot.isSaasAdmin}',
    );
  }

  Future<void> clear() => _storage.deleteAll();
}
