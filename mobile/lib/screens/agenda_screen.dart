import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/formatters.dart';
import '../core/theme.dart';
import '../data/branch_selection.dart';
import '../data/models.dart';
import '../state/app_state.dart';
import '../widgets/common.dart';

class AgendaScreen extends StatefulWidget {
  const AgendaScreen({super.key});

  @override
  State<AgendaScreen> createState() => _AgendaScreenState();
}

class _AgendaScreenState extends State<AgendaScreen> {
  String _filter = 'Próximas';

  @override
  Widget build(BuildContext context) {
    final app = context.watch<AppState>();
    final bookings = app.bookings;
    final now = DateTime.now();
    final filtered = switch (_filter) {
      'Hoy' => bookings
          .where(
            (booking) =>
                booking.startAt!.toLocal().day == now.day &&
                booking.startAt!.toLocal().month == now.month &&
                booking.startAt!.toLocal().year == now.year,
          )
          .toList(),
      'Todas' => bookings,
      _ => bookings
          .where(
            (booking) =>
                booking.startAt!.isAfter(now.subtract(const Duration(hours: 2))) &&
                booking.isActive,
          )
          .toList(),
    };
    final canWrite = app.can('bookings.write');

    return Scaffold(
      floatingActionButton: app.moduleEnabled('agenda') && canWrite
          ? FloatingActionButton.extended(
              onPressed: () => _createBooking(context),
              icon: const Icon(Icons.add_rounded),
              label: const Text('Reservar'),
            )
          : null,
      body: SafeArea(
        child: RefreshIndicator(
          color: Theme.of(context).colorScheme.primary,
          onRefresh: () => context.read<AppState>().refreshAll(),
          child: ListView(
            physics: const AlwaysScrollableScrollPhysics(),
            padding: const EdgeInsets.only(bottom: 120),
            children: [
              ScreenHeader(
                title: 'Agenda',
                subtitle:
                    '${app.bootstrap?.companyName ?? ''} · ${friendlyDay(now)} ${formatDate(now)}',
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
                padding: const EdgeInsets.symmetric(horizontal: 20),
                child: Row(
                  children: [
                    _Metric(
                      value: '${filtered.where((b) => b.isActive).length}',
                      label: 'ACTIVAS',
                    ),
                    const SizedBox(width: 10),
                    _Metric(
                      value:
                          '${bookings.where((b) => b.startAt!.isAfter(now) && b.isActive).length}',
                      label: 'PRÓXIMAS',
                    ),
                    const SizedBox(width: 10),
                    _Metric(
                      value:
                          '${bookings.where((b) => b.startAt!.toLocal().day == now.day && b.isActive).length}',
                      label: 'HOY',
                    ),
                  ],
                ),
              ),
              Padding(
                padding: const EdgeInsets.fromLTRB(20, 18, 20, 4),
                child: Wrap(
                  spacing: 8,
                  children: [
                    for (final option in const ['Próximas', 'Hoy', 'Todas'])
                      ChoiceChip(
                        label: Text(option),
                        selected: _filter == option,
                        onSelected: (_) => setState(() => _filter = option),
                        selectedColor: Theme.of(context).colorScheme.secondary,
                        backgroundColor: context.palette.surface,
                        side: BorderSide(color: context.palette.border),
                        labelStyle: TextStyle(
                          color: _filter == option
                              ? Theme.of(context).colorScheme.onSecondary
                              : context.palette.muted,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                  ],
                ),
              ),
              if (!app.moduleEnabled('agenda'))
                const EmptyState(
                  icon: Icons.lock_outline_rounded,
                  title: 'Agenda no incluida',
                  message:
                      'El plan actual no incluye reservas o tu rol no tiene acceso.',
                )
              else if (filtered.isEmpty)
                EmptyState(
                  icon: Icons.event_available_outlined,
                  title: 'Sin reservas',
                  message:
                      'No hay reservas para este filtro. Desliza hacia abajo para sincronizar.',
                  action: canWrite
                      ? OutlinedButton(
                          onPressed: () => _createBooking(context),
                          child: const Text('Crear reserva'),
                        )
                      : null,
                )
              else
                ..._grouped(filtered),
            ],
          ),
        ),
      ),
    );
  }

  List<Widget> _grouped(List<BookingRecord> bookings) {
    final groups = <String, List<BookingRecord>>{};
    for (final booking in bookings) {
      final key = friendlyDay(booking.startAt!);
      groups.putIfAbsent(key, () => []).add(booking);
    }
    final widgets = <Widget>[];
    for (final entry in groups.entries) {
      widgets.add(SectionLabel(entry.key));
      for (final booking in entry.value) {
        widgets.add(
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 0, 20, 10),
            child: _BookingCard(
              booking: booking,
              onTap: () => _openBooking(context, booking),
            ),
          ),
        );
      }
    }
    return widgets;
  }

