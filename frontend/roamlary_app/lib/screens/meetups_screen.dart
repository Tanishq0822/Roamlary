import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/app_theme.dart';
import '../core/format.dart';
import '../models/enums.dart';
import '../models/models.dart';
import '../state/app_state.dart';
import '../widgets/common.dart';

/// Meetups & house parties (Phase 9): browse community events, join or
/// leave them, and host a new one. Mirrors the backend's capacity and
/// participation rules in the UI (full events cannot be joined; only the
/// host can cancel).
class MeetupsScreen extends StatefulWidget {
  const MeetupsScreen({super.key});

  @override
  State<MeetupsScreen> createState() => _MeetupsScreenState();
}

class _MeetupsScreenState extends State<MeetupsScreen> {
  List<Meetup>? _items;
  Object? _error;
  bool _busy = false;
  MeetupCategory? _categoryFilter;

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
      final items = await context.read<AppState>().repo.listMeetups();
      if (mounted) setState(() => _items = items);
    } catch (e) {
      if (mounted) setState(() => _error = e);
    }
  }

  Future<void> _run(Future<void> Function() action) async {
    if (_busy) return;
    setState(() => _busy = true);
    try {
      await action();
      await _load();
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('$e')),
        );
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _openCreate() async {
    final created = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (_) => const _CreateMeetupSheet(),
    );
    if (created == true) await _load();
  }

  @override
  Widget build(BuildContext context) {
    final filtered = _items
        ?.where((m) => _categoryFilter == null || m.category == _categoryFilter)
        .toList();

    return Scaffold(
      appBar: AppBar(
        title: const Text('Meetups'),
        actions: [
          IconButton(
            tooltip: 'Filter by category',
            icon: Icon(
              _categoryFilter == null
                  ? Icons.filter_list_outlined
                  : Icons.filter_list,
              color: _categoryFilter == null ? null : AppTheme.green,
            ),
            onPressed: _pickFilter,
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        heroTag: 'fab-meetups',
        onPressed: _openCreate,
        icon: const Icon(Icons.add),
        label: const Text('Host'),
      ),
      body: _items == null && _error == null
          ? const LoadingView()
          : _error != null
              ? ErrorView(message: '$_error', onRetry: _load)
              : filtered!.isEmpty
                  ? EmptyView(
                      icon: Icons.event_outlined,
                      title: 'No meetups here',
                      message: _categoryFilter == null
                          ? 'Host the first one — hikers and foodies are '
                              'waiting.'
                          : 'Nothing in ${_categoryFilter!.label} right now.',
                      action: OutlinedButton(
                        onPressed: _pickFilter,
                        child: const Text('Change filter'),
                      ),
                    )
                  : RefreshIndicator(
                      onRefresh: _load,
                      child: ListView.separated(
                        padding: const EdgeInsets.fromLTRB(16, 12, 16, 88),
                        itemCount: filtered.length,
                        separatorBuilder: (_, _) => const SizedBox(height: 12),
                        itemBuilder: (context, i) => _MeetupCard(
                          meetup: filtered[i],
                          busy: _busy,
                          onJoin: () =>
                              _run(() => context.read<AppState>().repo
                                  .joinMeetup(filtered[i].id)),
                          onLeave: () =>
                              _run(() => context.read<AppState>().repo
                                  .leaveMeetup(filtered[i].id)),
                        ),
                      ),
                    ),
    );
  }

  Future<void> _pickFilter() async {
    final picked = await showModalBottomSheet<MeetupCategory?>(
      context: context,
      showDragHandle: true,
      builder: (sheetContext) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            ListTile(
              title: const Text('All categories'),
              leading: const Icon(Icons.all_inclusive),
              onTap: () => Navigator.of(sheetContext).pop(null),
            ),
            for (final c in MeetupCategory.values)
              ListTile(
                title: Text(c.label),
                onTap: () => Navigator.of(sheetContext).pop(c),
              ),
            const SizedBox(height: 8),
          ],
        ),
      ),
    );
    setState(() => _categoryFilter = picked);
  }
}

class _MeetupCard extends StatelessWidget {
  const _MeetupCard({
    required this.meetup,
    required this.busy,
    required this.onJoin,
    required this.onLeave,
  });

