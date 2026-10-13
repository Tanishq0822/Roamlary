import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/app_theme.dart';
import '../data/app_repository.dart';
import '../state/app_state.dart';

/// Live feature tests.
///
/// Every row calls the real repository (and therefore the real backend when
/// [AppConfig.useMocks] is off) and reports pass/fail with round-trip latency,
/// so a broken endpoint is visible here instead of as a silently empty screen
/// somewhere else. Nothing mutates state — all checks are reads.
///
/// The four sections map to the backend's phase groups:
///   1. Core & session
///   2. Discovery & social
///   3. Safety
///   4. Phase 9-13 (meetups, house parties, notifications, sharing, AI)
///
/// Endpoints are labelled exactly as the repository calls them. Note the
/// trailing slashes on `/check-ins/` and `/trusted-contacts/`: those routes
/// are declared as `/`, so calling them without the slash triggers FastAPI's
/// 307 redirect, which strips the `Authorization` header and answers 401.
class FeatureTestsScreen extends StatefulWidget {
  const FeatureTestsScreen({super.key});

  @override
  State<FeatureTestsScreen> createState() => _FeatureTestsScreenState();
}

typedef _Runner = Future<String> Function(AppRepository repo);

class _Check {
  const _Check(this.id, this.label, this.endpoint, this.run);

  final String id;
  final String label;

  /// Shown under the label so a failure points at a concrete route.
  final String endpoint;
  final _Runner run;
}

class _Section {
  const _Section(this.title, this.subtitle, this.icon, this.checks);

  final String title;
  final String subtitle;
  final IconData icon;
  final List<_Check> checks;
}

enum _Status { idle, running, pass, fail }

class _Result {
  const _Result(this.status, {this.ms = 0, this.detail = '', this.error = ''});

  final _Status status;
  final int ms;
  final String detail;
  final String error;

  static const idle = _Result(_Status.idle);
  static const running = _Result(_Status.running);
}

class _FeatureTestsScreenState extends State<FeatureTestsScreen> {
  final Map<String, _Result> _results = {};
  bool _runningAll = false;

  static final List<_Section> _sections = [
    _Section(
      'Core & session',
      'Reachability, identity and trusted contacts',
      Icons.foundation,
      const [
        _Check('health', 'Backend health', 'GET /health', _health),
        _Check(
          'verification',
          'Identity verification',
          'GET /verification/status',
          _verification,
        ),
        _Check(
          'contacts',
          'Trusted contacts',
          'GET /trusted-contacts/',
          _contacts,
        ),
      ],
    ),
    _Section(
      'Discovery & social',
      'Suggested travellers, blocking and chat requests',
      Icons.people_outline,
      const [
        _Check(
          'discovery',
          'Discovery pool',
          'GET /social/discovery',
          _discovery,
        ),
        _Check(
          'candidates',
          'Suggested travellers',
          'GET /travel-buddies/discover',
          _candidates,
        ),
        _Check('blocks', 'Blocked users', 'GET /blocks', _blocks),
        _Check(
          'chat_requests',
          'Incoming chat requests',
          'GET /chat/requests?direction=incoming',
          _chatRequests,
        ),
      ],
    ),
    _Section(
      'Safety',
      'Check-ins, SOS and community reports',
      Icons.shield_outlined,
      const [
        _Check('checkins', 'Check-ins', 'GET /check-ins/', _checkIns),
        _Check(
          'overdue',
          'Overdue check-ins',
          'GET /check-ins/overdue',
          _overdue,
        ),
        _Check('sos', 'SOS events', 'GET /sos', _sos),
        _Check('reports', 'Community reports', 'GET /reports', _reports),
      ],
    ),
    _Section(
      'Phase 9-13',
      'Meetups, house parties, notifications, sharing, AI',
      Icons.auto_awesome_outlined,
      const [
        _Check('meetups', 'Meetups', 'GET /meetups', _meetups),
        _Check(
          'invitations',
          'House-party invitations',
          'GET /invitations',
          _invitations,
        ),
        _Check(
          'notifications',
          'Notification inbox',
          'GET /notifications',
          _notifications,
        ),
        _Check('trip_shares', 'Trip shares', 'GET /trip-shares', _tripShares),
        _Check('ai', 'AI companion status', 'GET /ai/status', _ai),
      ],
    ),
  ];

  int get _total => _sections.fold(0, (n, s) => n + s.checks.length);

  int get _done => _results.values
      .where((r) => r.status == _Status.pass || r.status == _Status.fail)
      .length;

  int get _passing =>
      _results.values.where((r) => r.status == _Status.pass).length;

