import 'package:agenda_mobile/data/local_store.dart';
import 'package:agenda_mobile/data/models.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('mergeCache upserts by id and preserves the cursor', () async {
    final store = await LocalStore.memory();
    await store.mergeCache('products', [
      {'id': 'a', 'name': 'Uno'},
    ], companyId: 'c1', cursor: '2026-01-01T00:00:00Z');
    await store.mergeCache('products', [
      {'id': 'a', 'name': 'Uno editado'},
      {'id': 'b', 'name': 'Dos'},
    ], companyId: 'c1');

    final snapshot = await store.readCache('products', companyId: 'c1');

    expect(snapshot.items, hasLength(2));
    expect(
      snapshot.items.firstWhere((item) => item['id'] == 'a')['name'],
      'Uno editado',
    );
    expect(snapshot.cursor, '2026-01-01T00:00:00Z');
  });

  test('replaceCache discards previous items', () async {
    final store = await LocalStore.memory();
    await store.mergeCache('stock', [
      {'id': 'old', 'quantity': 3},
    ], companyId: 'c1');
    await store.replaceCache('stock', [
      {'id': 'new', 'quantity': 8},
    ], companyId: 'c1', cursor: '2026-02-02T00:00:00Z');

    final snapshot = await store.readCache('stock', companyId: 'c1');

    expect(snapshot.items, hasLength(1));
    expect(snapshot.items.single['id'], 'new');
    expect(snapshot.cursor, '2026-02-02T00:00:00Z');
  });

  test('cached resources are isolated per company', () async {
    final store = await LocalStore.memory();
    await store.mergeCache('products', [
      {'id': 'a', 'name': 'Solo empresa A'},
    ], companyId: 'a');
    await store.replaceCache('products', [], companyId: 'b');

    final companyA = await store.readCache('products', companyId: 'a');
    final companyB = await store.readCache('products', companyId: 'b');

    expect(companyA.items, hasLength(1));
    expect(companyB.items, isEmpty);
  });

  test('outbox items are listed only for their company', () async {
    final store = await LocalStore.memory();
    await store.addOutbox(
      OutboxItem(
        clientId: 'client-a',
        type: 'booking.create',
        payload: {'service': 's1'},
        createdAt: '2026-01-01T10:00:00Z',
        companyId: 'a',
      ),
    );
    await store.addOutbox(
      OutboxItem(
        clientId: 'client-b',
        type: 'booking.create',
        payload: {'service': 's2'},
        createdAt: '2026-01-01T11:00:00Z',
        companyId: 'b',
      ),
    );

    final companyA = await store.outboxItems(companyId: 'a');

    expect(companyA.single.clientId, 'client-a');
    expect(await store.outboxItems(companyId: 'c'), isEmpty);
  });

  test('installation id is generated once and reused', () async {
    final store = await LocalStore.memory();

    final first = await store.installationId();
    final second = await store.installationId();

    expect(first, isNotEmpty);
    expect(second, first);
  });

  test('outbox items survive a store roundtrip with status', () async {
    final store = await LocalStore.memory();
    final item = OutboxItem(
      clientId: 'client-1',
      type: 'inventory.movement',
      payload: {'product': 'p1', 'quantity': '2.000'},
      createdAt: '2026-01-01T10:00:00Z',
    );
    await store.addOutbox(item);

    item
      ..status = 'conflict'
      ..error = 'Stock insuficiente';
    await store.updateOutbox(item);

    final stored = await store.outboxItems();

    expect(stored, hasLength(1));
    expect(stored.single.clientId, 'client-1');
    expect(stored.single.pending, isFalse);
    expect(stored.single.error, 'Stock insuficiente');
  });
}
