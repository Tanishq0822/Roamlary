import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/app_theme.dart';
import '../core/format.dart';
import '../data/app_repository.dart';
import '../models/enums.dart';
import '../models/models.dart';
import '../state/app_state.dart';
import '../widgets/common.dart';
import 'chat_hub_screen.dart';
import 'checkins_screen.dart';
import 'meetups_screen.dart';
import 'sos_screen.dart';

/// Human label for an SOS status (the enum itself only carries the wire
/// value).
String _sosLabel(SosStatus status) => switch (status) {
      SosStatus.active => 'ACTIVE',
      SosStatus.acknowledged => 'Acknowledged',
      SosStatus.resolved => 'Resolved',
      SosStatus.falseAlarm => 'False alarm',
      SosStatus.cancelled => 'Cancelled',
    };

/// Human label for a report status — `ReportStatus` only carries the wire
/// value (no `label` field, unlike `ReportCategory`).
String _reportStatusLabel(ReportStatus status) => switch (status) {
      ReportStatus.pending => 'Under review',
      ReportStatus.approved => 'Approved',
      ReportStatus.rejected => 'Rejected',
    };

/// Landing dashboard.
///
/// Layout follows the product brief, top to bottom:
///  1. Company corner top-left (logo + wordmark), chats top-right.
///  2. A short description of what Roamlary is.
///  3. Live SOS workflow (when an incident is open) — acknowledge, contact
///     attempts, resolve/cancel — so SOS is usable without leaving Home.
///  4. Overdue + next check-ins, with real-time location sharing.
///  5. "Add connection": traveller suggestions with requirement filters.
///
/// The round SOS button itself lives in the bottom bar (see home_shell).
class HomeDashboard extends StatefulWidget {
  const HomeDashboard({super.key});

  @override
  State<HomeDashboard> createState() => _HomeDashboardState();
}

class _HomeDashboardState extends State<HomeDashboard> {
  late Future<_DashboardData> _future;

  @override
  void initState() {
    super.initState();
    _future = _load();
  }

  /// Every call is individually protected: the social endpoints fail closed
  /// for unverified accounts, and that must not take the whole page down.
  static Future<T> _safe<T>(Future<T> call, T fallback) async {
    try {
      return await call;
    } catch (_) {
      return fallback;
    }
  }

  Future<_DashboardData> _load() async {
    final repo = context.read<AppState>().repo;
    final openCheckIns = await _safe(
      repo.listCheckIns(status: CheckInStatus.pending),
      <CheckIn>[],
    );
    final sosEvents = await _safe(repo.listSosEvents(), <SosEvent>[]);
    final contacts = await _safe(repo.listContacts(), <TrustedContact>[]);
    final overdue = await _safe(repo.listOverdueCheckIns(), <CheckIn>[]);

    // Discovery fails closed (403) for unverified accounts — keep the
    // reason so the rail can explain the gate instead of showing "empty".
    List<DiscoveryCandidate> candidates = const [];
    var socialDenied = false;
    try {
      candidates = await repo.discover(limit: 6);
    } on SocialGateDeniedException {
      socialDenied = true;
    } catch (_) {
      // Offline/other error: show the empty state, don't fail the page.
    }

    final incomingRequests = await _safe(
      repo.listChatRequests(direction: 'incoming'),
      <Conversation>[],
    );

    // "Recent activity" (bottom card): four feeds merged and sorted newest
    // first. Each is independently protected so one failing feed cannot
    // blank the card, let alone the page.
    final reports = await _safe(repo.listReports(limit: 20), <CommunityReport>[]);
    final meetups = await _safe(repo.listMeetups(), <Meetup>[]);
    final invitations = await _safe(repo.listInvitations(), <Invitation>[]);
    final tripShares = await _safe(repo.listTripShares(), <TripShare>[]);
    final doneCheckIns = await _safe(
      repo.listCheckIns(status: CheckInStatus.safe),
      <CheckIn>[],
    );

    final activity = <_ActivityItem>[
      for (final r in reports)
        _ActivityItem(
          icon: Icons.report_gmailerrorred_outlined,
          color: AppTheme.danger,
          title: r.description,
          subtitle: '${r.category.label} report · '
              '${_reportStatusLabel(r.status)}',
          at: r.createdAt,
          pending: r.status == ReportStatus.pending,
        ),
      for (final m in meetups)
        _ActivityItem(
          icon: Icons.event_available_outlined,
          color: AppTheme.green,
          title: m.title,
          subtitle: m.kind == 'house_party'
              ? 'House party · ${m.hostDisplayName}'
              : 'Meetup · ${m.hostDisplayName}',
          at: m.startAt,
          pending: m.myMembership == MembershipStatus.approved,
        ),
      for (final i in invitations)
        _ActivityItem(
          icon: Icons.mail_outline,
          color: AppTheme.purple,
          title: i.eventTitle,
          subtitle: 'House-party invite · ${i.status.label}',
          at: i.createdAt,
          pending: i.isPending,
        ),
      for (final s in tripShares)
        _ActivityItem(
          icon: Icons.link_outlined,
          color: AppTheme.purple,
          title: s.planDestination ?? 'Itinerary link',
          subtitle: s.revokedAt != null ? 'Trip share · revoked' : 'Trip share · active',
          at: s.createdAt,
          pending: s.revokedAt == null,
        ),
      for (final c in doneCheckIns)
        _ActivityItem(
          icon: Icons.check_circle_outline,
          color: AppTheme.green,
          title: c.note ?? 'Check-in completed',
          subtitle: 'Check-in · completed',
          at: c.completedAt ?? c.createdAt,
          pending: false,
        ),
    ]..sort((a, b) => b.at.compareTo(a.at));

    return _DashboardData(
      openCheckIns: openCheckIns,
      sosEvents: sosEvents,
      contacts: contacts,
      overdue: overdue,
      candidates: candidates,
      incomingRequests: incomingRequests.length,
      socialDenied: socialDenied,
      activity: activity,
    );
  }