  Future<void> _runCheck(_Check check) async {
    setState(() => _results[check.id] = _Result.running);
    final repo = context.read<AppState>().repo;
    final sw = Stopwatch()..start();
    try {
      final detail = await check.run(repo);
      sw.stop();
      if (!mounted) return;
      setState(
        () => _results[check.id] = _Result(_Status.pass, ms: sw.elapsedMilliseconds, detail: detail),
      );
    } catch (e) {
      sw.stop();
      if (!mounted) return;
      setState(
        () => _results[check.id] = _Result(_Status.fail, ms: sw.elapsedMilliseconds, error: '$e'),
      );
    }
  }

  Future<void> _runAll() async {
    if (_runningAll) return;
    setState(() {
      _runningAll = true;
      _results.clear();
    });
    for (final section in _sections) {
      for (final check in section.checks) {
        await _runCheck(check);
      }
    }
    if (mounted) setState(() => _runningAll = false);
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Feature tests'),
        actions: [
          IconButton(
            tooltip: 'Run all',
            onPressed: _runningAll ? null : _runAll,
            icon: const Icon(Icons.play_arrow_rounded),
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(16, 12, 16, 32),
        children: [
          _SummaryCard(
            done: _done,
            total: _total,
            passing: _passing,
            running: _runningAll,
            onRunAll: _runAll,
          ),
          const SizedBox(height: 16),
          for (final section in _sections) ...[
            _SectionHeader(section: section),
            const SizedBox(height: 8),
            Card(
              margin: EdgeInsets.zero,
              clipBehavior: Clip.antiAlias,
              child: Column(
                children: [
                  for (final check in section.checks)
                    _CheckRow(
                      check: check,
                      result: _results[check.id] ?? _Result.idle,
                      disabled: _runningAll,
                      onTap: _runningAll
                          ? null
                          : () => _runCheck(check),
                    ),
                ],
              ),
            ),
            const SizedBox(height: 18),
          ],
          Text(
            'All checks are read-only. Latency is measured on the client, '
            'so a slow row usually means a cold backend rather than a bug.',
            style: theme.textTheme.bodySmall
                ?.copyWith(color: theme.colorScheme.onSurfaceVariant),
          ),
        ],
      ),
    );
  }
}

class _SummaryCard extends StatelessWidget {
  const _SummaryCard({
    required this.done,
    required this.total,
    required this.passing,
    required this.running,
    required this.onRunAll,
  });

  final int done;
  final int total;
  final int passing;
  final bool running;
  final VoidCallback onRunAll;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final pct = total == 0 ? 0.0 : done / total;

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(18),
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            AppTheme.green.withValues(alpha: 0.12),
            AppTheme.purple.withValues(alpha: 0.10),
          ],
        ),
        border: Border.all(color: theme.dividerColor),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  running ? 'Running…' : '$passing / $total passing',
                  style: theme.textTheme.titleLarge?.copyWith(
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ),
              FilledButton.icon(
                onPressed: running ? null : onRunAll,
                icon: running
                    ? const SizedBox(
                        width: 16,
                        height: 16,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.play_arrow_rounded, size: 18),
                label: Text(running ? 'Working' : 'Run all'),
              ),
            ],
          ),
          const SizedBox(height: 12),
          ClipRRect(
            borderRadius: BorderRadius.circular(999),
            child: LinearProgressIndicator(
              value: pct,
              minHeight: 6,
              backgroundColor: Colors.white,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            running
                ? 'Exercising the backend phase by phase…'
                : '$done of $total checks completed',
            style: theme.textTheme.bodySmall
                ?.copyWith(color: theme.colorScheme.onSurfaceVariant),
          ),
        ],
      ),
    );
  }
}

class _SectionHeader extends StatelessWidget {
  const _SectionHeader({required this.section});

  final _Section section;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Row(
      children: [
        Icon(section.icon, size: 18, color: AppTheme.purple),
        const SizedBox(width: 8),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                section.title,
                style: theme.textTheme.titleSmall
                    ?.copyWith(fontWeight: FontWeight.w800),
              ),
              Text(
                section.subtitle,
                style: theme.textTheme.bodySmall
                    ?.copyWith(color: theme.colorScheme.onSurfaceVariant),
              ),
            ],
          ),
        ),
      ],
    );
  }
}

class _CheckRow extends StatelessWidget {
  const _CheckRow({
    required this.check,
    required this.result,
    required this.disabled,
    required this.onTap,
  });

