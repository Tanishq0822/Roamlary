import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/app_theme.dart';
import '../core/format.dart';
import '../models/enums.dart';
import '../models/models.dart';
import '../state/app_state.dart';
import '../widgets/common.dart';

/// SOS: activate a (recorded) incident, then cancel or resolve it.
///
/// This prototype only records an incident — it does not call emergency
/// services or notify anyone. That boundary is stated in the UI so the demo
/// never over-promises.
class SosScreen extends StatefulWidget {
  const SosScreen({super.key});

  @override
  State<SosScreen> createState() => _SosScreenState();
}

class _SosScreenState extends State<SosScreen> {
  final _descriptionCtrl = TextEditingController();
  List<SosEvent>? _events;
  Object? _error;
  bool _submitting = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _descriptionCtrl.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() {
      _error = null;
      _events = null;
    });
    try {
      final events = await context.read<AppState>().repo.listSosEvents();
      if (!mounted) return;
      setState(() => _events = events);
    } catch (e) {
      if (!mounted) return;
      setState(() => _error = e);
    }
  }

  Future<void> _activate() async {
    if (_submitting) return;
    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Activate SOS?'),
        content: const Text(
          'This records an incident in your history. This prototype does NOT '
          'contact emergency services or notify anyone.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            style: FilledButton.styleFrom(backgroundColor: AppTheme.danger),
            onPressed: () => Navigator.of(ctx).pop(true),
            child: const Text('Activate'),
          ),
        ],
      ),
    );
    if (confirm != true || !mounted) return;

    setState(() => _submitting = true);
    try {
      // Location capture is not wired in this prototype; send description only.
      await context.read<AppState>().repo.createSos(
            description: _descriptionCtrl.text.trim().isEmpty
                ? null
                : _descriptionCtrl.text.trim(),
          );
      _descriptionCtrl.clear();
      await _load();
    } catch (e) {
      if (!mounted) return;
      _showError(e);
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  Future<void> _close(SosEvent event, {required bool resolve}) async {
    final repo = context.read<AppState>().repo;
    try {
      if (resolve) {
        await repo.resolveSos(event.id);
      } else {
        await repo.cancelSos(event.id);
      }
      await _load();
    } catch (e) {
      if (!mounted) return;
      _showError(e);
    }
  }

  void _showError(Object e) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text('$e')),
    );
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(title: const Text('Emergency SOS')),
      body: _error != null
          ? ErrorView(message: '$_error', onRetry: _load)
          : _events == null
              ? const LoadingView(label: 'Loading SOS history…')
              : RefreshIndicator(
                  onRefresh: _load,
                  child: ListView(
                    padding: const EdgeInsets.all(16),
                    children: [
                      Container(
                        padding: const EdgeInsets.all(16),
                        decoration: BoxDecoration(
                          color: theme.colorScheme.errorContainer,
                          borderRadius: BorderRadius.circular(16),
                        ),
                        child: Row(
                          children: [
                            Icon(
                              Icons.info_outline,
                              color: theme.colorScheme.onErrorContainer,
                            ),
                            const SizedBox(width: 12),
                            Expanded(
                              child: Text(
                                'Recording only — no emergency services or '
                                'contacts are contacted in this prototype.',
                                style: theme.textTheme.bodySmall?.copyWith(
                                  color: theme.colorScheme.onErrorContainer,
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(height: 16),
                      TextField(
                        controller: _descriptionCtrl,
                        maxLines: 3,
                        maxLength: 500,
                        decoration: const InputDecoration(
                          labelText: 'What is happening? (optional)',
                          hintText: 'e.g. Being followed near the station',
                          alignLabelWithHint: true,
                        ),
                      ),
                      const SizedBox(height: 8),
                      FilledButton.icon(
                        style: FilledButton.styleFrom(
                          backgroundColor: AppTheme.danger,
                          foregroundColor: Colors.white,
                          minimumSize: const Size.fromHeight(56),
                        ),
                        onPressed: _submitting ? null : _activate,
                        icon: _submitting
                            ? const SizedBox(
                                height: 20,
                                width: 20,
                                child: CircularProgressIndicator(
                                  strokeWidth: 2,
                                  color: Colors.white,
                                ),
                              )
                            : const Icon(Icons.crisis_alert),
                        label: const Text('Activate SOS'),
                      ),
                      const SizedBox(height: 24),
                      Text(
                        'History',
                        style: theme.textTheme.titleMedium?.copyWith(
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                      const SizedBox(height: 8),
                      if (_events!.isEmpty)
                        const EmptyView(
                          icon: Icons.shield_outlined,
                          title: 'No incidents yet',
                          message: 'Recorded SOS incidents will appear here.',
                        )
                      else
                        ..._events!.map((e) => _SosCard(
                              event: e,
                              onCancel: e.isActive
                                  ? () => _close(e, resolve: false)
                                  : null,
                              onResolve: e.isActive
                                  ? () => _close(e, resolve: true)
                                  : null,
                            )),
                    ],
                  ),
                ),
    );
  }
}

class _SosCard extends StatelessWidget {
  const _SosCard({
    required this.event,
    required this.onCancel,
    required this.onResolve,
  });

  final SosEvent event;
  final VoidCallback? onCancel;
  final VoidCallback? onResolve;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final (label, color) = switch (event.status) {
      SosStatus.active => ('ACTIVE', AppTheme.danger),
      SosStatus.resolved => ('Resolved', theme.colorScheme.primary),
      SosStatus.cancelled => ('Cancelled', theme.colorScheme.outline),
      _ => (event.status.name, theme.colorScheme.outline),
    };

    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                StatusPill(label: label, color: color),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    formatDateTime(event.createdAt),
                    style: theme.textTheme.bodySmall,
                  ),
                ),
              ],
            ),
            if (event.description != null) ...[
              const SizedBox(height: 10),
              Text(event.description!, style: theme.textTheme.bodyMedium),
            ],
            if (event.latitude != null && event.longitude != null) ...[
              const SizedBox(height: 8),
              Row(
                children: [
                  const Icon(Icons.location_on_outlined, size: 16),
                  const SizedBox(width: 4),
                  Text(
                    '${event.latitude!.toStringAsFixed(4)}, '
                    '${event.longitude!.toStringAsFixed(4)}',
                    style: theme.textTheme.bodySmall,
                  ),
                ],
              ),
            ],
            if (onCancel != null || onResolve != null) ...[
              const SizedBox(height: 12),
              Row(
                children: [
                  if (onResolve != null)
                    Expanded(
                      child: OutlinedButton.icon(
                        onPressed: onResolve,
                        icon: const Icon(Icons.check),
                        label: const Text('Resolve'),
                      ),
                    ),
                  if (onResolve != null && onCancel != null)
                    const SizedBox(width: 12),
                  if (onCancel != null)
                    Expanded(
                      child: OutlinedButton.icon(
                        onPressed: onCancel,
                        icon: const Icon(Icons.close),
                        label: const Text('Cancel'),
                      ),
                    ),
                ],
              ),
            ],
          ],
        ),
      ),
    );
  }
}
