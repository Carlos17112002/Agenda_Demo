import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/theme.dart';
import '../state/app_state.dart';
import 'common.dart';

const _labels = {
  'booking.create': 'Nueva reserva',
  'booking.cancel': 'Cancelación',
  'booking.reschedule': 'Reprogramación',
  'inventory.movement': 'Movimiento de stock',
};

class OutboxPanel extends StatelessWidget {
  const OutboxPanel({super.key, this.showPending = false});

  final bool showPending;

  @override
  Widget build(BuildContext context) {
    final app = context.watch<AppState>();
    final items = app.outboxItems
        .where((item) => showPending || !item.pending)
        .toList();
    if (items.isEmpty) return const SizedBox.shrink();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SectionLabel(showPending ? 'Cola de sincronización' : 'Cambios con conflicto'),
        for (final item in items)
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 0, 20, 8),
            child: SurfaceCard(
              padding: const EdgeInsets.all(14),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Icon(
                        item.pending
                            ? Icons.schedule_send_rounded
                            : Icons.error_outline_rounded,
                        size: 17,
                        color: item.pending
                            ? context.palette.muted
                            : Theme.of(context).colorScheme.error,
                      ),
                      const SizedBox(width: 9),
                      Expanded(
                        child: Text(
                          _labels[item.type] ?? item.type,
                          style: const TextStyle(
                            fontWeight: FontWeight.w800,
                            fontSize: 13,
                          ),
                        ),
                      ),
                      StatusPill(
                        label: item.pending ? 'Pendiente' : 'Conflicto',
                        tone: item.pending ? 'warning' : 'danger',
                      ),
                    ],
                  ),
                  if (item.error != null) ...[
                    const SizedBox(height: 6),
                    Text(
                      item.error!,
                      maxLines: 3,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(
                        color: context.palette.muted,
                        fontSize: 11.5,
                        height: 1.35,
                      ),
                    ),
                  ],
                  const SizedBox(height: 6),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.end,
                    children: [
                      TextButton(
                        onPressed: () => context
                            .read<AppState>()
                            .discardOutbox(item.clientId),
                        child: const Text('Descartar'),
                      ),
                      if (!item.pending)
                        FilledButton(
                          onPressed: () => context
                              .read<AppState>()
                              .retryOutbox(item.clientId),
                          style: FilledButton.styleFrom(
                            minimumSize: const Size(0, 34),
                            padding: const EdgeInsets.symmetric(horizontal: 14),
                          ),
                          child: const Text('Reintentar'),
                        ),
                    ],
                  ),
                ],
              ),
            ),
          ),
      ],
    );
  }
}
