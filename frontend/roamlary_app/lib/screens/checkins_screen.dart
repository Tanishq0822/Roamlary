import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/app_theme.dart';
import '../core/format.dart';
import '../models/enums.dart';
import '../models/models.dart';
import '../state/app_state.dart';
import '../widgets/common.dart';

/// Check-ins: create a "promise" check-in with an optional deadline, then
/// answer it as SAFE or NEEDS_HELP, or cancel it. Mirrors the backend's
/// pending-only transition rules in the UI.
class CheckInsScreen extends StatefulWidget {
  const CheckInsScreen({super.key});

  @override
  State<CheckInsScreen> createState() => _CheckInsScreenState();
}

class _CheckInsScreenState extends State<CheckInsScreen> {
  List<CheckIn>? _items;
  Object? _error;

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
      final items = await context.read<AppState>().repo.listCheckIns();
      if (!mounted) return;
      setState(() => _items = items);
    } catch (e) {
      if (!mounted) return;
      setState(() => _error = e);
    }
  }

  Future<void> _openCreate() async {
    final created = await showDialog<bool>(
      context: context,
      builder: (_) => const _CreateCheckInDialog(),
    );
    if (created == true && mounted) {
      await _load();
    }
  }

  Future<void> _answer(CheckIn c, CheckInStatus target) async {
    final repo = context.read<AppState>().repo;
    try {
      if (target == CheckInStatus.safe) {
        await repo.completeCheckIn(c.id);
      } else {
        await repo.updateCheckInStatus(c.id, target);
      }
      await _load();
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('$e')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(title: const Text('Safety check-ins')),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _openCreate,
        icon: const Icon(Icons.add),
        label: const Text('New check-in'),
      ),
      body: _error != null
          ? ErrorView(message: '$_error', onRetry: _load)
          : _items == null
              ? const LoadingView(label: 'Loading check-ins…')
              : RefreshIndicator(
                  onRefresh: _load,
                  child: _items!.isEmpty
                      ? ListView(
                          padding: const EdgeInsets.all(16),
                          children: const [
                            SizedBox(height: 80),
                            EmptyView(
                              icon: Icons.task_alt,
                              title: 'No check-ins yet',
                              message:
                                  'Create one before you head out so there is a '
                                  'record of when you expected to be back.',
                            ),
                          ],
                        )
                      : ListView.builder(
                          padding: const EdgeInsets.fromLTRB(16, 16, 16, 88),
                          itemCount: _items!.length,
                          itemBuilder: (context, i) =>
                              _CheckInCard(checkIn: _items![i], onAnswer: _answer),
                        ),
                ),
    );
  }
}

class _CheckInCard extends StatelessWidget {
  const _CheckInCard({required this.checkIn, required this.onAnswer});

  final CheckIn checkIn;
  final void Function(CheckIn, CheckInStatus) onAnswer;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final status = checkIn.status;