  Future<void> _createBooking(BuildContext context) async {
    final app = context.read<AppState>();
    if (app.services.isEmpty ||
        app.workers.isEmpty ||
        app.customers.isEmpty ||
        (app.bootstrap?.branches.isEmpty ?? true)) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(
            'Sincroniza los catálogos antes de crear una reserva (servicios, profesionales y clientes).',
          ),
        ),
      );
      return;
    }
    final payload = await showModalBottomSheet<Map<String, dynamic>>(
      context: context,
      isScrollControlled: true,
      backgroundColor: context.palette.surface,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      builder: (_) => const _CreateBookingSheet(),
    );
    if (payload == null || !context.mounted) return;
    await _queue(context, 'booking.create', payload, title: 'Reserva creada');
  }

  Future<void> _openBooking(
    BuildContext context,
    BookingRecord booking,
  ) async {
    final action = await showModalBottomSheet<String>(
      context: context,
      backgroundColor: context.palette.surface,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      builder: (_) => _BookingDetailSheet(booking: booking),
    );
    if (action == null || !context.mounted) return;
    if (action == 'cancel') {
      await _cancelBooking(context, booking);
      return;
    }
    if (action == 'reschedule' && context.mounted) {
      await _rescheduleBooking(context, booking);
    }
  }

  Future<void> _cancelBooking(
    BuildContext context,
    BookingRecord booking,
  ) async {
    final reason = await showDialog<String>(
      context: context,
      builder: (dialogContext) {
        final controller = TextEditingController();
        return AlertDialog(
          backgroundColor: context.palette.surface,
          title: const Text('Cancelar reserva'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                '${booking.serviceName} · ${booking.customerName}',
                style: TextStyle(color: context.palette.muted),
              ),
              const SizedBox(height: 16),
              TextField(
                controller: controller,
                decoration: const InputDecoration(labelText: 'Motivo (opcional)'),
              ),
            ],
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(dialogContext),
              child: const Text('Volver'),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(dialogContext, controller.text),
              child: const Text('Cancelar reserva'),
            ),
          ],
        );
      },
    );
    if (reason == null || !context.mounted) return;
    await _queue(
      context,
      'booking.cancel',
      {'booking': booking.id, 'reason': reason},
      title: 'Cancelación en cola',
    );
  }

  Future<void> _rescheduleBooking(
    BuildContext context,
    BookingRecord booking,
  ) async {
    final newStart = await showModalBottomSheet<DateTime>(
      context: context,
      isScrollControlled: true,
      backgroundColor: context.palette.surface,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      builder: (_) => _RescheduleSheet(initial: booking.startAt!.toLocal()),
    );
    if (newStart == null || !context.mounted) return;
    await _queue(
      context,
      'booking.reschedule',
      {
        'booking': booking.id,
        'start_at': newStart.toUtc().toIso8601String(),
        'expected_start_at': booking.raw['start_at']?.toString(),
        'reason': 'Reprogramada desde móvil',
      },
      title: 'Reprogramación en cola',
    );
  }

  Future<void> _queue(
    BuildContext context,
    String type,
    Map<String, dynamic> payload, {
    required String title,
  }) async {
    final app = context.read<AppState>();
    await app.queueOperation(type, payload);
    if (!context.mounted) return;
    final problems = app.outboxItems.where((item) => !item.pending).toList();
    final message = problems.isNotEmpty
        ? problems.last.error ?? 'La operación quedó con conflicto.'
        : title;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        backgroundColor: problems.isNotEmpty
            ? Theme.of(context).colorScheme.error
            : context.palette.surfaceAlt,
      ),
    );
  }
}