  final _Check check;
  final _Result result;
  final bool disabled;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return InkWell(
      onTap: onTap,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 11),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            SizedBox(width: 24, height: 24, child: _leading(theme)),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    check.label,
                    style: const TextStyle(fontWeight: FontWeight.w700),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    check.endpoint,
                    style: theme.textTheme.labelSmall?.copyWith(
                      fontFamily: 'monospace',
                      color: theme.colorScheme.onSurfaceVariant,
                    ),
                  ),
                  if (result.status == _Status.pass &&
                      result.detail.isNotEmpty) ...[
                    const SizedBox(height: 4),
                    Text(
                      result.detail,
                      style: theme.textTheme.bodySmall
                          ?.copyWith(color: AppTheme.green),
                    ),
                  ],
                  if (result.status == _Status.fail) ...[
                    const SizedBox(height: 4),
                    Text(
                      result.error,
                      maxLines: 3,
                      overflow: TextOverflow.ellipsis,
                      style: theme.textTheme.bodySmall
                          ?.copyWith(color: AppTheme.danger),
                    ),
                  ],
                ],
              ),
            ),
            const SizedBox(width: 8),
            _trailing(theme),
          ],
        ),
      ),
    );
  }

  Widget _leading(ThemeData theme) {
    switch (result.status) {
      case _Status.running:
        return const Padding(
          padding: EdgeInsets.all(3),
          child: CircularProgressIndicator(strokeWidth: 2),
        );
      case _Status.pass:
        return const Icon(Icons.check_circle, color: AppTheme.green, size: 22);
      case _Status.fail:
        return const Icon(Icons.cancel, color: AppTheme.danger, size: 22);
      case _Status.idle:
        return Icon(
          Icons.radio_button_unchecked,
          size: 20,
          color: theme.colorScheme.onSurfaceVariant,
        );
    }
  }

  Widget _trailing(ThemeData theme) {
    if (result.status == _Status.running) return const SizedBox.shrink();
    if (result.status == _Status.idle) {
      return Icon(
        Icons.chevron_right,
        size: 18,
        color: theme.colorScheme.onSurfaceVariant,
      );
    }
    return Text(
      '${result.ms} ms',
      style: theme.textTheme.labelSmall?.copyWith(
        color: theme.colorScheme.onSurfaceVariant,
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Check bodies. Each returns a one-line human summary or throws.
// ---------------------------------------------------------------------------

Future<String> _health(AppRepository repo) async {
  final ok = await repo.health();
  return ok ? 'Backend reachable' : 'Backend reported unhealthy';
}

Future<String> _verification(AppRepository repo) async {
  final info = await repo.verificationStatus();
  return '${info.verificationStatus.label} · role=${info.role.label}'
      '${info.socialAccessRequired ? ' · social gated' : ''}';
}

Future<String> _contacts(AppRepository repo) async {
  final items = await repo.listContacts();
  return '${items.length} trusted contact${items.length == 1 ? '' : 's'}';
}

Future<String> _discovery(AppRepository repo) async {
  final result = await repo.discovery();
  return '${result.profiles.length} profile${result.profiles.length == 1 ? '' : 's'} available';
}

Future<String> _candidates(AppRepository repo) async {
  final items = await repo.discover(limit: 10);
  if (items.isEmpty) {
    return '0 candidates (needs a verified profile and an active plan)';
  }
  return '${items.length} candidates, best score ${items.first.compatibilityScore}%';
}

Future<String> _blocks(AppRepository repo) async {
  final items = await repo.listBlocks();
  return '${items.length} blocked user${items.length == 1 ? '' : 's'}';
}

Future<String> _chatRequests(AppRepository repo) async {
  final items = await repo.listChatRequests(direction: 'incoming');
  return '${items.length} awaiting reply';
}

Future<String> _checkIns(AppRepository repo) async {
  final items = await repo.listCheckIns();
  return '${items.length} check-in${items.length == 1 ? '' : 's'}';
}

Future<String> _overdue(AppRepository repo) async {
  final items = await repo.listOverdueCheckIns();
  return items.isEmpty ? 'None overdue' : '${items.length} overdue';
}

Future<String> _sos(AppRepository repo) async {
  final items = await repo.listSosEvents();
  if (items.isEmpty) return '0 incidents';
  final active = items.where((e) => e.status.name == 'active').length;
  return '${items.length} incident${items.length == 1 ? '' : 's'}, $active active';
}

Future<String> _reports(AppRepository repo) async {
  final items = await repo.listReports(limit: 50);
  return '${items.length} report${items.length == 1 ? '' : 's'}';
}

Future<String> _meetups(AppRepository repo) async {
  final items = await repo.listMeetups();
  return '${items.length} public meetup${items.length == 1 ? '' : 's'} '
      '(house parties are excluded by design)';
}

Future<String> _invitations(AppRepository repo) async {
  final items = await repo.listInvitations();
  final pending = items.where((i) => i.isPending).length;
  return '${items.length} invitation${items.length == 1 ? '' : 's'}, $pending pending';
}

Future<String> _notifications(AppRepository repo) async {
  final items = await repo.listNotifications();
  return '${items.length} notification${items.length == 1 ? '' : 's'}';
}

Future<String> _tripShares(AppRepository repo) async {
  final out = await repo.listTripShares();
  final incoming = await repo.listSharedWithMe();
  return '${out.length} outgoing · ${incoming.length} shared with me';
}

Future<String> _ai(AppRepository repo) async {
  final status = await repo.aiStatus();
  return '${status.provider}${status.configured ? ' · configured' : ' · not configured'}';
}