  final Meetup meetup;
  final bool busy;
  final VoidCallback onJoin;
  final VoidCallback onLeave;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final going = meetup.myMembership == MembershipStatus.approved;
    final requested = meetup.myMembership == MembershipStatus.requested;
    final full = meetup.approvedCount >= meetup.capacity;
    final cancelled = meetup.status != MeetupStatus.active;

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _CategoryBadge(category: meetup.category),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        meetup.title,
                        style: theme.textTheme.titleSmall
                            ?.copyWith(fontWeight: FontWeight.w800),
                      ),
                      const SizedBox(height: 2),
                      Text(
                        'Hosted by ${meetup.hostDisplayName}',
                        style: theme.textTheme.labelSmall
                            ?.copyWith(color: theme.colorScheme.onSurfaceVariant),
                      ),
                    ],
                  ),
                ),
                StatusPill(
                  label: cancelled ? meetup.status.label : (full ? 'Full' : 'Open'),
                  color: cancelled
                      ? AppTheme.danger
                      : full
                          ? Colors.orange.shade800
                          : AppTheme.green,
                ),
              ],
            ),
            if (meetup.description != null) ...[
              const SizedBox(height: 10),
              Text(meetup.description!, style: theme.textTheme.bodyMedium),
            ],
            const SizedBox(height: 12),
            _InfoRow(
              icon: Icons.schedule,
              text:
                  '${formatDateTime(meetup.startAt)} → ${formatTime(meetup.endAt)}',
            ),
            if (meetup.locationText != null)
              _InfoRow(icon: Icons.place_outlined, text: meetup.locationText!),
            _InfoRow(
              icon: Icons.people_outline,
              text:
                  '${meetup.approvedCount}/${meetup.capacity} going · ${meetup.participation == 'open' ? 'open join' : 'host approval'}',
            ),
            const SizedBox(height: 12),
            if (going)
              OutlinedButton.icon(
                onPressed: busy ? null : () => onLeave(),
                icon: const Icon(Icons.logout, size: 18),
                label: const Text('Leave'),
              )
            else if (requested)
              const StatusPill(label: 'Request pending', color: Colors.orange)
            else
              FilledButton.icon(
                onPressed: cancelled || full || busy ? null : () => onJoin(),
                icon: const Icon(Icons.event_available, size: 18),
                label: Text(full ? 'Full' : 'Join'),
              ),
          ],
        ),
      ),
    );
  }
}

class _CategoryBadge extends StatelessWidget {
  const _CategoryBadge({required this.category});

  final MeetupCategory category;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 44,
      height: 44,
      decoration: BoxDecoration(
        color: AppTheme.purple.withValues(alpha: 0.14),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Icon(_icon, color: AppTheme.purple, size: 22),
    );
  }

  IconData get _icon => switch (category) {
        MeetupCategory.hiking => Icons.terrain,
        MeetupCategory.food => Icons.restaurant,
        MeetupCategory.culture => Icons.museum_outlined,
        MeetupCategory.adventure => Icons.paragliding,
        MeetupCategory.leisure => Icons.beach_access,
        MeetupCategory.nightlife => Icons.nightlife_outlined,
        MeetupCategory.other => Icons.event,
      };
}

class _InfoRow extends StatelessWidget {
  const _InfoRow({required this.icon, required this.text});

