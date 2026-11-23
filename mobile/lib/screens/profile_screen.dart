import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';

import '../core/formatters.dart';
import '../core/theme.dart';
import '../data/api_client.dart';
import '../state/app_state.dart';
import '../widgets/common.dart';
import '../widgets/outbox_panel.dart';
import 'branding_screen.dart';
import 'create_company_screen.dart';

const _permissionLabels = {
  'bookings.read': 'Ver reservas',
  'bookings.write': 'Editar reservas',
  'bookings.own.read': 'Mi agenda',
  'bookings.own.write': 'Editar mi agenda',
  'customers.read': 'Ver clientes',
  'customers.write': 'Editar clientes',
  'customers.assigned.read': 'Clientes asignados',
  'catalog.read': 'Ver catálogo',
  'catalog.write': 'Editar catálogo',
  'workforce.read': 'Ver equipo',
  'workforce.write': 'Editar equipo',
  'inventory.read': 'Ver inventario',
  'inventory.write': 'Movimientos de stock',
  'purchases.read': 'Ver compras',
  'purchases.write': 'Editar compras',
  'sales.read': 'Ver ventas',
  'sales.write': 'Editar ventas',
  'cash.read': 'Ver caja',
  'cash.manage': 'Gestionar caja',
  'payments.read': 'Ver pagos',
  'expenses.read': 'Ver gastos',
  'expenses.write': 'Editar gastos',
  'reports.read': 'Informes',
  'subscription.read': 'Ver suscripción',
  'subscription.manage': 'Gestionar suscripción',
  'branches.read': 'Ver sucursales',
  'branches.manage': 'Editar sucursales',
};

class ProfileScreen extends StatelessWidget {
  const ProfileScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final app = context.watch<AppState>();
    final bootstrap = app.bootstrap;
    if (bootstrap == null) {
      return const Center(child: CircularProgressIndicator());
    }
    final subscription = bootstrap.subscription;
    final planName = subscription?['plan'] is Map
        ? '${(subscription!['plan'] as Map)['name'] ?? ''}'
        : null;
    final effectiveStatus = subscription?['effective_status']?.toString();
    final days = subscription?['days_remaining'];
    final permissions = bootstrap.permissions;
    final pending = app.outboxItems.where((item) => item.pending).length;

