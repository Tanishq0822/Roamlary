import 'dart:async';

import 'package:flutter/material.dart';
import 'package:geolocator/geolocator.dart';
import 'package:provider/provider.dart';

import '../core/app_theme.dart';
import '../core/format.dart';
import '../models/enums.dart';
import '../models/models.dart';
import '../state/app_state.dart';
import '../widgets/common.dart';

/// Check-ins: create a "promise" check-in with an optional deadline, share
/// live location with it, then answer it as SAFE or NEEDS_HELP, or cancel.
///
/// LOCATION SHARING: the backend's check-in contract carries no coordinate
/// fields, so live position is written into the (500-char) note as a
/// `📍 lat,lng` marker and parsed back via [CheckIn.location]. While a
/// pending check-in is "sharing", this screen refreshes that marker every
/// [_refreshInterval] so contacts always see a recent position — that is the
/// real-time part. Overdue check-ins surface in their own banner at the top.
class CheckInsScreen extends StatefulWidget {
  const CheckInsScreen({super.key});

  @override
  State<CheckInsScreen> createState() => _CheckInsScreenState();
}

/// How often a sharing check-in pushes a fresh coordinate.
const _refreshInterval = Duration(seconds: 20);

class _CheckInsScreenState extends State<CheckInsScreen> {
  List<CheckIn>? _items;
  List<CheckIn> _overdue = const [];
  Object? _error;