class _Metric extends StatelessWidget {
  const _Metric({required this.value, required this.label});

  final String value;
  final String label;

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 14, horizontal: 12),
        decoration: BoxDecoration(
          color: context.palette.surface,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: context.palette.border),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              value,
              style: TextStyle(
                fontSize: 24,
                fontWeight: FontWeight.w900,
                color: Theme.of(context).colorScheme.primary,
              ),
            ),
            const SizedBox(height: 2),
            Text(
              label,
              style: TextStyle(
                color: context.palette.muted,
                fontSize: 9.5,
                letterSpacing: 1.2,
                fontWeight: FontWeight.w700,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _BookingCard extends StatelessWidget {
  const _BookingCard({required this.booking, required this.onTap});

  final BookingRecord booking;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final tone = switch (booking.status) {
      'confirmed' => 'success',
      'scheduled' => 'warning',
      'canceled' || 'no_show' => 'danger',
      _ => 'neutral',
    };
    return SurfaceCard(
      onTap: onTap,
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 54,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  formatTime(booking.startAt!),
                  style: TextStyle(
                    fontSize: 17,
                    fontWeight: FontWeight.w900,
                    color: context.palette.onSurface,
                  ),
                ),
                Text(
                  formatTime(booking.endAt ?? booking.startAt!),
                  style: TextStyle(
                    color: context.palette.muted,
                    fontSize: 11.5,
                  ),
                ),
              ],
            ),
          ),
          Container(
            width: 2,
            height: 48,
            margin: const EdgeInsets.symmetric(horizontal: 12),
            color: tone == 'danger'
                ? Theme.of(context).colorScheme.error
                : context.palette.border,
          ),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        booking.serviceName,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(
                          fontWeight: FontWeight.w800,
                          fontSize: 15,
                        ),
                      ),
                    ),
                    StatusPill(label: booking.statusDisplay, tone: tone),
                  ],
                ),
                const SizedBox(height: 5),
                Text(
                  booking.customerName,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(
                    color: context.palette.muted,
                    fontSize: 12.5,
                  ),
                ),
                const SizedBox(height: 3),
                Text(
                  '${booking.workerName} · ${booking.publicCode}',
                  style: TextStyle(
                    color: context.palette.muted,
                    fontSize: 11,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _BookingDetailSheet extends StatelessWidget {
  const _BookingDetailSheet({required this.booking});

  final BookingRecord booking;

  @override
  Widget build(BuildContext context) {
    final active = booking.isActive;
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.all(22),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    booking.serviceName,
                    style: const TextStyle(
                      fontSize: 22,
                      fontWeight: FontWeight.w900,
                    ),
                  ),
                ),
                StatusPill(label: booking.statusDisplay),
              ],
            ),
            const SizedBox(height: 16),
            _DetailRow(
              icon: Icons.schedule_rounded,
              text: '${friendlyDay(booking.startAt!)} · ${formatTime(booking.startAt!)} a ${formatTime(booking.endAt ?? booking.startAt!)}',
            ),
            _DetailRow(
              icon: Icons.person_outline_rounded,
              text: booking.customerName,
            ),
            _DetailRow(
              icon: Icons.badge_outlined,
              text: booking.workerName,
            ),
            _DetailRow(
              icon: Icons.confirmation_number_outlined,
              text: booking.publicCode,
            ),
            const SizedBox(height: 18),
            if (active)
              Row(
                children: [
                  Expanded(
                    child: OutlinedButton(
                      onPressed: () => Navigator.pop(context, 'reschedule'),
                      child: const Text('Reprogramar'),
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: FilledButton(
                      onPressed: () => Navigator.pop(context, 'cancel'),
                      child: const Text('Cancelar'),
                    ),
                  ),
                ],
              )
            else
              Text(
                'Esta reserva ya está cerrada; puedes consultar su detalle sin cambios.',
                style: TextStyle(color: context.palette.muted),
              ),
          ],
        ),
      ),
    );
  }
}