  // NOTE: block body, not `=>`. An arrow closure here would *return*
  // `_load()`'s Future to setState(), which Flutter rejects ("setState()
  // callback argument returned a Future").
  void _refresh() {
    setState(() {
      _future = _load();
    });
  }

  Future<void> _openChatHub() async {
    await Navigator.of(context).push(
      MaterialPageRoute<void>(builder: (_) => const ChatHubScreen()),
    );
    _refresh();
  }

  @override
  Widget build(BuildContext context) {
    final profile = context.watch<AppState>().profile;

    return Scaffold(
      // The brief puts the brand corner top-left and chats top-right, so the
      // dashboard brings its own header instead of a generic AppBar.
      body: FutureBuilder<_DashboardData>(
        future: _future,
        builder: (context, snapshot) {
          final data = snapshot.data;
          final loading = snapshot.connectionState != ConnectionState.done;

          return RefreshIndicator(
            onRefresh: () async => _refresh(),
            child: ListView(
              padding: const EdgeInsets.fromLTRB(16, 8, 16, 32),
              children: [
                _Header(
                  displayName: profile?.displayName,
                  chatBadge:
                      loading ? 0 : (data?.incomingRequests ?? 0),
                  onChats: _openChatHub,
                  onRefresh: _refresh,
                ),
                const SizedBox(height: 14),
                const _AboutCard(),
                if (loading) ...[
                  const SizedBox(height: 24),
                  const LoadingView(label: 'Loading your dashboard…'),
                ] else if (snapshot.hasError) ...[
                  const SizedBox(height: 16),
                  ErrorView(
                    message: '${snapshot.error}',
                    onRetry: _refresh,
                  ),
                ] else if (data != null) ...[
                  const SizedBox(height: 16),
                  _SosWorkflowCard(
                    events: data.sosEvents,
                    onChanged: _refresh,
                  ),
                  if (data.overdue.isNotEmpty) ...[
                    const SizedBox(height: 16),
                    _OverdueCard(items: data.overdue),
                  ],
                  const SizedBox(height: 16),
                  _QuickActions(onChanged: _refresh),
                  const SizedBox(height: 16),
                  Row(
                    children: [
                      Expanded(
                        child: _StatCard(
                          icon: Icons.task_alt,
                          label: 'Open check-ins',
                          value: '${data.openCheckIns.length}',
                          color: AppTheme.green,
                          onTap: () async {
                            await Navigator.of(context).push(
                              MaterialPageRoute<void>(
                                builder: (_) => const CheckInsScreen(),
                              ),
                            );
                            _refresh();
                          },
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: _StatCard(
                          icon: Icons.people,
                          label: 'Trusted contacts',
                          value: '${data.contacts.length}',
                          color: AppTheme.purple,
                          onTap: () {},
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 16),
                  SectionCard(
                    title: 'Next check-in',
                    trailing: TextButton(
                      onPressed: () async {
                        await Navigator.of(context).push(
                          MaterialPageRoute<void>(
                            builder: (_) => const CheckInsScreen(),
                          ),
                        );
                        _refresh();
                      },
                      child: const Text('All'),
                    ),
                    child: data.openCheckIns.isEmpty
                        ? Text(
                            'No open check-ins. Set one before you head out.',
                            style: Theme.of(context)
                                .textTheme
                                .bodyMedium
                                ?.copyWith(
                                  color: Theme.of(context)
                                      .colorScheme
                                      .onSurfaceVariant,
                                ),
                          )
                        : _NextCheckInTile(checkIn: data.openCheckIns.first),
                  ),
                  const SizedBox(height: 16),
                  _AddConnectionSection(
                    candidates: data.candidates,
                    socialDenied: data.socialDenied,
                    onChanged: _refresh,
                  ),
                  // Deliberately last: reports, meetups, invites, shares and
                  // finished check-ins merged into one newest-first feed.
                  const SizedBox(height: 16),
                  _RecentActivityCard(items: data.activity),
                ],
              ],
            ),
          );
        },
      ),
    );
  }
}

class _DashboardData {
  const _DashboardData({
    required this.openCheckIns,
    required this.sosEvents,
    required this.contacts,
    required this.overdue,
    required this.candidates,
    required this.incomingRequests,
    required this.socialDenied,
    required this.activity,
  });

  final List<CheckIn> openCheckIns;
  final List<SosEvent> sosEvents;
  final List<TrustedContact> contacts;
  final List<CheckIn> overdue;
  final List<DiscoveryCandidate> candidates;
  final int incomingRequests;
  final bool socialDenied;

  /// Reports, meetups, invitations, shares and completed check-ins merged
  /// and sorted newest first — rendered by the bottom activity card.
  final List<_ActivityItem> activity;
}

/// One row of the merged recent-activity feed.
class _ActivityItem {
  const _ActivityItem({
    required this.icon,
    required this.color,
    required this.title,
    required this.subtitle,
    required this.at,
    required this.pending,
  });

  final IconData icon;
  final Color color;
  final String title;
  final String subtitle;
  final DateTime at;
  final bool pending;
}

// ---------------------------------------------------------------------------
// Header: company corner + chats
// ---------------------------------------------------------------------------

class _Header extends StatelessWidget {
  const _Header({
    required this.displayName,
    required this.chatBadge,
    required this.onChats,
    required this.onRefresh,
  });

  final String? displayName;
  final int chatBadge;
  final VoidCallback onChats;
  final VoidCallback onRefresh;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Row(
      children: [
        // Company corner (top-left).
        Container(
          padding: const EdgeInsets.all(6),
          decoration: BoxDecoration(
            gradient: const LinearGradient(
              colors: [AppTheme.green, AppTheme.purple],
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
            ),
            borderRadius: BorderRadius.circular(14),
            boxShadow: [
              BoxShadow(
                color: AppTheme.green.withValues(alpha: 0.35),
                blurRadius: 12,
                offset: const Offset(0, 4),
              ),
            ],
          ),
          child: const Icon(Icons.explore, color: Colors.white, size: 24),
        ),
        const SizedBox(width: 10),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Roamlary',
                style: theme.textTheme.titleLarge?.copyWith(
                  fontWeight: FontWeight.w800,
                  letterSpacing: -0.4,
                ),
              ),
              Text(
                displayName == null
                    ? 'Travel safe'
                    : 'Hi, $displayName',
                style: theme.textTheme.bodySmall?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                ),
                overflow: TextOverflow.ellipsis,
              ),
            ],
          ),
        ),
        IconButton(
          tooltip: 'Refresh',
          onPressed: onRefresh,
          icon: const Icon(Icons.refresh),
        ),
        // Chats (top-right).
        Stack(
          clipBehavior: Clip.none,
          children: [
            IconButton(
              tooltip: 'Chats',
              onPressed: onChats,
              icon: const Icon(Icons.chat_bubble_outline, size: 26),
            ),
            if (chatBadge > 0)
              Positioned(
                right: 6,
                top: 6,
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1),
                  decoration: BoxDecoration(
                    color: AppTheme.purple,
                    borderRadius: BorderRadius.circular(999),
                    border: Border.all(color: theme.colorScheme.surface, width: 1.5),
                  ),
                  child: Text(
                    chatBadge > 9 ? '9+' : '$chatBadge',
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 10,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                ),
              ),
          ],
        ),
      ],
    );
  }
}

