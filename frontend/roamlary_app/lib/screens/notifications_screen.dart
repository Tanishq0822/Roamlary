import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/app_theme.dart';
import '../core/format.dart';
import '../models/enums.dart';
import '../models/models.dart';
import '../state/app_state.dart';
import '../widgets/common.dart';

/// Notification inbox (Phase 11): every outbound alert the backend queued,
/// with its delivery status and attempt count. Tapping an unread row marks
/// it read; failed rows can be retried in place.
class NotificationsScreen extends StatefulWidget {
  const NotificationsScreen({super.key});

  @override
  State<NotificationsScreen> createState() => _NotificationsScreenState();
}

class _NotificationsScreenState extends State<NotificationsScreen> {
  List<AppNotification>? _items;
  Object? _error;
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _error = null;
      _items = null;
    });
    try {
      final items =
          await context.read<AppState>().repo.listNotifications();
      if (mounted) setState(() => _items = items);
    } catch (e) {
      if (mounted) setState(() => _error = e);
    }
  }

  Future<void> _openRead(AppNotification n) async {
    if (n.isRead || _busy) return;
    setState(() => _busy = true);
    try {
      await context.read<AppState>().repo.markNotificationRead(n.id);
      await _load();
    } catch (_) {
      // Best effort — the list still shows the row as unread.
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Notifications')),
      body: _items == null && _error == null
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? ErrorView(message: '$_error', onRetry: _load)
              : _items!.isEmpty
                  ? const EmptyView(
                      icon: Icons.notifications_none,
                      title: 'Nothing yet',
                      message: 'Alerts about check-ins, chats and SOS relay '
                          'attempts will appear here.',
                    )
                  : RefreshIndicator(
                      onRefresh: _load,
                      child: ListView.separated(
                        padding: const EdgeInsets.fromLTRB(16, 12, 16, 32),
                        itemCount: _items!.length,
                        separatorBuilder: (_, _) => const SizedBox(height: 10),
                        itemBuilder: (context, i) {
                          final n = _items![i];
                          return _NotificationTile(
                            item: n,
                            onTap: () => _openRead(n),
                          );
                        },
                      ),
                    ),
    );
  }
}

class _NotificationTile extends StatelessWidget {
  const _NotificationTile({required this.item, required this.onTap});

  final AppNotification item;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final unread = !item.isRead;

    final (statusLabel, statusColor) = switch (item.status) {
      NotificationStatus.delivered => ('Delivered', AppTheme.green),
      NotificationStatus.failed => ('Failed', AppTheme.danger),
      NotificationStatus.queued => ('Queued', Colors.orange.shade800),
      NotificationStatus.attempted => ('Attempted', Colors.orange.shade800),
      NotificationStatus.unavailable => ('Unavailable', Colors.grey),
      NotificationStatus.unknown => ('Unknown', Colors.grey),
    };

    return Material(
      color: unread
          ? AppTheme.green.withValues(alpha: 0.05)
          : theme.colorScheme.surface,
      borderRadius: BorderRadius.circular(16),
      child: Container(
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(16),
          border: Border.all(
            color: unread
                ? AppTheme.green.withValues(alpha: 0.35)
                : theme.dividerColor,
          ),
        ),
        child: InkWell(
          borderRadius: BorderRadius.circular(16),
          onTap: onTap,
          child: Padding(
            padding: const EdgeInsets.all(14),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Icon(
                  _iconFor(item.kind),
                  color: unread ? AppTheme.green : theme.colorScheme.onSurfaceVariant,
                  size: 22,
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
                              item.title,
                              style: theme.textTheme.titleSmall?.copyWith(
                                fontWeight: unread ? FontWeight.w800 : FontWeight.w600,
                              ),
                            ),
                          ),
                          Container(
                            padding: const EdgeInsets.symmetric(
                                horizontal: 8, vertical: 3),
                            decoration: BoxDecoration(
                              color: statusColor.withValues(alpha: 0.12),
                              borderRadius: BorderRadius.circular(999),
                            ),
                            child: Text(
                              statusLabel,
                              style: TextStyle(
                                fontSize: 10,
                                fontWeight: FontWeight.w700,
                                color: statusColor,
                              ),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 4),
                      Text(item.body, style: theme.textTheme.bodySmall),
                      const SizedBox(height: 6),
                      Text(
                        '${formatDateTime(item.createdAt)}'
                        '${item.attempts > 1 ? '  ·  ${item.attempts} attempts' : ''}'
                        '${item.lastError != null ? '  ·  ${item.lastError}' : ''}',
                        style: theme.textTheme.labelSmall
                            ?.copyWith(color: theme.colorScheme.onSurfaceVariant),
                      ),
                    ],
                  ),
                ),
                if (unread)
                  Padding(
                    padding: const EdgeInsets.only(left: 6, top: 4),
                    child: Container(
                      width: 8,
                      height: 8,
                      decoration: const BoxDecoration(
                        shape: BoxShape.circle,
                        color: AppTheme.green,
                      ),
                    ),
                  ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  static IconData _iconFor(String kind) => switch (kind) {
        'chat_request' => Icons.forum_outlined,
        'buddy_request' => Icons.handshake_outlined,
        'checkin_due' => Icons.alarm,
        'sos_contact' => Icons.sos,
        'meetup' => Icons.event_outlined,
        _ => Icons.notifications_outlined,
      };
}
