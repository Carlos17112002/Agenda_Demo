import 'package:sembast/sembast_memory.dart';
import 'package:uuid/uuid.dart';

import 'local_db.dart';
import 'models.dart';

class CacheSnapshot {
  CacheSnapshot({required this.items, this.cursor});

  final List<Map<String, dynamic>> items;
  final String? cursor;

  bool get isEmpty => items.isEmpty;
}

class LocalStore {
  LocalStore(this._db);

  final Database _db;

  static final _cacheStore = stringMapStoreFactory.store('cache');
  static final _outboxStore = stringMapStoreFactory.store('outbox');
  static final _metaStore = stringMapStoreFactory.store('meta');

  static Future<LocalStore> open() async {
    final database = await openAppDatabase();
    return LocalStore(database);
  }

  static Future<LocalStore> memory() async {
    final database = await databaseFactoryMemory.openDatabase(
      'agenda_memory_${const Uuid().v4()}',
    );
    return LocalStore(database);
  }

  static String _cacheKey(String companyId, String resource) =>
      '$companyId::$resource';

  Future<CacheSnapshot> readCache(
    String resource, {
    required String companyId,
  }) async {
    final record = await _cacheStore
        .record(_cacheKey(companyId, resource))
        .get(_db);
    if (record == null) return CacheSnapshot(items: const []);
    final rawItems = record['items'];
    final items = rawItems is List
        ? rawItems
              .whereType<Map>()
              .map(
                (item) => item.map((key, value) => MapEntry('$key', value)),
              )
              .toList()
        : <Map<String, dynamic>>[];
    return CacheSnapshot(items: items, cursor: record['cursor']?.toString());
  }

  Future<void> mergeCache(
    String resource,
    List<Map<String, dynamic>> incoming, {
    required String companyId,
    String? cursor,
  }) async {
    final snapshot = await readCache(resource, companyId: companyId);
    final merged = <String, Map<String, dynamic>>{
      for (final item in snapshot.items) '${item['id']}': item,
    };
    for (final item in incoming) {
      final id = '${item['id']}';
      if (id.isEmpty || id == 'null') continue;
      merged[id] = item;
    }
    await _cacheStore.record(_cacheKey(companyId, resource)).put(_db, {
      'items': merged.values.toList(),
      'cursor': cursor ?? snapshot.cursor,
    });
  }

  Future<void> replaceCache(
    String resource,
    List<Map<String, dynamic>> items, {
    required String companyId,
    String? cursor,
  }) {
    return _cacheStore.record(_cacheKey(companyId, resource)).put(_db, {
      'items': items,
      'cursor': cursor,
    });
  }

  Future<void> saveMeta(String key, Map<String, dynamic> value) {
    return _metaStore.record(key).put(_db, value);
  }

  Future<Map<String, dynamic>?> readMeta(String key) async {
    final record = await _metaStore.record(key).get(_db);
    if (record == null) return null;
    return record.map((mapKey, value) => MapEntry(mapKey, value));
  }

  Future<void> removeMeta(String key) => _metaStore.record(key).delete(_db);

  Future<String> installationId() async {
    final existing = await _metaStore.record('installation').get(_db);
    final id = existing?['id']?.toString();
    if (id != null && id.isNotEmpty) return id;
    final created = const Uuid().v4();
    await _metaStore.record('installation').put(_db, {'id': created});
    return created;
  }

  Future<void> addOutbox(OutboxItem item) {
    return _outboxStore.record(item.clientId).put(_db, item.toJson());
  }

  Future<List<OutboxItem>> outboxItems({String? companyId}) async {
    final records = await _outboxStore.find(
      _db,
      finder: Finder(sortOrders: [SortOrder('created_at')]),
    );
    return records
        .map((record) => OutboxItem.fromJson(record.value))
        .where((item) => item.companyId == companyId)
        .toList();
  }

  Future<void> updateOutbox(OutboxItem item) => addOutbox(item);

  Future<void> removeOutbox(String clientId) {
    return _outboxStore.record(clientId).delete(_db);
  }
}
