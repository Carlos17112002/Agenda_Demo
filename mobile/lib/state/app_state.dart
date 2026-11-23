import 'package:flutter/foundation.dart';
import 'package:flutter/widgets.dart';
import 'package:provider/provider.dart';

import '../data/api_client.dart';
import '../data/local_store.dart';
import '../data/models.dart';
import '../data/outbox.dart';
import '../data/session_store.dart';

enum AppStatus { loading, loggedOut, chooseCompany, ready, failure }

class AppState extends ChangeNotifier {
  AppState({ApiClient? api, LocalStore? store, SessionStore? sessions})
    : api = api ?? ApiClient(),
      _storeOverride = store,
      sessions = sessions ?? SessionStore() {
    if (_storeOverride != null) {
      this.store = _storeOverride;
      outbox = Outbox(this.store);
    }
  }

  final ApiClient api;
  final SessionStore sessions;
  final LocalStore? _storeOverride;
  late LocalStore store;
  late Outbox outbox;
  bool _storeReady = false;

  AppStatus status = AppStatus.loading;
  String? errorMessage;
  Bootstrap? bootstrap;
  List<Map<String, dynamic>> companies = [];
  List<NotificationRecord> notifications = [];
  List<OutboxItem> outboxItems = [];
  int unreadCount = 0;
  bool busy = false;
  bool offline = false;
  bool isSaasAdmin = false;
  List<PlanOption> plans = [];
  String? syncMessage;
  DateTime? lastSync;
  String? activeCompanyId;

  final Map<String, List<Map<String, dynamic>>> _cache = {};

  bool get isReady => status == AppStatus.ready;
  bool get hasSession => api.hasSession;
  int get conflictCount => outboxItems.where((item) => !item.pending).length;

  List<Map<String, dynamic>> cached(String resource) =>
      _cache[resource] ?? const [];

  bool can(String permission) =>
      bootstrap?.permissions.contains(permission) ?? false;

  bool moduleEnabled(String module) =>
      bootstrap?.moduleEnabled(module) ?? false;

  List<BookingRecord> get bookings {
    final parsed = cached('bookings')
        .map(BookingRecord.new)
        .where((booking) => booking.startAt != null)
        .toList();
    parsed.sort((a, b) => a.startAt!.compareTo(b.startAt!));
    return parsed;
  }

  List<ProductRecord> get products =>
      cached('products')
          .map(ProductRecord.new)
          .where((product) => product.active)
          .toList();

  List<WarehouseRecord> get warehouses =>
      cached('warehouses')
          .map(WarehouseRecord.new)
          .where((warehouse) => warehouse.active)
          .toList();

  List<ServiceRecord> get services =>
      cached('services')
          .map(ServiceRecord.new)
          .where((service) => service.active)
          .toList();

  List<WorkerRecord> get workers =>
      cached('workers')
          .map(WorkerRecord.new)
          .where((worker) => worker.active)
          .toList();

  List<CustomerRecord> get customers =>
      cached('customers')
          .map(CustomerRecord.new)
          .where((customer) => customer.active)
          .toList();

  List<StockRow> get stockRows {
    final byId = {for (final product in products) product.id: product};
    return cached('stock').map((raw) {
      final productId = '${raw['product']}';
      return StockRow(raw, byId[productId]);
    }).toList();
  }

  double stockFor(String productId) {
    return cached('stock')
        .where((row) => '${row['product']}' == productId)
        .fold<double>(
          0,
          (sum, row) => sum + (double.tryParse('${row['quantity']}') ?? 0),
        );
  }

