import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/formatters.dart';
import '../core/theme.dart';
import '../data/api_client.dart';
import '../data/models.dart';
import '../state/app_state.dart';
import '../widgets/common.dart';
import '../widgets/outbox_panel.dart';

class NotificationsScreen extends StatelessWidget {
  const NotificationsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final app = context.watch<AppState>();
    final notifications = app.notifications;

    return Scaffold(
      body: SafeArea(
        child: RefreshIndicator(
          color: Theme.of(context).colorScheme.primary,
          onRefresh: () => context.read<AppState>().refreshAll(),
          child: ListView(
            physics: const AlwaysScrollableScrollPhysics(),
            padding: const EdgeInsets.only(bottom: 40),
            children: [
              ScreenHeader(
                title: 'Alertas',
                subtitle: app.unreadCount == 0
                    ? 'Todo al día'
                    : '${app.unreadCount} sin leer',
                trailing: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    if (app.unreadCount > 0)
                      TextButton(
                        onPressed: () => _run(
                          context,
                          () => context
                              .read<AppState>()
                              .markAllNotificationsRead(),
                        ),
                        child: const Text('Leer todo'),
                      ),
                    IconButton(
                      tooltip: 'Sincronizar',
                      onPressed: app.busy
                          ? null
                          : () => context.read<AppState>().refreshAll(),
                      icon: const Icon(Icons.sync_rounded),
                    ),
                  ],
                ),
              ),
              const SyncBanner(),
              const Padding(
                padding: EdgeInsets.fromLTRB(20, 4, 20, 10),
                child: _DeviceCard(),
              ),
              const OutboxPanel(),
              if (notifications.isEmpty)
                const EmptyState(
                  icon: Icons.notifications_none_rounded,
                  title: 'Sin notificaciones',
                  message:
                      'Aquí llegan las reservas, cancelaciones y alertas de stock de la empresa activa.',
                )
              else ...[
                const SectionLabel('Centro de notificaciones'),
                for (final notification in notifications)
                  Padding(
                    padding: const EdgeInsets.fromLTRB(20, 0, 20, 10),
                    child: _NotificationCard(
                      notification: notification,
                      onTap: notification.unread
                          ? () => _run(
                              context,
                              () => context
                                  .read<AppState>()
                                  .markNotificationRead(notification.id),
                            )
                          : null,
                    ),
                  ),
              ],
            ],
          ),
        ),
      ),
    );
  }

  Future<void> _run(
    BuildContext context,
    Future<void> Function() action,
  ) async {
    try {
      await action();
    } on ApiException catch (error) {
      if (!context.mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(error.message),
          backgroundColor: Theme.of(context).colorScheme.error,
        ),
      );
    }
  }
}

class _DeviceCard extends StatelessWidget {
  const _DeviceCard();

  @override
  Widget build(BuildContext context) {
    final app = context.watch<AppState>();
    return SurfaceCard(
      child: Row(
        children: [
          Container(
            width: 46,
            height: 46,
            decoration: BoxDecoration(
              color: Theme.of(context).colorScheme.secondary,
              borderRadius: BorderRadius.circular(13),
            ),
            alignment: Alignment.center,
            child: Icon(
              Icons.notifications_active_outlined,
              color: Theme.of(context).colorScheme.onSecondary,
              size: 22,
            ),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Este dispositivo',
                  style: TextStyle(fontWeight: FontWeight.w800, fontSize: 14),
                ),
                const SizedBox(height: 3),
                Text(
                  'Registrado para alertas. El push nativo se activa al integrar FCM; por ahora las alertas se consultan aquí.',
                  style: TextStyle(
                    color: context.palette.muted,
                    fontSize: 11.5,
                    height: 1.35,
                  ),
                ),
              ],
            ),
          ),
          IconButton(
            tooltip: 'Actualizar registro',
            onPressed: app.busy
                ? null
                : () async {
                    try {
                      await context.read<AppState>().registerDevice();
                      if (!context.mounted) return;
                      ScaffoldMessenger.of(context).showSnackBar(
                        const SnackBar(
                          content: Text('Dispositivo registrado'),
                        ),
                      );
                    } on ApiException catch (error) {
                      if (!context.mounted) return;
                      ScaffoldMessenger.of(context).showSnackBar(
                        SnackBar(
                          content: Text(error.message),
                          backgroundColor: Theme.of(
                            context,
                          ).colorScheme.error,
                        ),
                      );
                    }
                  },
            icon: Icon(
              app.offline ? Icons.cloud_off_rounded : Icons.verified_outlined,
              color: app.offline
                  ? Theme.of(context).colorScheme.error
                  : context.palette.muted,
            ),
          ),
        ],
      ),
    );
  }
}

class _NotificationCard extends StatelessWidget {
  const _NotificationCard({required this.notification, this.onTap});

  final NotificationRecord notification;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final unread = notification.unread;
    return SurfaceCard(
      onTap: onTap,
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(
            _iconFor(notification.kind),
            size: 20,
            color: unread
                ? Theme.of(context).colorScheme.primary
                : context.palette.muted,
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        notification.title,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(
                          fontWeight: unread
                              ? FontWeight.w800
                              : FontWeight.w600,
                          fontSize: 14,
                        ),
                      ),
                    ),
                    if (unread)
                      Container(
                        width: 7,
                        height: 7,
                        decoration: BoxDecoration(
                          color: Theme.of(context).colorScheme.primary,
                          shape: BoxShape.circle,
                        ),
                      ),
                  ],
                ),
                const SizedBox(height: 4),
                Text(
                  notification.body,
                  maxLines: 3,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(
                    color: context.palette.muted,
                    fontSize: 12.5,
                    height: 1.4,
                  ),
                ),
                const SizedBox(height: 6),
                Text(
                  relativeTime(notification.createdAt),
                  style: TextStyle(
                    color: context.palette.muted,
                    fontSize: 10.5,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  IconData _iconFor(String kind) {
    return switch (kind) {
      'booking_created' => Icons.event_available_rounded,
      'booking_confirmed' => Icons.verified_rounded,
      'booking_rescheduled' => Icons.update_rounded,
      'booking_canceled' => Icons.event_busy_rounded,
      'low_stock' => Icons.warning_amber_rounded,
      _ => Icons.notifications_none_rounded,
    };
  }
}
