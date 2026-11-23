String? initialBranchId(
  List<Map<String, dynamic>> branches,
  String? preferred,
) {
  final active = branches
      .where((branch) => branch['active'] != false)
      .toList(growable: false);
  if (preferred != null && preferred.isNotEmpty) {
    for (final branch in active) {
      if ('${branch['id']}' == preferred) return preferred;
    }
  }
  return active.isEmpty ? null : '${active.first['id']}';
}