// ---------------------------------------------------------------------------
// "What is Roamlary" blurb
// ---------------------------------------------------------------------------

class _AboutCard extends StatelessWidget {
  const _AboutCard();

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [
            AppTheme.greenTint,
            AppTheme.purpleTint,
          ],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: AppTheme.lightGreen),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Your safety net, wherever you wander',
            style: theme.textTheme.titleMedium
                ?.copyWith(fontWeight: FontWeight.w800),
          ),
          const SizedBox(height: 6),
          Text(
            'Roamlary keeps you connected while you travel: scheduled '
            'check-ins with live location, one-tap SOS with contact relay, '
            'community hazard reports, and a verified network of fellow '
            'travellers to meet along the way.',
            style: theme.textTheme.bodyMedium?.copyWith(
              color: theme.colorScheme.onSurfaceVariant,
              height: 1.45,
            ),
          ),
          const SizedBox(height: 12),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: const [
              _Pill(icon: Icons.task_alt, label: 'Check-ins'),
              _Pill(icon: Icons.sos, label: 'SOS'),
              _Pill(icon: Icons.campaign_outlined, label: 'Reports'),
              _Pill(icon: Icons.handshake_outlined, label: 'Meetups'),
              _Pill(icon: Icons.share_outlined, label: 'Trip links'),
            ],
          ),
        ],
      ),
    );
  }
}

class _Pill extends StatelessWidget {
  const _Pill({required this.icon, required this.label});

  final IconData icon;
  final String label;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: theme.colorScheme.surface,
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: theme.dividerColor),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 14, color: AppTheme.green),
          const SizedBox(width: 5),
          Text(
            label,
            style: theme.textTheme.labelSmall?.copyWith(
              fontWeight: FontWeight.w700,
            ),
          ),
        ],
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// SOS workflow on the home page
// ---------------------------------------------------------------------------

/// The live incident: status, contact-attempt log, and the three legal
/// transitions (acknowledge / resolve / cancel). 409s (someone else already
/// moved the incident) surface as a snackbar plus an automatic refresh.
class _SosWorkflowCard extends StatefulWidget {
  const _SosWorkflowCard({required this.events, required this.onChanged});

  final List<SosEvent> events;
  final VoidCallback onChanged;

  @override
  State<_SosWorkflowCard> createState() => _SosWorkflowCardState();
}

class _SosWorkflowCardState extends State<_SosWorkflowCard> {
  bool _busy = false;
  List<AppNotification>? _attempts;
  bool _attemptsOpen = false;

  SosEvent? get _openEvent {
    for (final e in widget.events) {
      if (e.isOpen) return e;
    }
    return null;
  }

  Future<void> _act(
    String label,
    Future<SosEvent> Function(AppRepository repo) action,
  ) async {
    if (_busy) return;
    setState(() => _busy = true);
    final repo = context.read<AppState>().repo;
    try {
      await action(repo);
      widget.onChanged();
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text('$label failed: $e')));
        widget.onChanged();
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _toggleAttempts(SosEvent event) async {
    if (_attemptsOpen) {
      setState(() {
        _attemptsOpen = false;
        _attempts = null;
      });
      return;
    }
    setState(() => _attemptsOpen = true);
    try {
      final list = await context
          .read<AppState>()
          .repo
          .listSosNotifications(event.id);
      if (mounted) setState(() => _attempts = list);
    } catch (e) {
      if (mounted) setState(() => _attempts = []);
    }
  }

