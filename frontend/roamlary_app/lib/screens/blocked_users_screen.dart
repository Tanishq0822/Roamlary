import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/app_theme.dart';
import '../core/format.dart';
import '../models/models.dart';
import '../state/app_state.dart';
import '../widgets/common.dart';

/// Blocked users (safety switch).
///
/// Blocking is server-enforced: a blocked account cannot start new chats or
/// appear in discovery for the blocker. This screen lists current blocks and
/// lets the user undo one.
class BlockedUsersScreen extends StatefulWidget {
  const BlockedUsersScreen({super.key});

  @override
  State<BlockedUsersScreen> createState() => _BlockedUsersScreenState();
}

class _BlockedUsersScreenState extends State<BlockedUsersScreen> {
  List<BlockedUser>? _items;
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
      final items = await context.read<AppState>().repo.listBlocks();
      if (mounted) setState(() => _items = items);
    } catch (e) {
      if (mounted) setState(() => _error = e);
    }
  }

  Future<void> _unblock(BlockedUser user) async {
    if (_busy) return;
    setState(() => _busy = true);
    try {
      await context.read<AppState>().repo.unblockUser(user.blockedId);
      await _load();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('${user.blockedDisplayName} unblocked')),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text('$e')));
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(title: const Text('Blocked users')),
      body: _items == null && _error == null
          ? const LoadingView()
          : _error != null
              ? ErrorView(message: '$_error', onRetry: _load)
              : _items!.isEmpty
                  ? const EmptyView(
                      icon: Icons.block,
                      title: 'No one is blocked',
                      message: 'People you block cannot contact you or appear '
                          'in your traveller suggestions. You can block '
                          'anyone from the ⋯ menu on their card.',
                    )
                  : RefreshIndicator(
                      onRefresh: _load,
                      child: ListView.separated(
                        padding: const EdgeInsets.fromLTRB(16, 12, 16, 32),
                        itemCount: _items!.length,
                        separatorBuilder: (_, _) => const SizedBox(height: 10),
                        itemBuilder: (context, i) {
                          final user = _items![i];
                          return Card(
                            margin: EdgeInsets.zero,
                            child: ListTile(
                              leading: CircleAvatar(
                                backgroundColor:
                                    AppTheme.danger.withValues(alpha: 0.12),
                                child: Text(
                                  user.blockedDisplayName.isEmpty
                                      ? '?'
                                      : user.blockedDisplayName[0]
                                          .toUpperCase(),
                                  style: const TextStyle(
                                      color: AppTheme.danger,
                                      fontWeight: FontWeight.w800),
                                ),
                              ),
                              title: Text(
                                user.blockedDisplayName,
                                style: const TextStyle(
                                    fontWeight: FontWeight.w700),
                              ),
                              subtitle: Text(
                                'Blocked ${formatDateTime(user.createdAt)}',
                                style: theme.textTheme.bodySmall?.copyWith(
                                  color: theme.colorScheme.onSurfaceVariant,
                                ),
                              ),
                              trailing: OutlinedButton(
                                onPressed:
                                    _busy ? null : () => _unblock(user),
                                child: const Text('Unblock'),
                              ),
                            ),
                          );
                        },
                      ),
                    ),
    );
  }
}