class _DetailRow extends StatelessWidget {
  const _DetailRow({required this.icon, required this.text});

  final IconData icon;
  final String text;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Row(
        children: [
          Icon(
            icon,
            size: 17,
            color: Theme.of(context).colorScheme.primary,
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Text(text, style: const TextStyle(fontSize: 13.5)),
          ),
        ],
      ),
    );
  }
}

class _CreateBookingSheet extends StatefulWidget {
  const _CreateBookingSheet();

  @override
  State<_CreateBookingSheet> createState() => _CreateBookingSheetState();
}

class _CreateBookingSheetState extends State<_CreateBookingSheet> {
  final _notes = TextEditingController();
  late DateTime _day;
  late TimeOfDay _time;
  String? _serviceId;
  String? _workerId;
  String? _customerId;
  String? _branchId;
  String? _error;

  @override
  void initState() {
    super.initState();
    final now = DateTime.now().add(const Duration(days: 1));
    _day = DateTime(now.year, now.month, now.day);
    _time = const TimeOfDay(hour: 10, minute: 0);
    final app = context.read<AppState>();
    _serviceId = app.services.isEmpty ? null : app.services.first.id;
    _workerId = app.workers.isEmpty ? null : app.workers.first.id;
    _customerId = app.customers.isEmpty ? null : app.customers.first.id;
    final branches = app.bootstrap?.branches ?? const [];
    _branchId = initialBranchId(branches, app.bootstrap?.defaultBranchId);
  }

  @override
  void dispose() {
    _notes.dispose();
    super.dispose();
  }

  Future<void> _pickDate() async {
    final selected = await showDatePicker(
      context: context,
      initialDate: _day,
      firstDate: DateTime.now(),
      lastDate: DateTime.now().add(const Duration(days: 120)),
    );
    if (selected != null) setState(() => _day = selected);
  }

  Future<void> _pickTime() async {
    final selected = await showTimePicker(
      context: context,
      initialTime: _time,
    );
    if (selected != null) setState(() => _time = selected);
  }

  void _submit() {
    if (_serviceId == null ||
        _workerId == null ||
        _customerId == null ||
        _branchId == null) {
      setState(() => _error = 'Completa servicio, profesional, cliente y sucursal.');
      return;
    }
    final start = DateTime(
      _day.year,
      _day.month,
      _day.day,
      _time.hour,
      _time.minute,
    );
    Navigator.pop(context, {
      'branch': _branchId,
      'service': _serviceId,
      'worker': _workerId,
      'customer': _customerId,
      'start_at': start.toUtc().toIso8601String(),
      'notes': _notes.text.trim(),
    });
  }