    final (label, color) = switch (status) {
      CheckInStatus.pending => ('Pending', theme.colorScheme.tertiary),
      CheckInStatus.safe => ('Safe', theme.colorScheme.primary),
      CheckInStatus.needsHelp => ('Needs help', AppTheme.danger),
      CheckInStatus.expired => ('Expired', theme.colorScheme.outline),
      CheckInStatus.cancelled => ('Cancelled', theme.colorScheme.outline),
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
                    'Created ${formatDateTime(checkIn.createdAt)}',
                    style: theme.textTheme.bodySmall,
                  ),
                ),
              ],
            ),
            if (checkIn.note != null) ...[
              const SizedBox(height: 10),
              Text(checkIn.note!, style: theme.textTheme.bodyMedium),
            ],
            if (checkIn.dueAt != null) ...[
              const SizedBox(height: 8),
              Row(
                children: [
                  const Icon(Icons.schedule, size: 16),
                  const SizedBox(width: 4),
                  Text(
                    'Due ${formatDateTime(checkIn.dueAt!)} '
                    '(${relativeLabel(checkIn.dueAt!)})',
                    style: theme.textTheme.bodySmall,
                  ),
                ],
              ),
            ],
            if (checkIn.completedAt != null) ...[
              const SizedBox(height: 8),
              Text(
                'Answered ${formatDateTime(checkIn.completedAt!)}',
                style: theme.textTheme.bodySmall,
              ),
            ],
            if (status == CheckInStatus.pending) ...[
              const SizedBox(height: 12),
              Row(
                children: [
                  Expanded(
                    child: FilledButton.icon(
                      style: FilledButton.styleFrom(
                        backgroundColor: theme.colorScheme.primary,
                        minimumSize: const Size.fromHeight(44),
                      ),
                      onPressed: () =>
                          onAnswer(checkIn, CheckInStatus.safe),
                      icon: const Icon(Icons.check),
                      label: const Text("I'm safe"),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: FilledButton.icon(
                      style: FilledButton.styleFrom(
                        backgroundColor: AppTheme.danger,
                        foregroundColor: Colors.white,
                        minimumSize: const Size.fromHeight(44),
                      ),
                      onPressed: () =>
                          onAnswer(checkIn, CheckInStatus.needsHelp),
                      icon: const Icon(Icons.warning_amber),
                      label: const Text('Need help'),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              Align(
                alignment: Alignment.centerRight,
                child: TextButton(
                  onPressed: () =>
                      onAnswer(checkIn, CheckInStatus.cancelled),
                  child: const Text('Cancel check-in'),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _CreateCheckInDialog extends StatefulWidget {
  const _CreateCheckInDialog();

  @override
  State<_CreateCheckInDialog> createState() => _CreateCheckInDialogState();
}

class _CreateCheckInDialogState extends State<_CreateCheckInDialog> {
  final _noteCtrl = TextEditingController();
  DateTime? _dueAt;
  bool _saving = false;

  @override
  void dispose() {
    _noteCtrl.dispose();
    super.dispose();
  }

  Future<void> _pickDue() async {
    final now = DateTime.now();
    final date = await showDatePicker(
      context: context,
      firstDate: now,
      lastDate: now.add(const Duration(days: 365)),
      initialDate: now.add(const Duration(hours: 2)),
    );
    if (date == null || !mounted) return;
    final time = await showTimePicker(
      context: context,
      initialTime: TimeOfDay.fromDateTime(now.add(const Duration(hours: 2))),
    );
    if (time == null) return;
    setState(() {
      _dueAt = DateTime(date.year, date.month, date.day, time.hour, time.minute);
    });
  }

  Future<void> _save() async {
    if (_saving) return;
    setState(() => _saving = true);
    final repo = context.read<AppState>().repo;
    try {
      await repo.createCheckIn(
        note: _noteCtrl.text.trim().isEmpty ? null : _noteCtrl.text.trim(),
        dueAt: _dueAt,
      );
      if (mounted) Navigator.of(context).pop(true);
    } catch (e) {
      if (!mounted) return;
      setState(() => _saving = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('$e')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return AlertDialog(
      title: const Text('New check-in'),
      content: SizedBox(
        width: 320,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              controller: _noteCtrl,
              maxLines: 2,
              maxLength: 500,
              decoration: const InputDecoration(
                labelText: 'Note (optional)',
                hintText: 'e.g. Night walk — back by 10 PM',
              ),
            ),
            const SizedBox(height: 8),
            ListTile(
              contentPadding: EdgeInsets.zero,
              leading: const Icon(Icons.schedule),
              title: Text(
                _dueAt == null
                    ? 'Set a deadline (optional)'
                    : 'Due ${formatDateTime(_dueAt!)}',
              ),
              trailing: const Icon(Icons.edit_calendar_outlined),
              onTap: _pickDue,
            ),
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: _saving ? null : () => Navigator.of(context).pop(false),
          child: const Text('Cancel'),
        ),
        FilledButton(
          onPressed: _saving ? null : _save,
          child: _saving
              ? const SizedBox(
                  height: 18,
                  width: 18,
                  child: CircularProgressIndicator(strokeWidth: 2),
                )
              : const Text('Create'),
        ),
      ],
    );
  }
}