  Future<void> _retryContacts(SosEvent event) async {
    if (_busy) return;
    setState(() => _busy = true);
    try {
      final list = await context
          .read<AppState>()
          .repo
          .retrySosNotifications(event.id);
      if (mounted) {
        setState(() {
          _attempts = list;
          _attemptsOpen = true;
        });
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Re-sent to ${list.length} contact(s)')),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text('Retry failed: $e')));
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final event = _openEvent;
    final lastClosed = widget.events.isEmpty
        ? null
        : widget.events.firstWhere((e) => !e.isOpen, orElse: () => widget.events.first);

    if (event == null && lastClosed == null) return const SizedBox.shrink();

    if (event == null) {
      // No open incident — a calm confirmation + history entry.
      return SectionCard(
        title: 'SOS status',
        child: Row(
          children: [
            const Icon(Icons.shield_outlined, color: AppTheme.green),
            const SizedBox(width: 10),
            Expanded(
              child: Text(
                'No open incidents. Last: ${_sosLabel(lastClosed!.status)} '
                '${relativeLabel(lastClosed.updatedAt)}.',
                style: theme.textTheme.bodyMedium,
              ),
            ),
            TextButton(
              onPressed: () => Navigator.of(context).push(
                MaterialPageRoute<void>(builder: (_) => const SosScreen()),
              ),
              child: const Text('History'),
            ),
          ],
        ),
      );
    }

    final (statusLabel, statusColor) = switch (event.status) {
      SosStatus.active => ('ACTIVE SOS', AppTheme.danger),
      SosStatus.acknowledged => ('Acknowledged', Colors.orange.shade800),
      SosStatus.resolved => ('Resolved', AppTheme.green),
      SosStatus.falseAlarm => ('False alarm', Colors.grey),
      SosStatus.cancelled => ('Cancelled', Colors.grey),
    };

    return Container(
      decoration: BoxDecoration(
        color: AppTheme.danger.withValues(alpha: 0.06),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: AppTheme.danger.withValues(alpha: 0.45)),
      ),
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.warning_amber_rounded, color: AppTheme.danger),
              const SizedBox(width: 8),
              StatusPill(label: statusLabel, color: statusColor),
              const Spacer(),
              Text(
                'raised ${relativeLabel(event.createdAt)}',
                style: theme.textTheme.labelSmall
                    ?.copyWith(color: theme.colorScheme.onSurfaceVariant),
              ),
            ],
          ),
          const SizedBox(height: 10),
          if (event.description != null) ...[
            Text(event.description!, style: theme.textTheme.bodyMedium),
            const SizedBox(height: 8),
          ],
          if (event.latitude != null && event.longitude != null)
            _LocationLine(lat: event.latitude!, lng: event.longitude!)
          else
            Text(
              'No location attached (it was off when you raised the SOS).',
              style: theme.textTheme.bodySmall
                  ?.copyWith(color: theme.colorScheme.onSurfaceVariant),
            ),
          const SizedBox(height: 12),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              if (event.status == SosStatus.active)
                FilledButton.icon(
                  style: FilledButton.styleFrom(
                      backgroundColor: Colors.orange.shade800),
                  onPressed:
                      _busy ? null : () => _act('Acknowledge', (r) => r.acknowledgeSos(event.id)),
                  icon: const Icon(Icons.visibility_outlined, size: 18),
                  label: const Text('Acknowledge'),
                ),
              FilledButton.icon(
                style:
                    FilledButton.styleFrom(backgroundColor: AppTheme.green),
                onPressed:
                    _busy ? null : () => _act('Resolve', (r) => r.resolveSos(event.id)),
                icon: const Icon(Icons.check_circle_outline, size: 18),
                label: const Text('I am safe'),
              ),
              OutlinedButton.icon(
                style: OutlinedButton.styleFrom(
                    foregroundColor: AppTheme.danger),
                onPressed:
                    _busy ? null : () => _act('Cancel', (r) => r.cancelSos(event.id)),
                icon: const Icon(Icons.close, size: 18),
                label: const Text('Cancel incident'),
              ),
              OutlinedButton.icon(
                onPressed: _busy ? null : () => _retryContacts(event),
                icon: const Icon(Icons.cached, size: 18),
                label: const Text('Re-notify contacts'),
              ),
              TextButton.icon(
                onPressed: () => _toggleAttempts(event),
                icon: Icon(
                  _attemptsOpen
                      ? Icons.keyboard_arrow_up
                      : Icons.keyboard_arrow_down,
                  size: 18,
                ),
                label: Text(_attemptsOpen
                    ? 'Hide contact log'
                    : 'Contact attempts'),
              ),
            ],
          ),
          if (_attemptsOpen) ...[
            const SizedBox(height: 8),
            if (_attempts == null)
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
            else if (_attempts!.isEmpty)
              Text(
                'No relay attempts recorded yet.',
                style: theme.textTheme.bodySmall,
              )
            else
              for (final a in _attempts!) _AttemptRow(item: a),
          ],
        ],
      ),
    );
  }
}

class _AttemptRow extends StatelessWidget {
  const _AttemptRow({required this.item});

  final AppNotification item;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final (label, color) = switch (item.status) {
      NotificationStatus.delivered => ('delivered', AppTheme.green),
      NotificationStatus.failed => ('failed', AppTheme.danger),
      NotificationStatus.unavailable => ('unavailable', Colors.grey),
      _ => (item.status.wire, Colors.orange.shade800),
    };
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 3),
      child: Row(
        children: [
          Icon(Icons.circle, size: 8, color: color),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              '${item.channel}: ${item.body}',
              style: theme.textTheme.bodySmall,
              overflow: TextOverflow.ellipsis,
            ),
          ),
          const SizedBox(width: 8),
          Text(
            '$label · ${item.attempts}×',
            style: theme.textTheme.labelSmall?.copyWith(color: color),
          ),
        ],
      ),
    );
  }
}

/// Coordinates rendered as a tappable maps deep-link.
class _LocationLine extends StatelessWidget {
  const _LocationLine({required this.lat, required this.lng});

  final double lat;
  final double lng;