  Timer? _ticker;
  final Set<String> _sharingIds = {};
  final Map<String, DateTime> _lastSharedAt = {};
  bool _locating = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _ticker?.cancel();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() {
      _error = null;
      _items = null;
    });
    final repo = context.read<AppState>().repo;
    try {
      final items = await repo.listCheckIns();
      List<CheckIn> overdue = const [];
      try {
        overdue = await repo.listOverdueCheckIns();
      } catch (_) {
        // Older backend / offline: the banner simply doesn't show.
      }
      if (!mounted) return;
      setState(() {
        _items = items;
        _overdue = overdue;
      });
      _ensureTicker();
    } catch (e) {
      if (!mounted) return;
      setState(() => _error = e);
    }
  }

  // -- live location ---------------------------------------------------------

  void _ensureTicker() {
    _ticker?.cancel();
    final hasSharing = _items?.any(
          (c) => c.status == CheckInStatus.pending && _sharingIds.contains(c.id),
        ) ??
        false;
    if (hasSharing) {
      _ticker = Timer.periodic(_refreshInterval, (_) => _pushLocations());
    }
  }

  Future<Position?> _currentPosition() async {
    try {
      var perm = await Geolocator.checkPermission();
      if (perm == LocationPermission.denied) {
        perm = await Geolocator.requestPermission();
      }
      if (perm == LocationPermission.denied ||
          perm == LocationPermission.deniedForever) {
        return null;
      }
      return await Geolocator.getCurrentPosition(
        locationSettings: const LocationSettings(
          accuracy: LocationAccuracy.high,
          timeLimit: Duration(seconds: 10),
        ),
      );
    } catch (_) {
      return null;
    }
  }

  /// Write a fresh coordinate into the note of every check-in that is
  /// currently being shared. Blanks are skipped so a denied permission
  /// doesn't wipe an existing marker.
  Future<void> _pushLocations() async {
    if (_locating) return;
    setState(() => _locating = true);
    try {
      final repo = context.read<AppState>().repo;
      final pending =
          _items?.where((c) => _sharingIds.contains(c.id)).toList() ?? const [];
      for (final checkIn in pending) {
        if (checkIn.status != CheckInStatus.pending) continue;
        final pos = await _currentPosition();
        if (pos == null) continue;
        final note = _withLocation(checkIn.noteWithoutLocation, pos);
        try {
          final updated = await repo.updateCheckInNote(checkIn.id, note: note);
          if (!mounted) continue;
          setState(() {
            final i = _items!.indexWhere((c) => c.id == checkIn.id);
            if (i != -1) _items![i] = updated;
            _lastSharedAt[checkIn.id] = DateTime.now();
          });
        } catch (_) {
          // One failed push shouldn't stop the others.
        }
      }
    } finally {
      if (mounted) setState(() => _locating = false);
      _ensureTicker();
    }
  }

  static String _withLocation(String? base, Position pos) {
    final marker = '📍 ${pos.latitude.toStringAsFixed(5)},'
        ' ${pos.longitude.toStringAsFixed(5)}';
    final body = (base == null || base.isEmpty) ? '' : '$base\n';
    final combined = '$body$marker';
    // The backend caps notes at 500 chars — keep the marker, trim the prose.
    return combined.length <= 500 ? combined : marker;
  }

  Future<void> _toggleSharing(CheckIn checkIn) async {
    final repo = context.read<AppState>().repo;
    if (_sharingIds.contains(checkIn.id)) {
      setState(() => _sharingIds.remove(checkIn.id));
      _ensureTicker();
      return;
    }
    setState(() => _locating = true);
    final pos = await _currentPosition();
    if (pos == null) {
      if (mounted) {
        setState(() => _locating = false);
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Location permission is off — enable it in your '
                'browser settings to share position.'),
          ),
        );
      }
      return;
    }
    try {
      final note = _withLocation(checkIn.noteWithoutLocation, pos);
      final updated = await repo.updateCheckInNote(checkIn.id, note: note);
      if (!mounted) return;
      setState(() {
        final i = _items!.indexWhere((c) => c.id == checkIn.id);
        if (i != -1) _items![i] = updated;
        _sharingIds.add(checkIn.id);
        _lastSharedAt[checkIn.id] = DateTime.now();
        _locating = false;
      });
      _ensureTicker();
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Sharing live location every '
              '${_refreshInterval.inSeconds}s until you stop or answer.'),
          backgroundColor: AppTheme.green,
        ),
      );
    } catch (e) {
      if (!mounted) return;
      setState(() => _locating = false);
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text('$e')));
    }
  }

  // -- CRUD ------------------------------------------------------------------

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
      _sharingIds.remove(c.id);
      if (mounted) await _load();
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('$e')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Safety check-ins')),
      floatingActionButton: FloatingActionButton.extended(
        heroTag: 'fab-checkins',
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
                  child: _items!.isEmpty && _overdue.isEmpty
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
                      : ListView(
                          padding: const EdgeInsets.fromLTRB(16, 16, 16, 88),
                          children: [
                            if (_overdue.isNotEmpty) ...[
                              _OverdueBanner(items: _overdue),
                              const SizedBox(height: 14),
                            ],
                            if (_locating)
                              const Padding(
                                padding: EdgeInsets.only(bottom: 12),
                                child: LinearProgressIndicator(),
                              ),
                            for (final c in _items!)
                              _CheckInCard(
                                checkIn: c,
                                onAnswer: _answer,
                                sharing: _sharingIds.contains(c.id),
                                lastSharedAt: _lastSharedAt[c.id],
                                onToggleSharing: () => _toggleSharing(c),
                              ),
                          ],
                        ),
                ),
    );
  }
}

// ---------------------------------------------------------------------------

/// Red banner listing check-ins whose deadline has passed unanswered.
class _OverdueBanner extends StatelessWidget {
  const _OverdueBanner({required this.items});

  final List<CheckIn> items;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppTheme.danger.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppTheme.danger.withValues(alpha: 0.5)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.timer_off_outlined,
                  color: AppTheme.danger, size: 20),
              const SizedBox(width: 8),
              Text(
                '${items.length} overdue — past your promised time',
                style: theme.textTheme.titleSmall?.copyWith(
                  fontWeight: FontWeight.w800,
                  color: AppTheme.danger,
                ),
              ),
            ],
          ),
          const SizedBox(height: 6),
          for (final c in items.take(3))
            Padding(
              padding: const EdgeInsets.only(bottom: 3),
              child: Text(
                '• ${c.noteWithoutLocation ?? 'Untitled'} — due '
                '${c.dueAt == null ? '' : relativeLabel(c.dueAt!)}',
                style: theme.textTheme.bodySmall,
              ),
            ),
        ],
      ),
    );
  }
}