  Future<void> bootstrapApp() async {
    if (!_storeReady) {
      if (_storeOverride == null) {
        store = await LocalStore.open();
      } else {
        store = _storeOverride;
      }
      outbox = Outbox(store);
      _storeReady = true;
    }
    final snapshot = await sessions.load();
    if (snapshot == null) {
      activeCompanyId = null;
      outbox.companyId = null;
      _cache.clear();
      outboxItems = [];
      status = AppStatus.loggedOut;
      notifyListeners();
      return;
    }
    api
      ..baseUrl = snapshot.baseUrl
      ..accessToken = snapshot.accessToken
      ..refreshToken = snapshot.refreshToken
      ..tenantContextId = snapshot.contextId;
    isSaasAdmin = snapshot.isSaasAdmin;
    activeCompanyId = snapshot.companyId;
    outbox.companyId = snapshot.companyId;
    await _loadCachedData();
    final cachedBootstrap = snapshot.companyId == null
        ? null
        : await store.readMeta(_bootstrapKey(snapshot.companyId!));
    if (cachedBootstrap != null) {
      bootstrap = Bootstrap.fromJson(cachedBootstrap);
      isSaasAdmin = bootstrap!.isSaasAdmin;
      status = AppStatus.ready;
      notifyListeners();
    }
    try {
      if (!await _establishContext(snapshot.companyId, snapshot.companyName)) {
        offline = false;
        syncMessage = null;
        notifyListeners();
        return;
      }
      await _loadBootstrap();
      await _refreshOnline();
    } on ApiException catch (error) {
      if (cachedBootstrap != null) {
        offline = true;
        syncMessage = 'Sin conexión: mostrando datos guardados.';
        status = AppStatus.ready;
      } else if (error.unauthorized) {
        await _clearSession();
      } else {
        errorMessage = error.message;
        status = AppStatus.failure;
      }
    }
    notifyListeners();
  }

  Future<void> login({
    required String baseUrl,
    required String email,
    required String password,
  }) async {
    _startBusy();
    try {
      api.baseUrl = baseUrl;
      final loginData = await api.login(email, password);
      final user = loginData['user'];
      isSaasAdmin = user is Map && user['is_saas_admin'] == true;
      companies = await api.getList('/api/v1/companies/mine/');
      if (companies.isEmpty) {
        throw ApiException(403, 'La cuenta no tiene empresas activas.');
      }
      await _saveSession();
      if (companies.length == 1) {
        await selectCompany(companies.first);
      } else {
        await _setCompanyScope(null);
        status = AppStatus.chooseCompany;
      }
    } on ApiException catch (error) {
      errorMessage = error.message;
      status = AppStatus.loggedOut;
    } finally {
      _stopBusy();
    }
  }

  Future<void> selectCompany(Map<String, dynamic> company) async {
    final companyId = '${company['id']}';
    final companyName = '${company['name'] ?? 'Empresa'}';
    _startBusy();
    try {
      if (!await _establishContext(companyId, companyName)) return;
      await _loadBootstrap();
      await _refreshOnline();
    } on ApiException catch (error) {
      errorMessage = error.message;
      status = AppStatus.failure;
    } finally {
      _stopBusy();
    }
  }

  Future<void> switchCompany() async {
    if (companies.isEmpty) return;
    status = AppStatus.chooseCompany;
    notifyListeners();
  }

  Future<bool> updateBranding({
    required String displayName,
    required String slug,
    required String primaryColor,
    required String secondaryColor,
    required bool darkMode,
  }) async {
    _startBusy();
    try {
      await api.patchMap(
        '/api/v1/company/branding/',
        body: {
          'display_name': displayName,
          'slug': slug,
          'primary_color': primaryColor,
          'secondary_color': secondaryColor,
          'theme_mode': darkMode ? 'dark' : 'light',
        },
      );
      await _loadBootstrap();
      return true;
    } on ApiException catch (error) {
      errorMessage = error.message;
      return false;
    } finally {
      _stopBusy();
    }
  }

  Future<bool> changePassword({
    required String currentPassword,
    required String newPassword,
  }) async {
    _startBusy();
    try {
      final data = await api.postMap(
        '/api/v1/auth/password/change/',
        body: {
          'current_password': currentPassword,
          'new_password': newPassword,
        },
      );
      final access = data['access']?.toString();
      final refresh = data['refresh']?.toString();
      if (access == null || refresh == null) {
        throw ApiException(
          500,
          'El servidor no devolvió las credenciales nuevas.',
        );
      }
      api
        ..accessToken = access
        ..refreshToken = refresh;
      await sessions.save(
        SessionSnapshot(
          baseUrl: api.baseUrl,
          accessToken: access,
          refreshToken: refresh,
          contextId: api.tenantContextId,
          companyId: activeCompanyId,
          companyName: bootstrap?.companyName,
          isSaasAdmin: isSaasAdmin,
        ),
      );
      await _loadBootstrap();
      return true;
    } on ApiException catch (error) {
      errorMessage = error.message;
      return false;
    } finally {
      _stopBusy();
    }
  }