  @override
  Widget build(BuildContext context) {
    final url = 'https://maps.google.com/?q=$lat,$lng';
    return InkWell(
      onTap: () => ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Open in browser: $url')),
      ),
      child: Row(
        children: [
          const Icon(Icons.place, size: 16, color: AppTheme.danger),
          const SizedBox(width: 6),
          Expanded(
            child: Text(
              '${lat.toStringAsFixed(4)}, ${lng.toStringAsFixed(4)} — tap '
              'for map',
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: AppTheme.danger,
                    fontWeight: FontWeight.w600,
                  ),
            ),
          ),
        ],
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Overdue check-ins
// ---------------------------------------------------------------------------

class _OverdueCard extends StatelessWidget {
  const _OverdueCard({required this.items});

  final List<CheckIn> items;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Container(
      decoration: BoxDecoration(
        color: Colors.orange.shade50,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: Colors.orange.shade400),
      ),
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.timer_off_outlined, color: Colors.orange.shade800),
              const SizedBox(width: 8),
              Text(
                '${items.length} check-in${items.length == 1 ? '' : 's'} '
                'overdue',
                style: theme.textTheme.titleSmall?.copyWith(
                  fontWeight: FontWeight.w800,
                  color: Colors.orange.shade900,
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          for (final c in items.take(3)) ...[
            Text(
              '• ${c.note ?? 'Untitled check-in'} — was due '
              '${c.dueAt == null ? '' : relativeLabel(c.dueAt!)}',
              style: theme.textTheme.bodySmall
                  ?.copyWith(color: Colors.orange.shade900),
            ),
          ],
          const SizedBox(height: 8),
          Align(
            alignment: Alignment.centerRight,
            child: FilledButton(
              style: FilledButton.styleFrom(
                  backgroundColor: Colors.orange.shade800),
              onPressed: () => Navigator.of(context).push(
                MaterialPageRoute<void>(builder: (_) => const CheckInsScreen()),
              ),
              child: const Text('Answer now'),
            ),
          ),
        ],
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Quick actions
// ---------------------------------------------------------------------------

class _QuickActions extends StatelessWidget {
  const _QuickActions({required this.onChanged});

  final VoidCallback onChanged;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: _QuickAction(
            icon: Icons.add_task,
            label: 'Check-in',
            onTap: () async {
              await Navigator.of(context).push(
                MaterialPageRoute<void>(builder: (_) => const CheckInsScreen()),
              );
              onChanged();
            },
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: _QuickAction(
            icon: Icons.event_outlined,
            label: 'Meetups',
            onTap: () => Navigator.of(context).push(
              MaterialPageRoute<void>(builder: (_) => const MeetupsScreen()),
            ),
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: _QuickAction(
            icon: Icons.campaign_outlined,
            label: 'Reports',
            onTap: () => onChanged(),
          ),
        ),
      ],
    );
  }
}

class _QuickAction extends StatelessWidget {
  const _QuickAction({
    required this.icon,
    required this.label,
    required this.onTap,
  });