class _CheckInCard extends StatelessWidget {
  const _CheckInCard({
    required this.checkIn,
    required this.onAnswer,
    required this.sharing,
    required this.lastSharedAt,
    required this.onToggleSharing,
  });

  final CheckIn checkIn;
  final void Function(CheckIn, CheckInStatus) onAnswer;
  final bool sharing;
  final DateTime? lastSharedAt;
  final VoidCallback onToggleSharing;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final status = checkIn.status;
    final location = checkIn.location;

    final (label, color) = switch (status) {
      CheckInStatus.pending => ('Pending', Colors.orange.shade800),
      CheckInStatus.safe => ('Safe', AppTheme.green),
      CheckInStatus.needsHelp => ('Needs help', AppTheme.danger),
      CheckInStatus.expired => ('Expired', Colors.grey),
      CheckInStatus.cancelled => ('Cancelled', Colors.grey),
    };
    final isOverdue = status == CheckInStatus.pending &&
        checkIn.dueAt != null &&
        checkIn.dueAt!.isBefore(DateTime.now());

    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(18),
        side: BorderSide(
          color: isOverdue
              ? AppTheme.danger.withValues(alpha: 0.5)
              : theme.dividerColor,
        ),
      ),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                StatusPill(label: label, color: color),
                if (isOverdue) ...[
                  const SizedBox(width: 8),
                  const StatusPill(label: 'OVERDUE', color: AppTheme.danger),
                ],
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    'Created ${formatDateTime(checkIn.createdAt)}',
                    style: theme.textTheme.bodySmall,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
              ],
            ),
            if (checkIn.noteWithoutLocation != null) ...[
              const SizedBox(height: 10),
              Text(checkIn.noteWithoutLocation!,
                  style: theme.textTheme.bodyMedium),
            ],
            if (checkIn.dueAt != null) ...[
              const SizedBox(height: 8),
              Row(
                children: [
                  Icon(Icons.schedule,
                      size: 16,
                      color: isOverdue ? AppTheme.danger : null),
                  const SizedBox(width: 4),
                  Text(
                    'Due ${formatDateTime(checkIn.dueAt!)} '
                    '(${relativeLabel(checkIn.dueAt!)})',
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: isOverdue ? AppTheme.danger : null,
                      fontWeight: isOverdue ? FontWeight.w700 : null,
                    ),
                  ),
                ],
              ),
            ],

            // Live location row -------------------------------------------
            if (location != null || sharing) ...[
              const SizedBox(height: 10),
              container(context, theme, location),
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
              // Share-location control (real-time).
              OutlinedButton.icon(
                style: OutlinedButton.styleFrom(
                  foregroundColor: sharing ? AppTheme.green : null,
                  minimumSize: const Size.fromHeight(42),
                ),
                onPressed: onToggleSharing,
                icon: Icon(
                  sharing ? Icons.location_on : Icons.location_on_outlined,
                  size: 18,
                ),
                label: Text(
                  sharing
                      ? 'Stop sharing location'
                      : (location == null
                          ? 'Share live location'
                          : 'Update location & share'),
                ),
              ),
              const SizedBox(height: 12),
              Row(
                children: [
                  Expanded(
                    child: FilledButton.icon(
                      style: FilledButton.styleFrom(
                        backgroundColor: AppTheme.green,
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

  Widget container(
    BuildContext context,
    ThemeData theme,
    CheckInLocation? location,
  ) {
    if (location == null) return const SizedBox.shrink();
    return InkWell(
      onTap: () => ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Open in maps: ${location.mapsUrl}')),
      ),
      borderRadius: BorderRadius.circular(12),
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
        decoration: BoxDecoration(
          color: AppTheme.greenTint,
          borderRadius: BorderRadius.circular(12),
        ),
        child: Row(
          children: [
            Icon(
              sharing ? Icons.location_on : Icons.location_on_outlined,
              size: 18,
              color: AppTheme.green,
            ),
            const SizedBox(width: 8),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    '${location.lat.toStringAsFixed(5)}, '
                    '${location.lng.toStringAsFixed(5)}',
                    style: theme.textTheme.bodySmall?.copyWith(
                      fontWeight: FontWeight.w700,
                      color: AppTheme.green,
                    ),
                  ),
                  if (sharing && lastSharedAt != null)
                    Text(
                      'Live · updated ${relativeLabel(lastSharedAt!)} '
                      '(every ${_refreshInterval.inSeconds}s)',
                      style: theme.textTheme.labelSmall
                          ?.copyWith(color: AppTheme.green),
                    )
                  else
                    Text(
                      'Shared with this check-in · tap for map',
                      style: theme.textTheme.labelSmall
                          ?.copyWith(color: AppTheme.green),
                    ),
                ],
              ),
            ),
            const Icon(Icons.open_in_new, size: 16, color: AppTheme.green),
          ],
        ),
      ),
    );
  }
}

