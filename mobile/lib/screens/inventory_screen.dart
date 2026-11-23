import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/formatters.dart';
import '../core/theme.dart';
import '../data/models.dart';
import '../state/app_state.dart';
import '../widgets/common.dart';

class InventoryScreen extends StatefulWidget {
  const InventoryScreen({super.key});

  @override
  State<InventoryScreen> createState() => _InventoryScreenState();
}

class _InventoryScreenState extends State<InventoryScreen> {
  bool _onlyLow = false;

  @override
  Widget build(BuildContext context) {
    final app = context.watch<AppState>();
    final products = app.products;
    final rows = app.stockRows;
    final totals = <String, double>{};
    for (final row in rows) {
      final product = row.product;
      if (product == null) continue;
      totals[product.id] = (totals[product.id] ?? 0) + row.quantity;
    }
    final lowCount = products
        .where((product) => _isLow(product, totals[product.id] ?? 0))
        .length;
    final visible = _onlyLow
        ? products
              .where((product) => _isLow(product, totals[product.id] ?? 0))
              .toList()
        : products;
    final canWrite = app.can('inventory.write');
    final enabled = app.moduleEnabled('inventory');

    return Scaffold(
      floatingActionButton: enabled && canWrite
          ? FloatingActionButton.extended(
              onPressed: () => _openMovement(context),
              icon: const Icon(Icons.swap_vert_rounded),
              label: const Text('Movimiento'),
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
                title: 'Inventario',
                subtitle:
                    '${app.warehouses.length} bodegas · ${products.length} productos',
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
                    _Metric(value: '${products.length}', label: 'PRODUCTOS'),
                    const SizedBox(width: 10),
                    _Metric(value: '$lowCount', label: 'BAJO MÍNIMO'),
                    const SizedBox(width: 10),
                    _Metric(
                      value: '${app.warehouses.length}',
                      label: 'BODEGAS',
                    ),
                  ],
                ),
              ),
              Padding(
                padding: const EdgeInsets.fromLTRB(20, 18, 20, 4),
                child: Wrap(
                  spacing: 8,
                  children: [
                    ChoiceChip(
                      label: const Text('Todo el stock'),
                      selected: !_onlyLow,
                      onSelected: (_) => setState(() => _onlyLow = false),
                      selectedColor: Theme.of(context).colorScheme.secondary,
                      backgroundColor: context.palette.surface,
                      side: BorderSide(color: context.palette.border),
                      labelStyle: TextStyle(
                        color: !_onlyLow
                            ? Theme.of(context).colorScheme.onSecondary
                            : context.palette.muted,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    ChoiceChip(
                      label: Text('Bajo mínimo ($lowCount)'),
                      selected: _onlyLow,
                      onSelected: (_) => setState(() => _onlyLow = true),
                      selectedColor: Theme.of(context).colorScheme.secondary,
                      backgroundColor: context.palette.surface,
                      side: BorderSide(color: context.palette.border),
                      labelStyle: TextStyle(
                        color: _onlyLow
                            ? Theme.of(context).colorScheme.onSecondary
                            : context.palette.muted,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ],
                ),
              ),
              if (!enabled)
                const EmptyState(
                  icon: Icons.lock_outline_rounded,
                  title: 'Inventario no incluido',
                  message:
                      'El plan actual no incluye inventario o tu rol no tiene acceso.',
                )
              else if (visible.isEmpty)
                EmptyState(
                  icon: Icons.inventory_2_outlined,
                  title: _onlyLow ? 'Sin alertas de stock' : 'Sin productos',
                  message: _onlyLow
                      ? 'Ningún producto está en su punto de reorden.'
                      : 'Desliza hacia abajo para sincronizar el catálogo de productos.',
                  action: canWrite
                      ? OutlinedButton(
                          onPressed: () => _openMovement(context),
                          child: const Text('Registrar movimiento'),
                        )
                      : null,
                )
              else ...[
                const SectionLabel('Catálogo'),
                for (final product in visible)
                  Padding(
                    padding: const EdgeInsets.fromLTRB(20, 0, 20, 10),
                    child: _ProductCard(
                      product: product,
                      quantity: totals[product.id] ?? 0,
                      rows: rows
                          .where((row) => row.product?.id == product.id)
                          .toList(),
                      low: _isLow(product, totals[product.id] ?? 0),
                      canWrite: canWrite,
                      onTap: () => _openDetail(context, product, rows),
                    ),
                  ),
              ],
              _PendingMovements(),
            ],
          ),
        ),
      ),
    );
  }

  static bool _isLow(ProductRecord product, double quantity) =>
      product.reorderPoint > 0 && quantity <= product.reorderPoint;

  Future<void> _openDetail(
    BuildContext context,
    ProductRecord product,
    List<StockRow> rows,
  ) async {
    final app = context.read<AppState>();
    final canWrite = app.can('inventory.write');
    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      backgroundColor: context.palette.surface,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      builder: (sheetContext) {
        final productRows = rows
            .where((row) => row.product?.id == product.id)
            .toList();
        return SafeArea(
          child: Padding(
            padding: const EdgeInsets.all(22),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  product.name,
                  style: const TextStyle(
                    fontSize: 22,
                    fontWeight: FontWeight.w900,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  '${product.sku.isEmpty ? 'Sin SKU' : product.sku} · ${formatMoney(product.price)}',
                  style: TextStyle(
                    color: context.palette.muted,
                    fontSize: 12.5,
                  ),
                ),
                const SizedBox(height: 16),
                if (productRows.isEmpty)
                  Text(
                    'Sin existencias registradas en las bodegas sincronizadas.',
                    style: TextStyle(color: context.palette.muted),
                  )
                else
                  for (final row in productRows)
                    Padding(
                      padding: const EdgeInsets.only(bottom: 10),
                      child: Row(
                        children: [
                          Expanded(
                            child: Text(
                              row.warehouseName.isEmpty
                                  ? 'Bodega'
                                  : row.warehouseName,
                              style: const TextStyle(fontSize: 13.5),
                            ),
                          ),
                          Text(
                            formatQuantity(row.quantity),
                            style: TextStyle(
                              fontWeight: FontWeight.w800,
                              color: row.lowStock
                                  ? Theme.of(context).colorScheme.error
                                  : context.palette.onSurface,
                            ),
                          ),
                        ],
                      ),
                    ),
                const SizedBox(height: 8),
                Text(
                  'Punto de reorden: ${formatQuantity(product.reorderPoint)}',
                  style: TextStyle(
                    color: context.palette.muted,
                    fontSize: 12,
                  ),
                ),
                if (canWrite) ...[
                  const SizedBox(height: 18),
                  FilledButton(
                    onPressed: () {
                      Navigator.pop(sheetContext);
                      _openMovement(context, product: product);
                    },
                    child: const Text('Registrar movimiento'),
                  ),
                ],
              ],
            ),
          ),
        );
      },
    );
  }

  Future<void> _openMovement(
    BuildContext context, {
    ProductRecord? product,
  }) async {
    final app = context.read<AppState>();
    if (app.products.isEmpty || app.warehouses.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(
            'Sincroniza productos y bodegas antes de registrar un movimiento.',
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
      builder: (_) => _MovementSheet(product: product),
    );
    if (payload == null || !context.mounted) return;
    await app.queueOperation('inventory.movement', payload);
    if (!context.mounted) return;
    final conflict = app.outboxItems
        .where((item) => !item.pending)
        .toList();
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(
          conflict.isNotEmpty
              ? conflict.last.error ?? 'El movimiento quedó con conflicto.'
              : 'Movimiento registrado',
        ),
        backgroundColor: conflict.isNotEmpty
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
                fontSize: 22,
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

class _ProductCard extends StatelessWidget {
  const _ProductCard({
    required this.product,
    required this.quantity,
    required this.rows,
    required this.low,
    required this.canWrite,
    required this.onTap,
  });

  final ProductRecord product;
  final double quantity;
  final List<StockRow> rows;
  final bool low;
  final bool canWrite;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return SurfaceCard(
      onTap: onTap,
      child: Row(
        children: [
          Container(
            width: 46,
            height: 46,
            decoration: BoxDecoration(
              color: low
                  ? Theme.of(context).colorScheme.error
                  : context.palette.border,
              borderRadius: BorderRadius.circular(13),
            ),
            alignment: Alignment.center,
            child: Icon(
              low ? Icons.warning_amber_rounded : Icons.inventory_2_outlined,
              color: low
                  ? Theme.of(context).colorScheme.onError
                  : context.palette.muted,
              size: 22,
            ),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  product.name,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    fontWeight: FontWeight.w800,
                    fontSize: 15,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  '${product.sku.isEmpty ? 'Sin SKU' : product.sku} · ${rows.length} bodegas',
                  style: TextStyle(
                    color: context.palette.muted,
                    fontSize: 11.5,
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(width: 10),
          Column(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Text(
                formatQuantity(quantity),
                style: TextStyle(
                  fontSize: 17,
                  fontWeight: FontWeight.w900,
                  color: low
                      ? Theme.of(context).colorScheme.error
                      : context.palette.onSurface,
                ),
              ),
              if (product.reorderPoint > 0)
                Text(
                  'mín. ${formatQuantity(product.reorderPoint)}',
                  style: TextStyle(
                    color: context.palette.muted,
                    fontSize: 10.5,
                  ),
                ),
            ],
          ),
        ],
      ),
    );
  }
}

class _MovementSheet extends StatefulWidget {
  const _MovementSheet({this.product});

  final ProductRecord? product;

  @override
  State<_MovementSheet> createState() => _MovementSheetState();
}

class _MovementSheetState extends State<_MovementSheet> {
  final _quantity = TextEditingController();
  final _unitCost = TextEditingController();
  final _note = TextEditingController();
  String _kind = 'entry';
  String? _productId;
  String? _warehouseId;
  String? _error;

  @override
  void initState() {
    super.initState();
    final app = context.read<AppState>();
    _productId = widget.product?.id ??
        (app.products.isNotEmpty ? app.products.first.id : null);
    _warehouseId = app.warehouses.isNotEmpty ? app.warehouses.first.id : null;
  }

  @override
  void dispose() {
    _quantity.dispose();
    _unitCost.dispose();
    _note.dispose();
    super.dispose();
  }

  void _submit() {
    final quantity = double.tryParse(_quantity.text.replaceAll(',', '.'));
    if (_productId == null || _warehouseId == null) {
      setState(() => _error = 'Selecciona producto y bodega.');
      return;
    }
    if (quantity == null || quantity <= 0) {
      setState(() => _error = 'Indica una cantidad mayor a cero.');
      return;
    }
    final payload = <String, dynamic>{
      'warehouse': _warehouseId,
      'product': _productId,
      'kind': _kind,
      'quantity': quantity.toStringAsFixed(3),
      'note': _note.text.trim(),
    };
    final cost = double.tryParse(_unitCost.text.replaceAll(',', '.'));
    if (_kind == 'entry' && cost != null) {
      payload['unit_cost'] = cost.toStringAsFixed(4);
    }
    Navigator.pop(context, payload);
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
              'Movimiento de stock',
              style: TextStyle(fontSize: 22, fontWeight: FontWeight.w900),
            ),
            const SizedBox(height: 16),
            SegmentedButton<String>(
              segments: const [
                ButtonSegment(
                  value: 'entry',
                  label: Text('Entrada'),
                  icon: Icon(Icons.south_west_rounded, size: 16),
                ),
                ButtonSegment(
                  value: 'exit',
                  label: Text('Salida'),
                  icon: Icon(Icons.north_east_rounded, size: 16),
                ),
              ],
              selected: {_kind},
              onSelectionChanged: (value) =>
                  setState(() => _kind = value.first),
              style: SegmentedButton.styleFrom(
                backgroundColor: context.palette.surface,
                foregroundColor: context.palette.muted,
                selectedBackgroundColor: Theme.of(
                  context,
                ).colorScheme.secondary,
                selectedForegroundColor: Theme.of(
                  context,
                ).colorScheme.onSecondary,
                side: BorderSide(color: context.palette.border),
              ),
            ),
            const SizedBox(height: 14),
            _Picker(
              label: 'Producto',
              value: _productId,
              items: {for (final product in app.products) product.id: product.name},
              onChanged: (value) => setState(() => _productId = value),
            ),
            const SizedBox(height: 12),
            _Picker(
              label: 'Bodega',
              value: _warehouseId,
              items: {
                for (final warehouse in app.warehouses)
                  warehouse.id: warehouse.name,
              },
              onChanged: (value) => setState(() => _warehouseId = value),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _quantity,
              keyboardType: const TextInputType.numberWithOptions(
                decimal: true,
              ),
              decoration: const InputDecoration(labelText: 'Cantidad'),
            ),
            if (_kind == 'entry') ...[
              const SizedBox(height: 12),
              TextField(
                controller: _unitCost,
                keyboardType: const TextInputType.numberWithOptions(
                  decimal: true,
                ),
                decoration: const InputDecoration(
                  labelText: 'Costo unitario (opcional)',
                ),
              ),
            ],
            const SizedBox(height: 12),
            TextField(
              controller: _note,
              maxLines: 2,
              decoration: const InputDecoration(
                labelText: 'Nota (opcional)',
                hintText: 'Recepción, merma, ajuste…',
              ),
            ),
            if (_error != null) ...[
              const SizedBox(height: 12),
              ErrorNote(_error!),
            ],
            const SizedBox(height: 18),
            FilledButton(
              onPressed: _submit,
              child: const Text('Guardar movimiento'),
            ),
            const SizedBox(height: 8),
            Text(
              'Si no hay conexión, el movimiento queda en la cola y se aplica al reconectar.',
              style: TextStyle(color: context.palette.muted, fontSize: 11.5),
            ),
          ],
        ),
      ),
    );
  }
}

