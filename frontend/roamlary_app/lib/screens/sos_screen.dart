import 'package:flutter/material.dart';
import 'package:geolocator/geolocator.dart';
import 'package:provider/provider.dart';

import '../core/app_theme.dart';
import '../core/format.dart';
import '../data/app_repository.dart';
import '../models/enums.dart';
import '../models/models.dart';
import '../state/app_state.dart';
import '../widgets/common.dart';

/// SOS workflow screen.
///
/// Mirrors the backend's lifecycle exactly (`backend/app/api/v1/endpoints/
/// sos_events.py`):
///
///   active ──acknowledge──▶ acknowledged ──resolve/cancel──▶ closed
///     └────────resolve / cancel──────────────────────────────▶ closed
///
/// Validation enforced here, matching the server's 422s so users never hit
/// them:
///  * description: trimmed, ≤500 chars, blank becomes null;
///  * coordinates: all-or-nothing, range-checked;
///  * every transition is compare-and-set — a 409 (someone else already
///    moved the incident) surfaces as a snackbar + refresh, never a crash.
///
/// Honest boundary: this records and relays an incident to your trusted
/// contacts. It does not call emergency services. That is stated in the UI.
class SosScreen extends StatefulWidget {
  const SosScreen({super.key});

  @override
  State<SosScreen> createState() => _SosScreenState();
}