// ---------------------------------------------------------------------------

class _CreateCheckInDialog extends StatefulWidget {
  const _CreateCheckInDialog();

  @override
  State<_CreateCheckInDialog> createState() => _CreateCheckInDialogState();
}

class _CreateCheckInDialogState extends State<_CreateCheckInDialog> {
  final _noteCtrl = TextEditingController();
  DateTime? _dueAt;
  bool _saving = false;
  bool _attachLocation = false;
  String? _formError;
  bool _locating = false;

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

    // Validation mirrors the backend: note ≤500 chars after trimming,
    // deadline must be in the future.
    var note = _noteCtrl.text.trim();
    if (_dueAt != null && _dueAt!.isBefore(DateTime.now())) {
      setState(() => _formError = 'The deadline must be in the future.');
      return;
    }
    if (note.length > 500) {
      setState(
          () => _formError = 'Note is too long (${note.length}/500).');
      return;
    }

    setState(() {
      _saving = true;
      _formError = null;
    });
    final repo = context.read<AppState>().repo;

    try {
      if (_attachLocation) {
        setState(() => _locating = true);
        try {
          var perm = await Geolocator.checkPermission();
          if (perm == LocationPermission.denied) {
            perm = await Geolocator.requestPermission();
          }
          if (perm == LocationPermission.whileInUse ||
              perm == LocationPermission.always) {
            final pos = await Geolocator.getCurrentPosition(
              locationSettings: const LocationSettings(
                accuracy: LocationAccuracy.high,
                timeLimit: Duration(seconds: 10),
              ),
            );
            final marker = '📍 ${pos.latitude.toStringAsFixed(5)},'
                ' ${pos.longitude.toStringAsFixed(5)}';
            note = note.isEmpty ? marker : '$note\n$marker';
            if (note.length > 500) note = marker;
          }
        } catch (_) {
          // Permission denied/timeout: create without coordinates.
        }
      }

      await repo.createCheckIn(
        note: note.isEmpty ? null : note,
        dueAt: _dueAt,
      );
      if (mounted) Navigator.of(context).pop(true);
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _saving = false;
        _locating = false;
        _formError = '$e';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
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
            SwitchListTile(
              contentPadding: EdgeInsets.zero,
              title: const Text('Attach my location'),
              subtitle: Text(_locating
                  ? 'Getting position…'
                  : 'Adds a 📍 coordinate to this check-in'),
              value: _attachLocation,
              onChanged: _saving
                  ? null
                  : (v) => setState(() => _attachLocation = v),
            ),
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
            if (_formError != null) ...[
              const SizedBox(height: 4),
              Text(
                _formError!,
                style: TextStyle(
                    color: Theme.of(context).colorScheme.error, fontSize: 12),
              ),
            ],
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