class _PendingMovements extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    final pending = context
        .watch<AppState>()
        .outboxItems
        .where((item) => item.type == 'inventory.movement')
        .toList();
    if (pending.isEmpty) return const SizedBox.shrink();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const SectionLabel('Movimientos en cola'),
        for (final item in pending)
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 0, 20, 8),
            child: SurfaceCard(
              padding: const EdgeInsets.symmetric(
                horizontal: 14,
                vertical: 12,
              ),
              child: Row(
                children: [
                  Icon(
                    item.pending
                        ? Icons.schedule_send_rounded
                        : Icons.error_outline_rounded,
                    size: 18,
                    color: item.pending
                        ? context.palette.muted
                        : Theme.of(context).colorScheme.error,
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          '${item.payload['kind'] == 'exit' ? 'Salida' : 'Entrada'} · '
                          '${item.payload['quantity']} unidades',
                          style: const TextStyle(
                            fontSize: 12.5,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                        if (item.error != null)
                          Text(
                            item.error!,
                            maxLines: 2,
                            overflow: TextOverflow.ellipsis,
                            style: TextStyle(
                              color: context.palette.muted,
                              fontSize: 11,
                            ),
                          ),
                        if (item.error != null)
                          TextButton(
                            onPressed: () => context
                                .read<AppState>()
                                .discardOutbox(item.clientId),
                            child: const Text('Descartar'),
                          ),
                      ],
                    ),
                  ),
                  StatusPill(
                    label: item.pending ? 'Pendiente' : 'Conflicto',
                    tone: item.pending ? 'warning' : 'danger',
                  ),
                ],
              ),
            ),
          ),
      ],
    );
  }
}

class _Picker extends StatelessWidget {
  const _Picker({
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