  Future<void> loadPlans() async {
    try {
      final data = await api.getList('/api/v1/plans/');
      plans = data.map(PlanOption.fromJson).toList();
      notifyListeners();
    } on ApiException catch (error) {      errorMessage = error.message;
      notifyListeners();
    }
  }

  Future<CompanyCreationResult?> createCompany({
    required String companyName,
    required String slug,
    required String email,
    String firstName = '',
    String? planCode,
    int? trialDays,
  }) async {
    _startBusy();
    try {
      final data = await api.postMap(
        '/api/v1/saas/companies/',
        body: {
          'company_name': companyName,
          'slug': slug,
          'email': email,
          'first_name': firstName,
          'plan': ?planCode,
          'trial_days': ?trialDays,
        },
      );
      return CompanyCreationResult.fromJson(data);
    } on ApiException catch (error) {
      errorMessage = error.message;
      return null;
    } finally {
      _stopBusy();
    }
  }

  Future<bool> uploadLogo({
    required List<int> bytes,
    required String filename,
  }) async {
    _startBusy();
    try {
      await api.postMultipart(
        '/api/v1/company/branding/logo/',
        field: 'logo',
        bytes: bytes,
        filename: filename,
      );
      await _loadBootstrap();
      return true;
    } on ApiException catch (error) {
      errorMessage = error.message;
      return false;
    } finally {
      _stopBusy();
    }
  }

  Future<bool> removeLogo() async {
    _startBusy();
    try {
      await api.deleteMap('/api/v1/company/branding/logo/');
      await _loadBootstrap();
      return true;
    } on ApiException catch (error) {
      errorMessage = error.message;
      return false;
    } finally {
      _stopBusy();
    }
  }

  Future<bool> _establishContext(String? companyId, String? companyName) async {
    if (companyId == null || companyId.isEmpty) {
      if (companies.isEmpty) {
        companies = await api.getList('/api/v1/companies/mine/');
      }
      if (companies.length == 1) {
        companyId = '${companies.first['id']}';
        companyName = '${companies.first['name']}';
      } else {
        status = AppStatus.chooseCompany;
        await _setCompanyScope(null);
        return false;
      }
    }
    final shouldCreate =
        api.tenantContextId == null ||
        companyId != activeCompanyId ||
        !await _contextStillValid();
    if (!shouldCreate) return true;
    try {
      await _createContext(companyId, companyName);
      return true;
    } on ApiException catch (error) {
      if (error.statusCode != 400 &&
          error.statusCode != 403 &&
          error.statusCode != 404) {
        rethrow;
      }
    }
    // La empresa guardada ya no existe o dejó de estar accesible.
    api.tenantContextId = null;
    activeCompanyId = null;
    await _saveSession();
    companies = await api.getList('/api/v1/companies/mine/');
    if (companies.length == 1) {
      await _createContext(
        '${companies.first['id']}',
        '${companies.first['name']}',
      );
      return true;
    }
    status = AppStatus.chooseCompany;
    await _setCompanyScope(null);
    return false;
  }

  Future<void> _createContext(String companyId, String? companyName) async {
    final created = await api.postMap(
      '/api/v1/tenant-contexts/',
      body: {'company': companyId},
    );
    api.tenantContextId = created['id']?.toString();
    if (api.tenantContextId == null) {
      throw ApiException(400, 'No se pudo crear el contexto de empresa.');
    }
    await _saveSession(
      contextId: api.tenantContextId,
      companyId: companyId,
      companyName: companyName,
    );
    await _setCompanyScope(companyId);
  }