    return Scaffold(
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.only(bottom: 40),
          children: [
            ScreenHeader(
              title: 'Perfil',
              subtitle: bootstrap.user['email']?.toString(),
              trailing: IconButton(
                tooltip: 'Sincronizar',
                onPressed: app.busy
                    ? null
                    : () => context.read<AppState>().refreshAll(),
                icon: const Icon(Icons.sync_rounded),
              ),
            ),
            const SyncBanner(),
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 4, 20, 12),
              child: SurfaceCard(
                child: Row(
                  children: [
                    CircleAvatar(
                      radius: 26,
                      backgroundColor: Theme.of(context).colorScheme.primary,
                      child: Text(
                        _initials(bootstrap.userName),
                        style: TextStyle(
                          color: Theme.of(context).colorScheme.onPrimary,
                          fontWeight: FontWeight.w900,
                          fontSize: 18,
                        ),
                      ),
                    ),
                    const SizedBox(width: 14),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            bootstrap.userName,
                            style: const TextStyle(
                              fontWeight: FontWeight.w800,
                              fontSize: 17,
                            ),
                          ),
                          const SizedBox(height: 3),
                          Text(
                            bootstrap.role,
                            style: TextStyle(
                              color: context.palette.muted,
                              fontSize: 12.5,
                            ),
                          ),
                          if (bootstrap.workerName != null) ...[
                            const SizedBox(height: 3),
                            Text(
                              'Agenda de ${bootstrap.workerName}',
                              style: TextStyle(
                                color: Theme.of(context).colorScheme.primary,
                                fontSize: 11.5,
                                fontWeight: FontWeight.w700,
                              ),
                            ),
                          ],
                        ],
                      ),
                    ),
                    StatusPill(
                      label: bootstrap.billingState == 'usable'
                          ? 'Activa'
                          : bootstrap.billingState == 'legacy'
                          ? 'Heredada'
                          : 'Inactiva',
                      tone: bootstrap.billingState == 'usable'
                          ? 'success'
                          : bootstrap.billingState == 'legacy'
                          ? 'warning'
                          : 'danger',
                    ),
                  ],
                ),
              ),
            ),
            const SectionLabel('Empresa'),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 20),
              child: SurfaceCard(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        CompanyLogo(company: bootstrap.company, size: 42),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                bootstrap.companyName,
                                style: const TextStyle(
                                  fontWeight: FontWeight.w800,
                                  fontSize: 15,
                                ),
                              ),
                              Text(
                                '${bootstrap.company['slug'] ?? ''}',
                                style: TextStyle(
                                  color: context.palette.muted,
                                  fontSize: 11.5,
                                ),
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 10),
                    Text(
                      '${bootstrap.branches.length} sucursales · '
                      '${bootstrap.workerName ?? bootstrap.role}',
                      style: TextStyle(
                        color: context.palette.muted,
                        fontSize: 12,
                      ),
                    ),
                    if (bootstrap.companyBookingUrl.isNotEmpty) ...[
                      const SizedBox(height: 14),
                      InkWell(
                        onTap: () => _copyBookingUrl(
                          context,
                          bootstrap.companyBookingUrl,
                        ),
                        borderRadius: BorderRadius.circular(12),
                        child: Container(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 12,
                            vertical: 10,
                          ),
                          decoration: BoxDecoration(
                            color: context.palette.background,
                            borderRadius: BorderRadius.circular(12),
                            border: Border.all(color: context.palette.border),
                          ),
                          child: Row(
                            children: [
                              Icon(
                                Icons.link_rounded,
                                size: 16,
                                color: Theme.of(context).colorScheme.primary,
                              ),
                              const SizedBox(width: 8),
                              Expanded(
                                child: Text(
                                  bootstrap.companyBookingUrl,
                                  maxLines: 1,
                                  overflow: TextOverflow.ellipsis,
                                  style: const TextStyle(fontSize: 11.5),
                                ),
                              ),
                              Icon(
                                Icons.copy_rounded,
                                size: 15,
                                color: context.palette.muted,
                              ),
                            ],
                          ),
                        ),
                      ),
                      const SizedBox(height: 5),
                      Text(
                        'Enlace público de reservas de la empresa',
                        style: TextStyle(
                          color: context.palette.muted,
                          fontSize: 10.5,
                        ),
                      ),
                    ],
                    if (app.can('company.manage')) ...[
                      const SizedBox(height: 14),
                      OutlinedButton.icon(
                        key: const Key('branding-open'),
                        onPressed: app.busy
                            ? null
                            : () => _openBranding(context),
                        icon: const Icon(Icons.palette_outlined, size: 18),
                        label: const Text('Editar marca'),
                      ),
                    ],
                    if (app.isSaasAdmin) ...[
                      const SizedBox(height: 14),
                      OutlinedButton.icon(
                        key: const Key('create-company-profile'),
                        onPressed: app.busy
                            ? null
                            : () => _openCreateCompany(context),
                        icon: const Icon(Icons.add_business_rounded, size: 18),
                        label: const Text('Crear empresa'),
                      ),
                    ],
                    if (app.companies.length > 1) ...[
                      const SizedBox(height: 14),
                      OutlinedButton.icon(
                        onPressed: app.busy ? null : app.switchCompany,
                        icon: const Icon(Icons.swap_horiz_rounded, size: 18),
                        label: const Text('Cambiar empresa'),
                      ),
                    ],
                  ],
                ),
              ),
            ),
            const SectionLabel('Suscripción'),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 20),
              child: SurfaceCard(
                child: Row(
                  children: [
                    Icon(
                      Icons.workspace_premium_outlined,
                      color: Theme.of(context).colorScheme.primary,
                      size: 22,
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            planName == null || planName.isEmpty
                                ? 'Sin plan registrado'
                                : planName,
                            style: const TextStyle(
                              fontWeight: FontWeight.w800,
                              fontSize: 14,
                            ),
                          ),
                          const SizedBox(height: 3),
                          Text(
                            _subscriptionLine(
                              bootstrap.billingState,
                              effectiveStatus,
                              days,
                            ),
                            style: TextStyle(
                              color: context.palette.muted,
                              fontSize: 12,
                              height: 1.35,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ),
            const SectionLabel('Módulos'),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 20),
              child: Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  for (final entry in bootstrap.modules.entries)
                    StatusPill(
                      label: _moduleLabel(entry.key),
                      tone: entry.value == true ? 'success' : 'danger',
                    ),
                ],
              ),
            ),
            SectionLabel('Permisos activos (${permissions.length})'),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 20),
              child: SurfaceCard(
                padding: EdgeInsets.zero,
                child: ExpansionTile(
                  shape: const Border(),
                  collapsedShape: const Border(),
                  tilePadding: const EdgeInsets.symmetric(horizontal: 16),
                  childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
                  iconColor: context.palette.muted,
                  collapsedIconColor: context.palette.muted,
                  title: const Text(
                    'Validados en el servidor',
                    style: TextStyle(fontSize: 13, fontWeight: FontWeight.w700),
                  ),
                  subtitle: Text(
                    'La app solo muestra lo permitido; cada acción se valida en la API.',
                    style: TextStyle(
                      color: context.palette.muted,
                      fontSize: 11,
                    ),
                  ),
                  children: [
                    Wrap(
                      spacing: 6,
                      runSpacing: 6,
                      children: [
                        for (final permission in permissions)
                          Container(
                            padding: const EdgeInsets.symmetric(
                              horizontal: 9,
                              vertical: 5,
                            ),
                            decoration: BoxDecoration(
                              color: context.palette.background,
                              borderRadius: BorderRadius.circular(8),
                              border: Border.all(color: context.palette.border),
                            ),
                            child: Text(
                              _permissionLabels[permission] ?? permission,
                              style: TextStyle(
                                fontSize: 11,
                                color: context.palette.muted,
                              ),
                            ),
                          ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
            const SectionLabel('Sincronización'),
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 0, 20, 8),
              child: SurfaceCard(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      app.lastSync == null
                          ? 'Aún no sincronizas en esta sesión.'
                          : 'Última sincronización ${relativeTime(app.lastSync)}',
                      style: const TextStyle(fontSize: 12.5),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      '$pending operaciones pendientes · '
                      '${bootstrap.syncResources.length} recursos disponibles',
                      style: TextStyle(
                        color: context.palette.muted,
                        fontSize: 11.5,
                      ),
                    ),
                    const SizedBox(height: 12),
                    Row(
                      children: [
                        Expanded(
                          child: OutlinedButton(
                            onPressed: app.busy ? null : () => _flush(context),
                            child: const Text('Sincronizar ahora'),
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
            const OutboxPanel(showPending: true),
            const SizedBox(height: 22),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 20),
              child: OutlinedButton.icon(
                onPressed: app.busy ? null : () => _logout(context),
                style: OutlinedButton.styleFrom(
                  foregroundColor: Theme.of(context).colorScheme.error,
                  side: BorderSide(color: Theme.of(context).colorScheme.error),
                ),
                icon: const Icon(Icons.logout_rounded, size: 18),
                label: const Text('Cerrar sesión'),
              ),
            ),
            const SizedBox(height: 18),
            Center(
              child: Text(
                '${bootstrap.companyName} · AGENDA móvil',
                style: TextStyle(
                  color: context.palette.muted,
                  fontSize: 10.5,
                  letterSpacing: 1.5,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  void _copyBookingUrl(BuildContext context, String url) {
    Clipboard.setData(ClipboardData(text: url));
    ScaffoldMessenger.of(
      context,
    ).showSnackBar(const SnackBar(content: Text('Enlace de reservas copiado')));
  }

  void _openBranding(BuildContext context) {
    Navigator.of(context)
        .push(MaterialPageRoute(builder: (_) => const BrandingScreen()));
  }

  void _openCreateCompany(BuildContext context) {
    Navigator.of(context)
        .push(MaterialPageRoute(builder: (_) => const CreateCompanyScreen()));
  }

  static String _initials(String name) {
    final parts = name
        .split(RegExp(r'\s+'))
        .where((part) => part.isNotEmpty)
        .toList();
    if (parts.isEmpty) return 'A';
    if (parts.length == 1) return parts.first.substring(0, 1).toUpperCase();
    return (parts.first.substring(0, 1) + parts.last.substring(0, 1))
        .toUpperCase();
  }

  static String _moduleLabel(String key) => switch (key) {
    'agenda' => 'Agenda',
    'inventory' => 'Inventario',
    'customers' => 'Clientes',
    'subscription' => 'Suscripción',
    _ => key,
  };

  static String _subscriptionLine(
    String billingState,
    String? effectiveStatus,
    dynamic days,
  ) {
    if (billingState == 'legacy') {
      return 'Acceso heredado sin historial de suscripción.';
    }
    if (billingState == 'inactive') {
      return 'Suscripción inactiva: regulariza el pago para seguir operando.';
    }
    final status = effectiveStatus ?? 'activa';
    if (days == null) return 'Estado: $status';
    return 'Estado: $status · $days días restantes';
  }

  Future<void> _flush(BuildContext context) async {
    final app = context.read<AppState>();
    try {
      final report = await app.flushOutbox();
      await app.syncAll();
      if (!context.mounted) return;
      final message =
          report.error ??
          'Sincronizado: ${report.applied} aplicadas, '
              '${report.conflicts} conflictos.';
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(message),
          backgroundColor: report.error != null
              ? Theme.of(context).colorScheme.error
              : context.palette.surfaceAlt,
        ),
      );
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

  Future<void> _logout(BuildContext context) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        backgroundColor: context.palette.surface,
        title: const Text('Cerrar sesión'),
        content: const Text(
          'Se borrarán los datos locales de esta empresa. Las operaciones pendientes se perderán.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext, false),
            child: const Text('Volver'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(dialogContext, true),
            child: const Text('Cerrar sesión'),
          ),
        ],
      ),
    );
    if (confirmed != true || !context.mounted) return;
    await context.read<AppState>().logout();
  }
}
