import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';

import '../core/app_theme.dart';
import '../core/format.dart';
import '../models/models.dart';
import '../state/app_state.dart';
import '../widgets/common.dart';

/// Trip sharing (Phase 11): mint a read-only link to my itinerary that
/// expires on my terms, and see what other travellers have shared with me.
class TripSharesScreen extends StatefulWidget {
  const TripSharesScreen({super.key});

  @override
  State<TripSharesScreen> createState() => _TripSharesScreenState();
}

class _TripSharesScreenState extends State<TripSharesScreen> {
  List<TripShare>? _mine;
  List<SharedItinerary>? _shared;
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
      _mine = null;
      _shared = null;
    });
    try {
      final repo = context.read<AppState>().repo;
      final results = await Future.wait<Object?>([
        repo.listTripShares(),
        repo.listSharedWithMe(),
      ]);
      if (!mounted) return;
      setState(() {
        _mine = results[0] as List<TripShare>;
        _shared = results[1] as List<SharedItinerary>;
      });
    } catch (e) {
      if (mounted) setState(() => _error = e);
    }
  }

  Future<void> _create() async {
    if (_busy) return;
    final expiresAt = await _pickExpiry();
    if (expiresAt == null || !mounted) return;
    setState(() => _busy = true);
    try {
      final share = await context
          .read<AppState>()
          .repo
          .createTripShare(expiresAt: expiresAt);
      await _load();
      if (mounted) _showShareSheet(share.shareUrl);
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text('$e')));
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<DateTime?> _pickExpiry() async {
    final days = await showModalBottomSheet<int>(
      context: context,
      showDragHandle: true,
      builder: (sheetContext) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 0, 20, 8),
              child: Text(
                'Link expires after…',
                style: Theme.of(sheetContext).textTheme.titleMedium,
              ),
            ),
            for (final d in const [1, 3, 7, 14, 30])
              ListTile(
                leading: const Icon(Icons.timer_outlined),
                title: Text(d == 1 ? '24 hours' : '$d days'),
                onTap: () => Navigator.of(sheetContext).pop(d),
              ),
            const SizedBox(height: 8),
          ],
        ),
      ),
    );
    if (days == null) return null;
    return DateTime.now().add(Duration(days: days));
  }

  Future<void> _revoke(TripShare share) async {
    if (_busy) return;
    final go = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Revoke link?'),
        content: const Text(
            'Anyone holding this link will immediately lose access.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(false),
            child: const Text('Keep'),
          ),
          FilledButton(
            onPressed: () => Navigator.of(dialogContext).pop(true),
            child: const Text('Revoke'),
          ),
        ],
      ),
    );
    if (go != true || !mounted) return;
    setState(() => _busy = true);
    try {
      await context.read<AppState>().repo.revokeTripShare(share.id);
      await _load();
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text('$e')));
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  void _showShareSheet(String url) {
    showModalBottomSheet<void>(
      context: context,
      showDragHandle: true,
      builder: (sheetContext) => Padding(
        padding: const EdgeInsets.fromLTRB(20, 0, 20, 32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text('Share your itinerary',
                style: Theme.of(sheetContext).textTheme.titleLarge),
            const SizedBox(height: 6),
            Text(
              'Whoever has this link can read your plan until it expires. '
              'No messages, no location — just the itinerary.',
              style: Theme.of(sheetContext).textTheme.bodySmall?.copyWith(
                    color: Theme.of(sheetContext).colorScheme.onSurfaceVariant,
                  ),
            ),
            const SizedBox(height: 14),
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: Theme.of(sheetContext).colorScheme.surfaceContainerHighest,
                borderRadius: BorderRadius.circular(12),
              ),
              child: Text(url, style: const TextStyle(fontFamily: 'monospace')),
            ),
            const SizedBox(height: 14),
            Row(
              children: [
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: () async {
                      await Clipboard.setData(ClipboardData(text: url));
                      if (sheetContext.mounted) {
                        ScaffoldMessenger.of(sheetContext).showSnackBar(
                          const SnackBar(content: Text('Link copied')),
                        );
                      }
                    },
                    icon: const Icon(Icons.copy, size: 18),
                    label: const Text('Copy'),
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: FilledButton(
                    onPressed: () => Navigator.of(sheetContext).pop(),
                    child: const Text('Done'),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(title: const Text('Trip sharing')),
      floatingActionButton: FloatingActionButton.extended(
        heroTag: 'fab-trip-shares',
        onPressed: _busy ? null : _create,
        icon: const Icon(Icons.link),
        label: const Text('New link'),
      ),
      body: _mine == null && _error == null
          ? const LoadingView()
          : _error != null
              ? ErrorView(message: '$_error', onRetry: _load)
              : RefreshIndicator(
                  onRefresh: _load,
                  child: ListView(
                    padding: const EdgeInsets.fromLTRB(16, 12, 16, 88),
                    children: [
                      Text(
                        'MY LINKS',
                        style: theme.textTheme.labelSmall?.copyWith(
                          color: theme.colorScheme.onSurfaceVariant,
                          fontWeight: FontWeight.w700,
                          letterSpacing: 1.1,
                        ),
                      ),
                      const SizedBox(height: 8),
                      if (_mine!.isEmpty)
                        _Placeholder(
                          icon: Icons.link_off,
                          text: 'No active links. Create one so a friend can '
                              'follow your plan.',
                        )
                      else
                        for (final share in _mine!)
                          Padding(
                            padding: const EdgeInsets.only(bottom: 10),
                            child: _MyShareCard(
                              share: share,
                              busy: _busy,
                              onCopy: () async {
                                await Clipboard.setData(
                                    ClipboardData(text: share.shareUrl));
                                if (context.mounted) {
                                  ScaffoldMessenger.of(context).showSnackBar(
                                    const SnackBar(
                                        content: Text('Link copied')),
                                  );
                                }
                              },
                              onRevoke: share.isActive
                                  ? () => _revoke(share)
                                  : null,
                            ),
                          ),
                      const SizedBox(height: 20),
                      Text(
                        'SHARED WITH ME',
                        style: theme.textTheme.labelSmall?.copyWith(
                          color: theme.colorScheme.onSurfaceVariant,
                          fontWeight: FontWeight.w700,
                          letterSpacing: 1.1,
                        ),
                      ),
                      const SizedBox(height: 8),
                      if (_shared!.isEmpty)
                        const _Placeholder(
                          icon: Icons.group_off_outlined,
                          text: 'Nobody has shared an itinerary with you yet.',
                        )
                      else
                        for (final shared in _shared!)
                          Card(
                            margin: const EdgeInsets.only(bottom: 10),
                            child: ListTile(
                              leading: CircleAvatar(
                                backgroundColor:
                                    AppTheme.purple.withValues(alpha: 0.15),
                                child: Text(
                                  shared.ownerDisplayName.characters.first
                                      .toUpperCase(),
                                  style: const TextStyle(
                                      color: AppTheme.purple,
                                      fontWeight: FontWeight.w700),
                                ),
                              ),
                              title: Text(
                                shared.planDestination ??
                                    'Shared itinerary',
                                style: const TextStyle(
                                    fontWeight: FontWeight.w700),
                              ),
                              subtitle: Text(
                                'From ${shared.ownerDisplayName} · '
                                '${shared.isActive ? 'expires ${relativeLabel(shared.expiresAt)}' : 'expired'}',
                              ),
                              trailing: shared.isActive
                                  ? const Icon(Icons.open_in_new, size: 18)
                                  : const Icon(Icons.lock_outline, size: 18),
                            ),
                          ),
                    ],
                  ),
                ),
    );
  }
}

class _MyShareCard extends StatelessWidget {
  const _MyShareCard({
    required this.share,
    required this.busy,
    required this.onCopy,
    this.onRevoke,
  });

  final TripShare share;
  final bool busy;
  final VoidCallback onCopy;
  final VoidCallback? onRevoke;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: share.isActive
              ? AppTheme.green.withValues(alpha: 0.35)
              : theme.dividerColor,
        ),
        color: share.isActive
            ? AppTheme.green.withValues(alpha: 0.04)
            : theme.colorScheme.surface,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(
                share.isActive ? Icons.link : Icons.link_off,
                size: 18,
                color: share.isActive
                    ? AppTheme.green
                    : theme.colorScheme.onSurfaceVariant,
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  share.planDestination ?? 'Full itinerary',
                  style: const TextStyle(fontWeight: FontWeight.w700),
                ),
              ),
              StatusPill(
                label: share.isActive ? 'Active' : 'Revoked',
                color: share.isActive ? AppTheme.green : Colors.grey,
              ),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            share.shareUrl,
            style: theme.textTheme.bodySmall
                ?.copyWith(fontFamily: 'monospace', color: Colors.grey.shade700),
            overflow: TextOverflow.ellipsis,
          ),
          const SizedBox(height: 6),
          Text(
            share.isActive
                ? 'Expires ${relativeLabel(share.expiresAt)}'
                : 'Link no longer works',
            style: theme.textTheme.labelSmall
                ?.copyWith(color: theme.colorScheme.onSurfaceVariant),
          ),
          const SizedBox(height: 10),
          Row(
            children: [
              OutlinedButton.icon(
                onPressed: onCopy,
                icon: const Icon(Icons.copy, size: 16),
                label: const Text('Copy'),
              ),
              if (onRevoke != null) ...[
                const SizedBox(width: 8),
                OutlinedButton.icon(
                  style: OutlinedButton.styleFrom(
                    foregroundColor: AppTheme.danger,
                  ),
                  onPressed: busy ? null : onRevoke,
                  icon: const Icon(Icons.block, size: 16),
                  label: const Text('Revoke'),
                ),
              ],
            ],
          ),
        ],
      ),
    );
  }
}

class _Placeholder extends StatelessWidget {
  const _Placeholder({required this.icon, required this.text});

  final IconData icon;
  final String text;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: theme.dividerColor, style: BorderStyle.solid),
      ),
      child: Row(
        children: [
          Icon(icon, color: theme.colorScheme.outline),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              text,
              style: theme.textTheme.bodySmall
                  ?.copyWith(color: theme.colorScheme.onSurfaceVariant),
            ),
          ),
        ],
      ),
    );
  }
}