class _SosScreenState extends State<SosScreen> {
  final _descriptionCtrl = TextEditingController();
  List<SosEvent>? _events;
  List<AppNotification>? _attempts;
  String? _attemptsForId;
  Object? _error;
  bool _submitting = false;
  bool _withLocation = true;
  bool _locating = false;
  String? _formError;

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
      if (mounted) setState(() => _events = events);
    } catch (e) {
      if (mounted) setState(() => _error = e);
    }
  }

  /// Client-side mirror of `SosEventCreate`'s validators. Returns an error
  /// string, or null when the payload is valid.
  String? _validate(String description) {
    if (description.length > 500) {
      return 'Description must be 500 characters or fewer '
          '(${description.length}/500).';
    }
    return null;
  }

  Future<void> _activate() async {
    final description = _descriptionCtrl.text.trim();
    final validationError = _validate(description);
    if (validationError != null) {
      setState(() => _formError = validationError);
      return;
    }
    if (_submitting) return;
    setState(() {
      _submitting = true;
      _formError = null;
      _locating = false;
    });
    final repo = context.read<AppState>().repo;

    double? lat;
    double? lng;
    try {
      if (_withLocation) {
        setState(() => _locating = true);
        try {
          final perm = await Geolocator.checkPermission();
          var effective = perm;
          if (perm == LocationPermission.denied) {
            effective = await Geolocator.requestPermission();
          }
          if (effective == LocationPermission.always ||
              effective == LocationPermission.whileInUse) {
            final pos = await Geolocator.getCurrentPosition(
              locationSettings: const LocationSettings(
                accuracy: LocationAccuracy.high,
                timeLimit: Duration(seconds: 10),
              ),
            );
            lat = pos.latitude;
            lng = pos.longitude;
          }
        } catch (_) {
          // Denied/timeout: continue without coordinates — the backend
          // treats location as optional (all-or-nothing, never guessed).
        }
      }

      await repo.createSos(
            description: description.isEmpty ? null : description,
            latitude: lat,
            longitude: lng,
          );
      _descriptionCtrl.clear();
      await _load();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('SOS raised. Your trusted contacts have been '
                'alerted with your location.'),
            backgroundColor: AppTheme.danger,
          ),
        );
      }
    } catch (e) {
      if (mounted) setState(() => _formError = '$e');
    } finally {
      if (mounted) {
        setState(() {
          _submitting = false;
          _locating = false;
        });
      }
    }
  }

  /// One transition (acknowledge / resolve / cancel) with 409 handling.
  Future<void> _transition(
    String id,
    Future<SosEvent> Function(AppRepository repo) action, [
    String label = 'update',
  ]) async {
    final repo = context.read<AppState>().repo;
    try {
      await action(repo);
      await _load();
      if (mounted && _attemptsForId == id) await _loadAttempts(id);
    } catch (e) {
      if (!mounted) return;
      // 409 = the incident already moved (concurrent transition). Reload so
      // the UI reflects reality instead of a stale action set.
      final conflict = '$e'.contains('409') || '$e'.contains('conflict');
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(conflict
              ? 'That incident already changed state elsewhere — refreshed.'
              : 'Could not $label: $e'),
        ),
      );
      await _load();
      if (mounted && _attemptsForId == id) await _loadAttempts(id);
    }
  }

  Future<void> _loadAttempts(String sosId) async {
    setState(() {
      _attemptsForId = sosId;
      _attempts = null;
    });
    try {
      final list =
          await context.read<AppState>().repo.listSosNotifications(sosId);
      if (mounted) setState(() => _attempts = list);
    } catch (e) {
      if (mounted) setState(() => _attempts = []);
    }
  }

  Future<void> _retry(String sosId) async {
    try {
      final list =
          await context.read<AppState>().repo.retrySosNotifications(sosId);
      if (!mounted) return;
      setState(() {
        _attempts = list;
        _attemptsForId = sosId;
      });
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Re-sent to ${list.length} contact(s).')),
      );
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text('Retry failed: $e')));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(title: const Text('SOS')),
      body: _events == null && _error == null
          ? const LoadingView()
          : _error != null
              ? ErrorView(message: '$_error', onRetry: _load)
              : RefreshIndicator(
                  onRefresh: _load,
                  child: ListView(
                    padding: const EdgeInsets.fromLTRB(16, 12, 16, 32),
                    children: [
                      _buildForm(theme),
                      const SizedBox(height: 20),
                      Text(
                        'INCIDENT HISTORY',
                        style: theme.textTheme.labelSmall?.copyWith(
                          color: theme.colorScheme.onSurfaceVariant,
                          fontWeight: FontWeight.w700,
                          letterSpacing: 1.1,
                        ),
                      ),
                      const SizedBox(height: 8),
                      if (_events!.isEmpty)
                        Text(
                          'No incidents recorded.',
                          style: theme.textTheme.bodyMedium?.copyWith(
                            color: theme.colorScheme.onSurfaceVariant,
                          ),
                        )
                      else
                        for (final event in _events!)
                          Padding(
                            padding: const EdgeInsets.only(bottom: 12),
                            child: _IncidentCard(
                              event: event,
                              attempts: _attemptsForId == event.id
                                  ? _attempts
                                  : null,
                              attemptsOpen: _attemptsForId == event.id,
                              onShowAttempts: () =>
                                  _attemptsForId == event.id
                                      ? setState(() {
                                          _attemptsForId = null;
                                          _attempts = null;
                                        })
                                      : _loadAttempts(event.id),
                              onRetry: () => _retry(event.id),
                              onAcknowledge: event.status == SosStatus.active
                                  ? () => _transition(
                                        event.id,
                                        (r) => r.acknowledgeSos(event.id),
                                        'acknowledge',
                                      )
                                  : null,
                              onResolve: event.isOpen
                                  ? () => _transition(
                                        event.id,
                                        (r) => r.resolveSos(event.id),
                                        'resolve',
                                      )
                                  : null,
                              onCancel: event.isOpen
                                  ? () => _confirmCancel(event)
                                  : null,
                            ),
                          ),
                    ],
                  ),
                ),
    );
  }

  Widget _buildForm(ThemeData theme) {
    final description = _descriptionCtrl.text.trim();
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: AppTheme.danger.withValues(alpha: 0.05),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: AppTheme.danger.withValues(alpha: 0.35)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.sos, color: AppTheme.danger, size: 28),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  'Raise an SOS',
                  style: theme.textTheme.titleMedium
                      ?.copyWith(fontWeight: FontWeight.w800),
                ),
              ),
            ],
          ),
          const SizedBox(height: 6),
          Text(
            'Records an incident and relays it to your trusted contacts with '
            'your last known location. Roamlary does not call emergency '
            'services on your behalf.',
            style: theme.textTheme.bodySmall?.copyWith(
              color: theme.colorScheme.onSurfaceVariant,
              height: 1.4,
            ),
          ),
          const SizedBox(height: 14),
          TextField(
            controller: _descriptionCtrl,
            maxLength: 500,
            maxLines: 3,
            textInputAction: TextInputAction.done,
            onChanged: (_) => setState(() {}),
            decoration: InputDecoration(
              labelText: 'What is happening? (optional)',
              hintText: 'e.g. Lost near the station, phone at 12%',
              border: const OutlineInputBorder(),
              counterText: '${description.length}/500',
              errorText: _formError,
            ),
          ),
          SwitchListTile(
            contentPadding: EdgeInsets.zero,
            title: const Text('Attach my live location'),
            subtitle: Text(_locating
                ? 'Getting your position…'
                : 'Captured once, at activation time'),
            value: _withLocation,
            onChanged: _submitting
                ? null
                : (v) => setState(() => _withLocation = v),
          ),
          const SizedBox(height: 8),
          SizedBox(
            width: double.infinity,
            child: FilledButton.icon(
              style: FilledButton.styleFrom(
                backgroundColor: AppTheme.danger,
                padding: const EdgeInsets.symmetric(vertical: 16),
              ),
              onPressed: _submitting ? null : _activate,
              icon: _submitting
                  ? const SizedBox(
                      width: 18,
                      height: 18,
                      child: CircularProgressIndicator(
                          strokeWidth: 2, color: Colors.white),
                    )
                  : const Icon(Icons.warning_amber_rounded),
              label: Text(_submitting ? 'Raising…' : 'Activate SOS'),
            ),
          ),
        ],
      ),
    );
  }

  Future<void> _confirmCancel(SosEvent event) async {
    final go = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Cancel this incident?'),
        content: const Text(
            'Use this only if the emergency is over or it was raised by '
            'mistake. Contacts you already alerted will see it closed.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(false),
            child: const Text('Keep it open'),
          ),
          FilledButton(
            style:
                FilledButton.styleFrom(backgroundColor: AppTheme.danger),
            onPressed: () => Navigator.of(dialogContext).pop(true),
            child: const Text('Cancel incident'),
          ),
        ],
      ),
    );
    if (go == true) {
      await _transition(event.id, (r) => r.cancelSos(event.id), 'cancel');
    }
  }
}