  Future<void> _saveSession({
    String? contextId,
    String? companyId,
    String? companyName,
  }) {
    return sessions.save(
      SessionSnapshot(
        baseUrl: api.baseUrl,
        accessToken: api.accessToken!,
        refreshToken: api.refreshToken!,
        contextId: contextId,
        companyId: companyId,
        companyName: companyName,
        isSaasAdmin: isSaasAdmin,
      ),
    );
  }

  Future<void> _setCompanyScope(String? companyId) async {
    activeCompanyId = companyId;
    outbox.companyId = companyId;
    if (companyId == null) api.tenantContextId = null;
    await _loadCachedData();
  }

  static String _bootstrapKey(String companyId) => 'bootstrap:$companyId';

  Future<bool> _contextStillValid() async {
    if (api.tenantContextId == null) return false;
    try {
      await api.getMap('/api/v1/mobile/bootstrap/');
      return true;
    } on ApiException catch (error) {
      return !error.unauthorized;
    }
  }

  Future<void> _loadBootstrap() async {
    final data = await api.getMap('/api/v1/mobile/bootstrap/');
    bootstrap = Bootstrap.fromJson(data);
    isSaasAdmin = bootstrap!.isSaasAdmin;
    if (bootstrap!.companies.isNotEmpty) companies = bootstrap!.companies;
    if (activeCompanyId != null) {
      await store.saveMeta(_bootstrapKey(activeCompanyId!), data);
    }
    offline = false;
    status = AppStatus.ready;
    notifyListeners();
  }

  Future<void> _refreshOnline() async {
    try {
      await registerDevice();
    } on ApiException {
      // el registro de push no bloquea el arranque
    }
    await refreshAll(silent: true);
  }

  Future<void> refreshAll({bool silent = false}) async {
    if (status != AppStatus.ready) return;
    if (!silent) _startBusy();
    syncMessage = null;
    try {
      final report = await flushOutbox();
      if (report.hasError) {
        syncMessage = 'Cambios en cola: ${report.error}';
      }
      await syncAll();
      await loadNotifications();
      await _loadCachedData();
      lastSync = DateTime.now();
      offline = false;
    } on ApiException catch (error) {
      offline = true;
      syncMessage = error.offline
          ? 'Sin conexión: los cambios quedan en la cola local.'
          : error.message;
    } finally {
      if (!silent) _stopBusy();
    }
  }

  Future<void> syncAll() async {
    final resources = bootstrap?.syncResources ?? const <String>[];
    for (final resource in resources) {
      await syncResource(resource);
    }
  }

  Future<void> syncResource(String resource) async {
    final companyId = activeCompanyId;
    if (companyId == null) return;
    var path = '/api/v1/mobile/sync/$resource/';
    var query = <String, String>{};
    String? nextSince;
    for (var page = 0; page < 20; page++) {
      final data = await api.getMap(path, query: query);
      final results = data['results'];
      final items = results is List
          ? results
                .whereType<Map>()
                .map(
                  (item) => item.map((key, value) => MapEntry('$key', value)),
                )
                .toList()
          : <Map<String, dynamic>>[];
      nextSince = data['next_since']?.toString() ?? nextSince;
      await store.mergeCache(
        resource,
        items,
        companyId: companyId,
        cursor: nextSince,
      );
      final next = data['next']?.toString();
      if (next == null || next.isEmpty) break;
      final nextUri = Uri.tryParse(next);
      if (nextUri == null) break;
      path = nextUri.path;
      query = nextUri.queryParameters;
    }
    await _loadCachedData();
  }

  Future<void> _loadCachedData() async {
    final companyId = activeCompanyId;
    if (companyId == null) {
      _cache.clear();
    } else {
      for (final resource in const [
        'bookings',
        'services',
        'workers',
        'customers',
        'products',
        'warehouses',
        'stock',
        'branches',
      ]) {
        final snapshot = await store.readCache(resource, companyId: companyId);
        _cache[resource] = snapshot.items;
      }
    }
    outboxItems = await outbox.all();
    notifyListeners();
  }