  final IconData icon;
  final String label;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Material(
      color: AppTheme.greenTint,
      borderRadius: BorderRadius.circular(16),
      child: InkWell(
        borderRadius: BorderRadius.circular(16),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 16, horizontal: 8),
          child: Column(
            children: [
              Icon(icon, color: AppTheme.green, size: 26),
              const SizedBox(height: 8),
              Text(
                label,
                style: theme.textTheme.titleSmall?.copyWith(
                  color: AppTheme.green,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _StatCard extends StatelessWidget {
  const _StatCard({
    required this.icon,
    required this.label,
    required this.value,
    required this.color,
    this.onTap,
  });

  final IconData icon;
  final String label;
  final String value;
  final Color color;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Card(
      child: InkWell(
        borderRadius: BorderRadius.circular(16),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(icon, color: color),
              const SizedBox(height: 12),
              Text(
                value,
                style: theme.textTheme.headlineMedium
                    ?.copyWith(fontWeight: FontWeight.w800),
              ),
              const SizedBox(height: 2),
              Text(
                label,
                style: theme.textTheme.bodySmall?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _NextCheckInTile extends StatelessWidget {
  const _NextCheckInTile({required this.checkIn});

  final CheckIn checkIn;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final hasLocation = checkIn.location != null;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (checkIn.note != null) ...[
          Text(checkIn.note!, style: theme.textTheme.bodyLarge),
          const SizedBox(height: 6),
        ],
        Row(
          children: [
            const Icon(Icons.schedule, size: 16),
            const SizedBox(width: 6),
            Expanded(
              child: Text(
                checkIn.dueAt == null
                    ? 'No deadline set'
                    : 'Due ${formatDateTime(checkIn.dueAt!)} '
                        '(${relativeLabel(checkIn.dueAt!)})',
                style: theme.textTheme.bodySmall,
              ),
            ),
          ],
        ),
        if (hasLocation) ...[
          const SizedBox(height: 6),
          _LocationLine(
            lat: checkIn.location!.lat,
            lng: checkIn.location!.lng,
          ),
        ],
      ],
    );
  }
}

// ---------------------------------------------------------------------------
// Add connection (suggestions + filter)
// ---------------------------------------------------------------------------

class _AddConnectionSection extends StatefulWidget {
  const _AddConnectionSection({
    required this.candidates,
    required this.socialDenied,
    required this.onChanged,
  });

  final List<DiscoveryCandidate> candidates;
  final bool socialDenied;
  final VoidCallback onChanged;

  @override
  State<_AddConnectionSection> createState() => _AddConnectionSectionState();
}

class _AddConnectionSectionState extends State<_AddConnectionSection> {
  bool _busy = false;
  ConnectionFilter? _filter;
  List<DiscoveryCandidate>? _filtered;
  bool _filteredLoading = false;

  /// Chat requests sent in this session.
  ///
  /// The backend's `existing_request` is derived only from TRAVEL-PARTNER
  /// (buddy) requests (`_request_states` in discovery.py never queries
  /// `conversations`), so a chat request sent from this card can never flip
  /// that field. We remember it here so the button flips to "Request sent"
  /// immediately instead of silently reverting on refresh.
  final Set<String> _sentChatTo = {};

  /// Users that answered 409 "already have an accepted conversation".
  final Set<String> _alreadyConnected = {};

  /// Users blocked this session — hidden from the rail immediately.
  final Set<String> _blocked = {};

  /// Local override for one candidate, or null when the server value stands.
  String? localStateFor(DiscoveryCandidate c) {
    if (_alreadyConnected.contains(c.userId)) return 'accepted';
    if (_sentChatTo.contains(c.userId)) return 'pending_sent';
    return null;
  }

  Future<void> _block(DiscoveryCandidate c) async {
    if (_busy) return;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: Text('Block ${c.displayName}?'),
        content: const Text(
            'They will no longer appear in your suggestions and cannot '
            'contact you. You can undo this from More → Blocked users.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            style: FilledButton.styleFrom(backgroundColor: AppTheme.danger),
            onPressed: () => Navigator.of(dialogContext).pop(true),
            child: const Text('Block'),
          ),
        ],
      ),
    );
    if (confirmed != true || !mounted) return;

    setState(() => _busy = true);
    try {
      await context.read<AppState>().repo.blockUser(c.userId);
      if (!mounted) return;
      setState(() => _blocked.add(c.userId));
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('${c.displayName} has been blocked.')),
      );
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text('$e')));
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  /// Drops blocked users from a candidate list.
  List<DiscoveryCandidate> _visible(List<DiscoveryCandidate> items) =>
      _blocked.isEmpty
          ? items
          : items.where((c) => !_blocked.contains(c.userId)).toList();

  Future<void> _connect(DiscoveryCandidate c) async {
    if (_busy) return;
    setState(() => _busy = true);
    try {
      await context.read<AppState>().repo.sendChatRequest(recipientId: c.userId);
      if (!mounted) return;
      setState(() => _sentChatTo.add(c.userId));
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Request sent to ${c.displayName}')),
      );
      // Refresh the chat badge on the header — but never re-fetch this
      // rail, since that would wipe the local state above.
      widget.onChanged();
    } catch (e) {
      if (!mounted) return;
      final message = '$e';
      if (message.contains('409') || message.toLowerCase().contains('already')) {
        // Already connected (or a request is already pending) — reflect it
        // rather than showing a raw HTTP error.
        setState(() => _alreadyConnected.add(c.userId));
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
              content: Text('You and ${c.displayName} are already '
                  'connected.')),
        );
      } else {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(message)));
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _openFilter() async {
    final repo = context.read<AppState>().repo;
    final result = await showModalBottomSheet<ConnectionFilter?>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (_) => const _ConnectionFilterSheet(),
    );
    if (result == null) {
      // "Clear" — back to the unfiltered suggestion list.
      setState(() {
        _filter = null;
        _filtered = null;
      });
      return;
    }
    setState(() {
      _filter = result;
      _filtered = null;
      _filteredLoading = true;
    });
    try {
      final items = await repo.discoverFiltered(
            destination: result.destination,
            travelStyle: result.travelStyle,
            language: result.language,
            interests: result.interests,
            minScore: result.minScore,
          );
      if (mounted) setState(() => _filtered = items);
    } catch (e) {
      if (mounted) {
        setState(() => _filtered = []);
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text('$e')));
      }
    } finally {
      if (mounted) setState(() => _filteredLoading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final filterActive = _filter != null && !_filter!.isEmpty;
    final shown = _visible(filterActive
        ? (_filtered ?? const <DiscoveryCandidate>[])
        : widget.candidates);

    return SectionCard(
      title: 'Add connection',
      trailing: TextButton.icon(
        onPressed: _openFilter,
        icon: const Icon(Icons.tune, size: 18),
        label: Text(filterActive ? 'Filtered' : 'Filter'),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            filterActive
                ? 'Showing travellers that fit your requirements.'
                : 'Travellers matching your route, style and interests.',
            style: theme.textTheme.bodySmall
                ?.copyWith(color: theme.colorScheme.onSurfaceVariant),
          ),
          const SizedBox(height: 12),
          if (widget.socialDenied)
            Container(
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: AppTheme.purpleTint,
                borderRadius: BorderRadius.circular(14),
              ),
              child: Row(
                children: [
                  const Icon(Icons.lock_outline,
                      size: 20, color: AppTheme.purple),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      'Verify your identity to see traveller suggestions — '
                      'it keeps this feed free of bots and scammers.',
                      style: theme.textTheme.bodySmall,
                    ),
                  ),
                ],
              ),
            )
          else if (_filteredLoading)
            const Padding(
              padding: EdgeInsets.all(20),
              child: Center(child: CircularProgressIndicator()),
            )
          else if (shown.isEmpty)
            Text(
              filterActive
                  ? 'Nobody matches those requirements yet — try widening '
                      'your filters.'
                  : 'No suggestions right now. Add a travel plan or widen '
                      'your filters.',
              style: theme.textTheme.bodyMedium?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            )
          else
            SizedBox(
              height: 230,
              child: ListView.separated(
                scrollDirection: Axis.horizontal,
                itemCount: shown.length,
                separatorBuilder: (_, _) => const SizedBox(width: 12),
                itemBuilder: (context, i) => _CandidateCard(
                  candidate: shown[i],
                  busy: _busy,
                  localState: localStateFor(shown[i]),
                  onConnect: () => _connect(shown[i]),
                  onBlock: () => _block(shown[i]),
                ),
              ),
            ),
        ],
      ),
    );
  }
}

/// Merged "recent activity" feed — reports, meetups, house-party invites,
/// trip shares and completed check-ins in one newest-first list. Sits at the
/// very bottom of the dashboard.
class _RecentActivityCard extends StatelessWidget {
  const _RecentActivityCard({required this.items});

  final List<_ActivityItem> items;

