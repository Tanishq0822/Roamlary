/// Lightweight date/time formatting helpers. Deliberately dependency-free to
/// keep the app buildable with minimal packages.
String formatDateTime(DateTime value) {
  final local = value.toLocal();
  final month = _months[local.month - 1];
  final day = local.day.toString().padLeft(2, '0');
  final hour24 = local.hour.toString().padLeft(2, '0');
  final minute = local.minute.toString().padLeft(2, '0');
  return '$day $month ${local.year}  $hour24:$minute';
}

String formatTime(DateTime value) {
  final local = value.toLocal();
  final hour24 = local.hour.toString().padLeft(2, '0');
  final minute = local.minute.toString().padLeft(2, '0');
  return '$hour24:$minute';
}

/// Human-friendly relative label ("in 2h", "3d ago").
String relativeLabel(DateTime value) {
  final now = DateTime.now();
  final diff = value.difference(now);
  final abs = diff.abs();
  final suffix = diff.isNegative ? 'ago' : 'from now';

  if (abs.inMinutes < 1) return 'just now';
  if (abs.inHours < 1) return '${abs.inMinutes}m $suffix';
  if (abs.inDays < 1) return '${abs.inHours}h $suffix';
  return '${abs.inDays}d $suffix';
}

const List<String> _months = [
  'Jan',
  'Feb',
  'Mar',
  'Apr',
  'May',
  'Jun',
  'Jul',
  'Aug',
  'Sep',
  'Oct',
  'Nov',
  'Dec',
];
