import 'package:agenda_mobile/data/api_client.dart';
import 'package:agenda_mobile/data/local_store.dart';
import 'package:agenda_mobile/data/outbox.dart';
import 'package:flutter_test/flutter_test.dart';

Future<Outbox> _outbox() async => Outbox(await LocalStore.memory());

void main() {
  test('applied operations leave the queue', () async {
    final outbox = await _outbox();
    final item = await outbox.enqueue('booking.create', {'service': 's1'});

    final report = await outbox.flush(
      (pending) async => [
        {'client_id': item.clientId, 'status': 'applied'},
      ],
    );

    expect(report.applied, 1);
    expect(report.conflicts, 0);
    expect(await outbox.all(), isEmpty);
  });

  test('conflicts stay queued with a readable description', () async {
    final outbox = await _outbox();
    final item = await outbox.enqueue('booking.reschedule', {});

    final report = await outbox.flush(
      (pending) async => [
        {
          'client_id': item.clientId,
          'status': 'conflict',
          'error': {'detail': 'La reserva fue modificada por otra persona.'},
        },
      ],
    );

    final stored = (await outbox.all()).single;
    expect(report.conflicts, 1);
    expect(stored.pending, isFalse);
    expect(stored.status, 'conflict');
    expect(stored.error, 'La reserva fue modificada por otra persona.');
  });

  test('rejected operations keep the server validation message', () async {
    final outbox = await _outbox();
    final item = await outbox.enqueue('booking.cancel', {});

    final report = await outbox.flush(
      (pending) async => [
        {
          'client_id': item.clientId,
          'status': 'rejected',
          'error': {'booking': ['La reserva no existe en la empresa activa.']},
        },
      ],
    );

    final stored = (await outbox.all()).single;
    expect(report.rejected, 1);
    expect(stored.status, 'rejected');
    expect(stored.error, '[La reserva no existe en la empresa activa.]');
  });

  test('network failures preserve pending work', () async {
    final outbox = await _outbox();
    await outbox.enqueue('inventory.movement', {'quantity': '1.000'});

    final report = await outbox.flush(
      (pending) async => throw ApiException(0, 'No se pudo conectar.'),
    );

    expect(report.error, 'No se pudo conectar.');
    expect((await outbox.all()).single.pending, isTrue);
  });

  test('retry puts a conflicted operation back in the queue', () async {
    final outbox = await _outbox();
    final item = await outbox.enqueue('booking.create', {});
    await outbox.flush(
      (pending) async => [
        {'client_id': item.clientId, 'status': 'conflict', 'error': 'Ocupado'},
      ],
    );

    expect(await outbox.retry(item.clientId), isTrue);

    final stored = (await outbox.all()).single;
    expect(stored.pending, isTrue);
    expect(stored.error, isNull);

    final report = await outbox.flush(
      (pending) async => [
        {'client_id': item.clientId, 'status': 'applied'},
      ],
    );
    expect(report.applied, 1);
    expect(await outbox.all(), isEmpty);
  });
}