  static const int _visible = 8;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    if (items.isEmpty) {
      return SectionCard(
        title: 'Recent activity',
        child: Text(
          'Nothing yet — file a report, join a meetup or finish a check-in '
          'and it will show up here.',
          style: theme.textTheme.bodyMedium?.copyWith(
            color: theme.colorScheme.onSurfaceVariant,
          ),
        ),
      );
    }

    final shown = items.take(_visible).toList();

    return SectionCard(
      title: 'Recent activity',
      trailing: TextButton(
        onPressed: items.length <= _visible
            ? null
            : () => ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(
                    content: Text(
                      'Showing the ${shown.length} most recent of '
                      '${items.length} items.',
                    ),
                  ),
                ),
        child: Text('${items.length} total'),
      ),
      child: Column(
        children: [
          for (var i = 0; i < shown.length; i++) ...[
            if (i > 0) const Divider(height: 14),
            _ActivityTile(item: shown[i]),
          ],
        ],
      ),
    );
  }
}

class _ActivityTile extends StatelessWidget {
  const _ActivityTile({required this.item});

  final _ActivityItem item;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Container(
          width: 34,
          height: 34,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: item.color.withValues(alpha: 0.13),
          ),
          child: Icon(item.icon, size: 18, color: item.color),
        ),
        const SizedBox(width: 11),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                item.title,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(fontWeight: FontWeight.w700),
              ),
              const SizedBox(height: 2),
              Text(
                item.subtitle,
                style: theme.textTheme.bodySmall?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                ),
              ),
            ],
          ),
        ),
        const SizedBox(width: 8),
        Column(
          crossAxisAlignment: CrossAxisAlignment.end,
          children: [
            Text(
              _relative(item.at),
              style: theme.textTheme.labelSmall?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
            if (item.pending) ...[
              const SizedBox(height: 4),
              Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
                decoration: BoxDecoration(
                  color: item.color.withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(999),
                ),
                child: Text(
                  'Open',
                  style: TextStyle(
                    fontSize: 10,
                    fontWeight: FontWeight.w800,
                    color: item.color,
                  ),
                ),
              ),
            ],
          ],
        ),
      ],
    );
  }

  static String _relative(DateTime at) {
    final diff = DateTime.now().toUtc().difference(at.toUtc());
    if (diff.inMinutes < 1) return 'now';
    if (diff.inMinutes < 60) return '${diff.inMinutes}m ago';
    if (diff.inHours < 24) return '${diff.inHours}h ago';
    if (diff.inDays < 7) return '${diff.inDays}d ago';
    return formatDateTime(at);
  }
}

class _CandidateCard extends StatelessWidget {
  const _CandidateCard({
    required this.candidate,
    required this.busy,
    required this.onConnect,
    this.onBlock,
    this.localState,
  });

  final DiscoveryCandidate candidate;
  final bool busy;
  final VoidCallback onConnect;
  final VoidCallback? onBlock;

  /// Session-local override of [DiscoveryCandidate.existingRequest] — the
  /// backend derives that field only from buddy requests, so chat requests
  /// need remembering client-side (see localStateFor above).
  final String? localState;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    // Local session state wins: it reflects chat requests the server does
    // not fold into this field.
    final state = localState ?? candidate.existingRequest;
    final sent = state == 'pending_sent';
    final received = state == 'pending_received';
    final accepted = state == 'accepted';

    return Container(
      width: 220,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: theme.dividerColor),
        color: theme.colorScheme.surface,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              CircleAvatar(
                backgroundColor: AppTheme.purple.withValues(alpha: 0.15),
                child: Text(
                  candidate.displayName.characters.first.toUpperCase(),
                  style: const TextStyle(
                      color: AppTheme.purple, fontWeight: FontWeight.w800),
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      candidate.displayName,
                      style: theme.textTheme.titleSmall
                          ?.copyWith(fontWeight: FontWeight.w800),
                      overflow: TextOverflow.ellipsis,
                    ),
                    Text(
                      candidate.destination.isEmpty
                          ? (candidate.homeRegion ?? '')
                          : '→ ${candidate.destination}',
                      style: theme.textTheme.labelSmall
                          ?.copyWith(color: AppTheme.green),
                      overflow: TextOverflow.ellipsis,
                    ),
                  ],
                ),
              ),
              _ScoreBadge(score: candidate.compatibilityScore),
              if (onBlock != null)
                PopupMenuButton<String>(
                  tooltip: 'More',
                  padding: EdgeInsets.zero,
                  icon: const Icon(Icons.more_vert, size: 18),
                  onSelected: (v) {
                    if (v == 'block') onBlock!();
                  },
                  itemBuilder: (_) => [
                    const PopupMenuItem(
                      value: 'block',
                      child: Row(
                        children: [
                          Icon(Icons.block, size: 18, color: AppTheme.danger),
                          SizedBox(width: 10),
                          Text('Block user'),
                        ],
                      ),
                    ),
                  ],
                ),
            ],
          ),
          const SizedBox(height: 8),
          if (candidate.bio != null)
            Text(
              candidate.bio!,
              style: theme.textTheme.bodySmall,
              maxLines: 3,
              overflow: TextOverflow.ellipsis,
            ),
          const Spacer(),
          Wrap(
            spacing: 6,
            runSpacing: 6,
            children: [
              for (final s in (candidate.travelStyles ?? []).take(2))
                _Tag(text: s),
              for (final l in (candidate.languages ?? []).take(1)) _Tag(text: l),
            ],
          ),
          const SizedBox(height: 10),
          SizedBox(
            width: double.infinity,
            child: accepted
                ? const OutlinedButton(
                    onPressed: null, child: Text('Connected'))
                : received
                    ? FilledButton(
                        onPressed: busy ? null : onConnect,
                        child: const Text('Accept request'),
                      )
                    : FilledButton.icon(
                        onPressed: busy || sent ? null : onConnect,
                        icon: Icon(
                          sent ? Icons.check : Icons.person_add_alt,
                          size: 18,
                        ),
                        label: Text(sent ? 'Request sent' : 'Connect'),
                      ),
          ),
        ],
      ),
    );
  }
}