  @override
  Widget build(BuildContext context) {
    final app = context.watch<AppState>();
    return Padding(
      padding: EdgeInsets.fromLTRB(
        22,
        18,
        22,
        22 + MediaQuery.viewInsetsOf(context).bottom,
      ),
      child: SingleChildScrollView(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Nueva reserva',
              style: TextStyle(fontSize: 22, fontWeight: FontWeight.w900),
            ),
            const SizedBox(height: 18),
            _Dropdown(
              label: 'Servicio',
              value: _serviceId,
              items: {
                for (final service in app.services) service.id: service.name,
              },
              onChanged: (value) => setState(() => _serviceId = value),
            ),
            const SizedBox(height: 12),
            _Dropdown(
              label: 'Profesional',
              value: _workerId,
              items: {for (final worker in app.workers) worker.id: worker.name},
              onChanged: (value) => setState(() => _workerId = value),
            ),
            const SizedBox(height: 12),
            _Dropdown(
              label: 'Cliente',
              value: _customerId,
              items: {
                for (final customer in app.customers)
                  customer.id: customer.name,
              },
              onChanged: (value) => setState(() => _customerId = value),
            ),
            const SizedBox(height: 12),
            _Dropdown(
              label: 'Sucursal',
              value: _branchId,
              items: {
                for (final branch in app.bootstrap?.branches ?? const [])
                  '${branch['id']}': '${branch['name']}',
              },
              onChanged: (value) => setState(() => _branchId = value),
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: _pickDate,
                    icon: const Icon(Icons.calendar_today_rounded, size: 16),
                    label: Text(formatDate(_day)),
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: _pickTime,
                    icon: const Icon(Icons.schedule_rounded, size: 16),
                    label: Text(_time.format(context)),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _notes,
              maxLines: 2,
              decoration: const InputDecoration(
                labelText: 'Notas (opcional)',
              ),
            ),
            if (_error != null) ...[
              const SizedBox(height: 12),
              ErrorNote(_error!),
            ],
            const SizedBox(height: 18),
            FilledButton(
              onPressed: _submit,
              child: const Text('Guardar reserva'),
            ),
            const SizedBox(height: 8),
            Text(
              'Si no hay conexión, la reserva queda en la cola local y se envía al reconectar.',
              style: TextStyle(color: context.palette.muted, fontSize: 11.5),
            ),
          ],
        ),
      ),
    );
  }
}

class _RescheduleSheet extends StatefulWidget {
  const _RescheduleSheet({required this.initial});

  final DateTime initial;

  @override
  State<_RescheduleSheet> createState() => _RescheduleSheetState();
}

class _RescheduleSheetState extends State<_RescheduleSheet> {
  late DateTime _day;
  late TimeOfDay _time;

  @override
  void initState() {
    super.initState();
    _day = DateTime(
      widget.initial.year,
      widget.initial.month,
      widget.initial.day,
    );
    _time = TimeOfDay.fromDateTime(widget.initial);
  }

  Future<void> _pickDate() async {
    final selected = await showDatePicker(
      context: context,
      initialDate: _day,
      firstDate: DateTime.now(),
      lastDate: DateTime.now().add(const Duration(days: 120)),
    );
    if (selected != null) setState(() => _day = selected);
  }

  Future<void> _pickTime() async {
    final selected = await showTimePicker(
      context: context,
      initialTime: _time,
    );
    if (selected != null) setState(() => _time = selected);
  }

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.all(22),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Reprogramar',
              style: TextStyle(fontSize: 22, fontWeight: FontWeight.w900),
            ),
            const SizedBox(height: 8),
            Text(
              'Se enviará la fecha esperada para detectar cambios hechos por otra persona.',
              style: TextStyle(color: context.palette.muted, fontSize: 12),
            ),
            const SizedBox(height: 18),
            Row(
              children: [
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: _pickDate,
                    icon: const Icon(Icons.calendar_today_rounded, size: 16),
                    label: Text(formatDate(_day)),
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: _pickTime,
                    icon: const Icon(Icons.schedule_rounded, size: 16),
                    label: Text(_time.format(context)),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 18),
            FilledButton(
              onPressed: () => Navigator.pop(
                context,
                DateTime(
                  _day.year,
                  _day.month,
                  _day.day,
                  _time.hour,
                  _time.minute,
                ),
              ),
              child: const Text('Reprogramar'),
            ),
          ],
        ),
      ),
    );
  }
}

class _Dropdown extends StatelessWidget {
  const _Dropdown({
    required this.label,
    required this.value,
    required this.items,
    required this.onChanged,
  });

  final String label;
  final String? value;
  final Map<String, String> items;
  final ValueChanged<String?> onChanged;

  @override
  Widget build(BuildContext context) {
    return DropdownButtonFormField<String>(
      initialValue: items.containsKey(value) ? value : null,
      isExpanded: true,
      decoration: InputDecoration(labelText: label),
      dropdownColor: context.palette.surface,
      items: [
        for (final entry in items.entries)
          DropdownMenuItem(
            value: entry.key,
            child: Text(entry.value, overflow: TextOverflow.ellipsis),
          ),
      ],
      onChanged: onChanged,
    );
  }
}