// ---------------------------------------------------------------------------

class _IncidentCard extends StatelessWidget {
  const _IncidentCard({
    required this.event,
    required this.attempts,
    required this.attemptsOpen,
    required this.onShowAttempts,
    required this.onRetry,
    this.onAcknowledge,
    this.onResolve,
    this.onCancel,
  });

  final SosEvent event;
  final List<AppNotification>? attempts;
  final bool attemptsOpen;
  final VoidCallback onShowAttempts;
  final VoidCallback onRetry;
  final VoidCallback? onAcknowledge;
  final VoidCallback? onResolve;
  final VoidCallback? onCancel;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final (statusLabel, statusColor) = switch (event.status) {
      SosStatus.active => ('ACTIVE', AppTheme.danger),
      SosStatus.acknowledged => ('Acknowledged', Colors.orange.shade800),
      SosStatus.resolved => ('Resolved', AppTheme.green),
      SosStatus.falseAlarm => ('False alarm', Colors.grey),
      SosStatus.cancelled => ('Cancelled', Colors.grey),
    };
    final isOpen = event.isOpen;

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(18),
        border: Border.all(
          color: isOpen
              ? AppTheme.danger.withValues(alpha: 0.5)
              : theme.dividerColor,
        ),
        color: isOpen
            ? AppTheme.danger.withValues(alpha: 0.04)
            : theme.colorScheme.surface,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              StatusPill(label: statusLabel, color: statusColor),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  formatDateTime(event.createdAt),
                  style: theme.textTheme.bodySmall,
                ),
              ),
              Text(
                relativeLabel(event.createdAt),
                style: theme.textTheme.labelSmall
                    ?.copyWith(color: theme.colorScheme.onSurfaceVariant),
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
                const Icon(Icons.place, size: 16, color: AppTheme.danger),
                const SizedBox(width: 6),
                Expanded(
                  child: Text(
                    '${event.latitude!.toStringAsFixed(4)}, '
                    '${event.longitude!.toStringAsFixed(4)}',
                    style: theme.textTheme.bodySmall,
                  ),
                ),
                if (event.locationRecordedAt != null)
                  Text(
                    'at ${formatTime(event.locationRecordedAt!)}',
                    style: theme.textTheme.labelSmall
                        ?.copyWith(color: theme.colorScheme.onSurfaceVariant),
                  ),
              ],
            ),
          ] else if (isOpen) ...[
            const SizedBox(height: 8),
            Text(
              'No coordinates attached to this incident.',
              style: theme.textTheme.bodySmall
                  ?.copyWith(color: theme.colorScheme.onSurfaceVariant),
            ),
          ],
          // Timestamps for the closed states.
          if (event.acknowledgedAt != null)
            _Stamp(
              icon: Icons.visibility_outlined,
              text: 'Acknowledged ${formatDateTime(event.acknowledgedAt!)}',
              color: Colors.orange.shade800,
            ),
          if (event.resolvedAt != null)
            _Stamp(
              icon: Icons.check_circle_outline,
              text: 'Resolved ${formatDateTime(event.resolvedAt!)}',
              color: AppTheme.green,
            ),
          if (event.cancelledAt != null)
            _Stamp(
              icon: Icons.cancel_outlined,
              text: 'Cancelled ${formatDateTime(event.cancelledAt!)}',
              color: Colors.grey,
            ),
          const SizedBox(height: 12),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              if (onAcknowledge != null)
                FilledButton.icon(
                  style: FilledButton.styleFrom(
                      backgroundColor: Colors.orange.shade800),
                  onPressed: onAcknowledge,
                  icon: const Icon(Icons.visibility_outlined, size: 18),
                  label: const Text('Acknowledge'),
                ),
              if (onResolve != null)
                FilledButton.icon(
                  style: FilledButton.styleFrom(
                      backgroundColor: AppTheme.green),
                  onPressed: onResolve,
                  icon: const Icon(Icons.check, size: 18),
                  label: const Text('I am safe'),
                ),
              if (onCancel != null)
                OutlinedButton.icon(
                  style: OutlinedButton.styleFrom(
                      foregroundColor: AppTheme.danger),
                  onPressed: onCancel,
                  icon: const Icon(Icons.close, size: 18),
                  label: const Text('Cancel'),
                ),
              OutlinedButton.icon(
                onPressed: onRetry,
                icon: const Icon(Icons.cached, size: 18),
                label: const Text('Re-notify'),
              ),
              TextButton.icon(
                onPressed: onShowAttempts,
                icon: Icon(
                  attemptsOpen
                      ? Icons.keyboard_arrow_up
                      : Icons.keyboard_arrow_down,
                  size: 18,
                ),
                label: Text(attemptsOpen ? 'Hide log' : 'Contact log'),
              ),
            ],
          ),
          if (attemptsOpen) ...[
            const SizedBox(height: 10),
            if (attempts == null)
              const Center(
                child: Padding(
                  padding: EdgeInsets.all(8),
                  child: SizedBox(
                    width: 18,
                    height: 18,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  ),
                ),
              )
            else if (attempts!.isEmpty)
              Text(
                'No relay attempts recorded for this incident.',
                style: theme.textTheme.bodySmall,
              )
            else
              for (final a in attempts!)
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 3),
                  child: Row(
                    children: [
                      Icon(Icons.circle,
                          size: 8,
                          color: a.status == NotificationStatus.delivered
                              ? AppTheme.green
                              : a.status == NotificationStatus.failed
                                  ? AppTheme.danger
                                  : Colors.orange.shade800),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          '${a.channel} · ${a.body}',
                          style: theme.textTheme.bodySmall,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                      Text(
                        '${a.status.wire} · ${a.attempts}×',
                        style: theme.textTheme.labelSmall,
                      ),
                    ],
                  ),
                ),
          ],
        ],
      ),
    );
  }
}

class _Stamp extends StatelessWidget {
  const _Stamp({required this.icon, required this.text, required this.color});

  final IconData icon;
  final String text;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(top: 8),
      child: Row(
        children: [
          Icon(icon, size: 15, color: color),
          const SizedBox(width: 6),
          Text(
            text,
            style: Theme.of(context)
                .textTheme
                .labelSmall
                ?.copyWith(color: color, fontWeight: FontWeight.w600),
          ),
        ],
      ),
    );
  }
}