class _ScoreBadge extends StatelessWidget {
  const _ScoreBadge({required this.score});

  final int score;

  @override
  Widget build(BuildContext context) {
    final color = score >= 75
        ? AppTheme.green
        : score >= 50
            ? Colors.orange.shade800
            : Colors.grey;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.14),
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(
        '$score%',
        style: TextStyle(color: color, fontSize: 12, fontWeight: FontWeight.w800),
      ),
    );
  }
}

class _Tag extends StatelessWidget {
  const _Tag({required this.text});

  final String text;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: AppTheme.greenTint,
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(
        text,
        style: const TextStyle(
          fontSize: 10.5,
          fontWeight: FontWeight.w700,
          color: AppTheme.green,
        ),
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Connection filter sheet
// ---------------------------------------------------------------------------

/// Requirement filter for the "Add connection" rail. State is app-local
/// (returned as `true` when anything changed) so the sheet stays a pure UI
/// concern; the repository takes the same params the backend documents.
class _ConnectionFilterSheet extends StatefulWidget {
  const _ConnectionFilterSheet();

  @override
  State<_ConnectionFilterSheet> createState() => _ConnectionFilterSheetState();
}

/// The user's "personal requirement" for finding travellers. Returned by the
/// filter sheet and applied via `discoverFiltered` (or locally in mock mode).
class ConnectionFilter {
  const ConnectionFilter({
    this.destination,
    this.travelStyle,
    this.language,
    this.interests = const [],
    this.minScore = 0,
  });

  final String? destination;
  final String? travelStyle;
  final String? language;
  final List<String> interests;
  final int minScore;

  bool get isEmpty =>
      (destination == null ||
          destination!.isEmpty) &&
      travelStyle == null &&
      language == null &&
      interests.isEmpty &&
      minScore == 0;
}

class _ConnectionFilterSheetState extends State<_ConnectionFilterSheet> {
  static const _styles = [
    'backpacker',
    'solo',
    'slow_travel',
    'cultural',
    'road_trip',
    'adventure',
    'luxury',
    'family',
  ];
  static const _languages = [
    'English',
    'Hindi',
    'Spanish',
    'French',
    'Japanese',
    'German',
  ];
  static const _interestOptions = [
    'hiking',
    'food',
    'photography',
    'history',
    'museums',
    'wildlife',
    'nightlife',
    'beaches',
  ];

  String? _style;
  String? _language;
  final Set<String> _pickedInterests = {};
  int _minScore = 50;
  String _destination = '';

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
            Text('Filter travellers', style: theme.textTheme.titleLarge),
            const SizedBox(height: 4),
            Text(
              'Only show people who fit your plan.',
              style: theme.textTheme.bodySmall
                  ?.copyWith(color: theme.colorScheme.onSurfaceVariant),
            ),
            const SizedBox(height: 16),
            TextField(
              decoration: const InputDecoration(
                labelText: 'Destination',
                hintText: 'e.g. Manali',
                prefixIcon: Icon(Icons.place_outlined),
                border: OutlineInputBorder(),
              ),
              onChanged: (v) => _destination = v.trim(),
            ),
            const SizedBox(height: 12),
            DropdownButtonFormField<String?>(
              initialValue: _style,
              decoration: const InputDecoration(
                labelText: 'Travel style',
                border: OutlineInputBorder(),
              ),
              items: [
                const DropdownMenuItem<String?>(
                    value: null, child: Text('Any style')),
                for (final s in _styles)
                  DropdownMenuItem<String?>(
                      value: s, child: Text(s.replaceAll('_', ' '))),
              ],
              onChanged: (v) => setState(() => _style = v),
            ),
            const SizedBox(height: 12),
            DropdownButtonFormField<String?>(
              initialValue: _language,
              decoration: const InputDecoration(
                labelText: 'Language',
                border: OutlineInputBorder(),
              ),
              items: [
                const DropdownMenuItem<String?>(
                    value: null, child: Text('Any language')),
                for (final l in _languages)
                  DropdownMenuItem<String?>(value: l, child: Text(l)),
              ],
              onChanged: (v) => setState(() => _language = v),
            ),
            const SizedBox(height: 18),
            Text(
              'Minimum match: $_minScore%',
              style: theme.textTheme.titleSmall
                  ?.copyWith(fontWeight: FontWeight.w700),
            ),
            Slider(
              value: _minScore.toDouble(),
              min: 0,
              max: 100,
              divisions: 10,
              label: '$_minScore%',
              onChanged: (v) => setState(() => _minScore = v.round()),
            ),
            const SizedBox(height: 4),
            Text(
              'Shared interests',
              style: theme.textTheme.titleSmall
                  ?.copyWith(fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                for (final interest in _interestOptions)
                  FilterChip(
                    label: Text(interest),
                    selected: _pickedInterests.contains(interest),
                    onSelected: (v) => setState(() {
                      if (v) {
                        _pickedInterests.add(interest);
                      } else {
                        _pickedInterests.remove(interest);
                      }
                    }),
                  ),
              ],
            ),
            const SizedBox(height: 20),
            Row(
              children: [
                Expanded(
                  child: TextButton(
                    onPressed: () => Navigator.of(context).pop(null),
                    child: const Text('Clear'),
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  flex: 2,
                  child: FilledButton(
                    onPressed: () => Navigator.of(context).pop(ConnectionFilter(
                          destination:
                              _destination.isEmpty ? null : _destination,
                          travelStyle: _style,
                          language: _language,
                          interests: _pickedInterests.toList(),
                          minScore: _minScore,
                        )),
                    child: const Text('Apply filters'),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