  final IconData icon;
  final String text;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.only(bottom: 4),
      child: Row(
        children: [
          Icon(icon, size: 15, color: theme.colorScheme.onSurfaceVariant),
          const SizedBox(width: 6),
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

/// Creation form: title, category, start/end, location, capacity — each
/// validated the way the backend validates it.
class _CreateMeetupSheet extends StatefulWidget {
  const _CreateMeetupSheet();

  @override
  State<_CreateMeetupSheet> createState() => _CreateMeetupSheetState();
}

class _CreateMeetupSheetState extends State<_CreateMeetupSheet> {
  final _titleCtrl = TextEditingController();
  final _descriptionCtrl = TextEditingController();
  final _locationCtrl = TextEditingController();
  final _capacityCtrl = TextEditingController(text: '20');

  MeetupCategory _category = MeetupCategory.hiking;
  DateTime _start = DateTime.now().add(const Duration(days: 1));
  DateTime _end = DateTime.now().add(const Duration(days: 1, hours: 3));
  bool _submitting = false;
  String? _error;

  @override
  void dispose() {
    _titleCtrl.dispose();
    _descriptionCtrl.dispose();
    _locationCtrl.dispose();
    _capacityCtrl.dispose();
    super.dispose();
  }

  Future<void> _pickTime({required bool isStart}) async {
    final date = await showDatePicker(
      context: context,
      initialDate: isStart ? _start : _end,
      firstDate: DateTime.now().subtract(const Duration(days: 1)),
      lastDate: DateTime.now().add(const Duration(days: 365)),
    );
    if (date == null || !mounted) return;
    final time = await showTimePicker(
      context: context,
      initialTime: TimeOfDay.fromDateTime(isStart ? _start : _end),
    );
    if (time == null || !mounted) return;
    final combined =
        DateTime(date.year, date.month, date.day, time.hour, time.minute);
    setState(() {
      if (isStart) {
        _start = combined;
        if (!_end.isAfter(_start)) {
          _end = _start.add(const Duration(hours: 2));
        }
      } else {
        _end = combined;
      }
    });
  }

  Future<void> _submit() async {
    final title = _titleCtrl.text.trim();
    final description = _descriptionCtrl.text.trim();
    final capacity = int.tryParse(_capacityCtrl.text.trim()) ?? 0;

    final errors = <String>[
      if (title.isEmpty) 'Give the meetup a title.',
      if (title.length > 120) 'Title must be at most 120 characters.',
      if (description.length > 1000) 'Description is too long (max 1000).',
      if (capacity < 2 || capacity > 500) 'Capacity must be between 2 and 500.',
      if (!_end.isAfter(_start)) 'End time must be after start time.',
      if (_start.isBefore(DateTime.now().subtract(const Duration(minutes: 5))))
        'Start time cannot be in the past.',
    ];
    if (errors.isNotEmpty) {
      setState(() => _error = errors.first);
      return;
    }

    setState(() {
      _submitting = true;
      _error = null;
    });
    try {
      await context.read<AppState>().repo.createMeetup(
            title: title,
            description: description.isEmpty ? null : description,
            category: _category,
            startAt: _start,
            endAt: _end,
            locationText: _locationCtrl.text.trim().isEmpty
                ? null
                : _locationCtrl.text.trim(),
            capacity: capacity,
          );
      if (!mounted) return;
      Navigator.of(context).pop(true);
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _submitting = false;
        _error = '$e';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Padding(
      padding: EdgeInsets.only(
        left: 20,
        right: 20,
        bottom: MediaQuery.viewInsetsOf(context).bottom + 24,
      ),
      child: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text('Host a meetup', style: theme.textTheme.titleLarge),
            const SizedBox(height: 16),
            TextField(
              controller: _titleCtrl,
              maxLength: 120,
              decoration: const InputDecoration(
                labelText: 'Title *',
                hintText: 'e.g. Sunrise hike at Annapurna base',
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 12),
            DropdownButtonFormField<MeetupCategory>(
              initialValue: _category,
              decoration: const InputDecoration(
                labelText: 'Category',
                border: OutlineInputBorder(),
              ),
              items: [
                for (final c in MeetupCategory.values)
                  DropdownMenuItem(value: c, child: Text(c.label)),
              ],
              onChanged: (v) => setState(() => _category = v ?? _category),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _descriptionCtrl,
              maxLines: 2,
              maxLength: 1000,
              decoration: const InputDecoration(
                labelText: 'Description',
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _locationCtrl,
              decoration: const InputDecoration(
                labelText: 'Location',
                hintText: 'e.g. Pokhara, Nepal',
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 16),
            Row(
              children: [
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: () => _pickTime(isStart: true),
                    icon: const Icon(Icons.play_arrow, size: 18),
                    label: Text('Start: ${formatDateTime(_start)}'),
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: () => _pickTime(isStart: false),
                    icon: const Icon(Icons.stop, size: 18),
                    label: Text('End: ${formatDateTime(_end)}'),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _capacityCtrl,
              keyboardType: TextInputType.number,
              decoration: const InputDecoration(
                labelText: 'Capacity (2–500)',
                border: OutlineInputBorder(),
              ),
            ),
            if (_error != null) ...[
              const SizedBox(height: 12),
              Text(_error!, style: TextStyle(color: theme.colorScheme.error)),
            ],
            const SizedBox(height: 16),
            FilledButton(
              onPressed: _submitting ? null : _submit,
              style: FilledButton.styleFrom(padding: const EdgeInsets.symmetric(vertical: 16)),
              child: _submitting
                  ? const SizedBox(
                      width: 20,
                      height: 20,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Text('Create meetup'),
            ),
          ],
        ),
      ),
    );
  }
}
