import 'package:uuid/uuid.dart';

import 'api_client.dart';
import 'local_store.dart';
import 'models.dart';

typedef OperationSender =
    Future<List<Map<String, dynamic>>> Function(List<OutboxItem> pending);

class FlushReport {
  FlushReport({
    this.applied = 0,
    this.conflicts = 0,
    this.rejected = 0,
    this.error,
  });

  final int applied;
  final int conflicts;
  final int rejected;
  final String? error;

  bool get hasError => error != null;
}

class Outbox {
  Outbox(this._store, {this.uuid = const Uuid(), this.companyId});

  final LocalStore _store;
  final Uuid uuid;
  String? companyId;

  Future<OutboxItem> enqueue(
    String type,
    Map<String, dynamic> payload,
  ) async {
    final item = OutboxItem(
      clientId: uuid.v4(),
      type: type,
      payload: payload,
      createdAt: DateTime.now().toUtc().toIso8601String(),
      companyId: companyId,
    );
    await _store.addOutbox(item);
    return item;
  }

  Future<List<OutboxItem>> all() => _store.outboxItems(companyId: companyId);

  Future<List<OutboxItem>> pending() async {
    final items = await all();
    return items.where((item) => item.pending).toList();
  }

  Future<void> discard(String clientId) => _store.removeOutbox(clientId);

  Future<bool> retry(String clientId) async {
    for (final item in await all()) {
      if (item.clientId != clientId || item.pending) continue;
      item
        ..status = 'pending'
        ..error = null;
      await _store.updateOutbox(item);
      return true;
    }
    return false;
  }

  Future<FlushReport> flush(OperationSender sender) async {
    final items = await pending();
    if (items.isEmpty) return FlushReport();
    List<Map<String, dynamic>> results;
    try {
      results = await sender(items);
    } on ApiException catch (error) {
      return FlushReport(error: error.message);
    }
    var applied = 0;
    var conflicts = 0;
    var rejected = 0;
    final byClient = {for (final item in items) item.clientId: item};
    for (final result in results) {
      final clientId = result['client_id']?.toString();
      final item = byClient[clientId];
      if (item == null) continue;
      final status = result['status']?.toString() ?? 'rejected';
      if (status == 'applied') {
        await _store.removeOutbox(item.clientId);
        applied++;
        continue;
      }
      item.status = status == 'conflict' ? 'conflict' : 'rejected';
      item.error = _describeError(result['error']) ?? 'La operación no se aplicó.';
      await _store.updateOutbox(item);
      if (status == 'conflict') {
        conflicts++;
      } else {
        rejected++;
      }
    }
    return FlushReport(
      applied: applied,
      conflicts: conflicts,
      rejected: rejected,
    );
  }

  String? _describeError(dynamic error) {
    if (error == null) return null;
    if (error is String) return error;
    if (error is Map) {
      final detail = error['detail'];
      if (detail is String) return detail;
      if (detail is List && detail.isNotEmpty) return detail.first.toString();
      if (detail != null) return detail.toString();
      if (error.values.isEmpty) return null;
      return error.values.first?.toString();
    }
    return error.toString();
  }
}
