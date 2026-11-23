String twoDigits(int value) => value.toString().padLeft(2, '0');

String formatTime(DateTime value) {
  final local = value.toLocal();
  return '${twoDigits(local.hour)}:${twoDigits(local.minute)}';
}

String formatDate(DateTime value) {
  final local = value.toLocal();
  return '${twoDigits(local.day)}/${twoDigits(local.month)}/${local.year}';
}

String formatDateTime(DateTime value) => '${formatDate(value)} · ${formatTime(value)}';

String friendlyDay(DateTime value) {
  final local = value.toLocal();
  final now = DateTime.now();
  final day = DateTime(local.year, local.month, local.day);
  final today = DateTime(now.year, now.month, now.day);
  final difference = day.difference(today).inDays;
  if (difference == 0) return 'Hoy';
  if (difference == 1) return 'Mañana';
  if (difference == -1) return 'Ayer';
  const weekdays = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom'];
  return '${weekdays[local.weekday - 1]} ${twoDigits(local.day)}/${twoDigits(local.month)}';
}

String formatMoney(dynamic value) {
  final parsed = double.tryParse('$value');
  if (parsed == null) return '\$0';
  final rounded = parsed.round();
  final digits = rounded.abs().toString();
  final buffer = StringBuffer();
  for (var index = 0; index < digits.length; index++) {
    if (index > 0 && (digits.length - index) % 3 == 0) buffer.write('.');
    buffer.write(digits[index]);
  }
  return '${rounded < 0 ? '-' : ''}\$$buffer';
}

String formatQuantity(double value) {
  if (value == value.roundToDouble()) return value.toStringAsFixed(0);
  return value.toStringAsFixed(2);
}

String relativeTime(DateTime? value) {
  if (value == null) return '';
  final difference = DateTime.now().difference(value.toLocal());
  if (difference.inMinutes < 1) return 'Ahora';
  if (difference.inMinutes < 60) return 'Hace ${difference.inMinutes} min';
  if (difference.inHours < 24) return 'Hace ${difference.inHours} h';
  if (difference.inDays == 1) return 'Ayer';
  if (difference.inDays < 7) return 'Hace ${difference.inDays} días';
  return formatDate(value);
}