  Future<void> queueOperation(String type, Map<String, dynamic> payload) async {
    await outbox.enqueue(type, payload);
    outboxItems = await outbox.all();
    notifyListeners();
    final report = await flushOutbox();
    if (report.hasError) {
      syncMessage = 'Guardado localmente: ${report.error}';
    } else {
      await syncAll();
      await _loadCachedData();
    }
    notifyListeners();
  }

  Future<FlushReport> flushOutbox() async {
    final report = await outbox.flush((pending) async {
      final operations = pending
          .map(
            (item) => {
              'client_id': item.clientId,
              'type': item.type,
              'payload': item.payload,
            },
          )
          .toList();
      final data = await api.postMap(
        '/api/v1/mobile/operations/',
        body: {'operations': operations},
      );
      final results = data['results'];
      if (results is! List) return const [];
      return results
          .whereType<Map>()
          .map((item) => item.map((key, value) => MapEntry('$key', value)))
          .toList();
    });
    outboxItems = await outbox.all();
    notifyListeners();
    return report;
  }

  Future<void> discardOutbox(String clientId) async {
    await outbox.discard(clientId);
    outboxItems = await outbox.all();
    notifyListeners();
  }

  Future<void> retryOutbox(String clientId) async {
    if (!await outbox.retry(clientId)) return;
    outboxItems = await outbox.all();
    notifyListeners();
    final report = await flushOutbox();
    if (report.hasError) {
      syncMessage = 'Guardado localmente: ${report.error}';
      notifyListeners();
      return;
    }
    await syncAll();
    await _loadCachedData();
  }

  Future<void> loadNotifications() async {
    final data = await api.getMap('/api/v1/mobile/notifications/');
    final results = data['results'];
    notifications = results is List
        ? results
              .whereType<Map>()
              .map(
                (item) => NotificationRecord(
                  item.map((key, value) => MapEntry('$key', value)),
                ),
              )
              .toList()
        : [];
    unreadCount = int.tryParse('${data['unread_count']}') ?? 0;
    notifyListeners();
  }

  Future<void> markNotificationRead(String id) async {
    await api.postMap('/api/v1/mobile/notifications/$id/read/');
    await loadNotifications();
  }

  Future<void> markAllNotificationsRead() async {
    await api.postMap('/api/v1/mobile/notifications/read-all/');
    await loadNotifications();
  }

  Future<void> registerDevice() async {
    final installationId = await store.installationId();
    final platform = kIsWeb
        ? 'web'
        : switch (defaultTargetPlatform) {
            TargetPlatform.android => 'android',
            TargetPlatform.iOS => 'ios',
            _ => 'other',
          };
    await api.postMap(
      '/api/v1/mobile/devices/',
      body: {
        'installation_id': installationId,
        'platform': platform,
        'app_version': '1.0.0',
        'locale': 'es-CL',
      },
    );
  }

  Future<void> logout() async {
    _startBusy();
    try {
      final companyId = activeCompanyId;
      await sessions.clear();
      await store.removeMeta('bootstrap');
      if (companyId != null) {
        await store.removeMeta(_bootstrapKey(companyId));
      }
    } finally {
      _clearLocalState();
      _stopBusy();
    }
  }

  Future<void> _clearSession() async {
    await sessions.clear();
    _clearLocalState();
  }

  void _clearLocalState() {
    api
      ..accessToken = null
      ..refreshToken = null
      ..tenantContextId = null;
    bootstrap = null;
    notifications = [];
    unreadCount = 0;
    outboxItems = [];
    _cache.clear();
    activeCompanyId = null;
    outbox.companyId = null;
    offline = false;
    isSaasAdmin = false;
    syncMessage = null;
    errorMessage = null;
    status = AppStatus.loggedOut;
    notifyListeners();
  }

  void _startBusy() {
    busy = true;
    errorMessage = null;
    notifyListeners();
  }

  void _stopBusy() {
    busy = false;
    notifyListeners();
  }
}

extension AppStateProvider on BuildContext {
  AppState get app => read<AppState>();
}
