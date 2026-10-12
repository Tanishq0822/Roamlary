import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/app_theme.dart';
import '../core/format.dart';
import '../models/enums.dart';
import '../models/models.dart';
import '../state/app_state.dart';
import '../widgets/common.dart';
import 'checkins_screen.dart';
import 'sos_screen.dart';

/// Landing dashboard: greeting, quick safety actions, and summary cards.
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

  Future<_DashboardData> _load() async {
    final repo = context.read<AppState>().repo;
    final results = await Future.wait<Object?>([
      repo.listCheckIns(status: CheckInStatus.pending),
      repo.listSosEvents(),
      repo.listContacts(),
    ]);
    return _DashboardData(
      openCheckIns: results[0] as List<CheckIn>,
      sosEvents: results[1] as List<SosEvent>,
      contacts: results[2] as List<TrustedContact>,
    );
  }

  void _refresh() => setState(() => _future = _load());

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final profile = context.watch<AppState>().profile;

    return Scaffold(
      appBar: AppBar(
        title: Text('Hello, ${profile?.displayName ?? 'Traveller'}'),
        actions: [
          IconButton(
            tooltip: 'Refresh',
            onPressed: _refresh,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: FutureBuilder<_DashboardData>(
        future: _future,
        builder: (context, snapshot) {
          if (snapshot.connectionState != ConnectionState.done) {
            return const LoadingView(label: 'Loading your dashboard…');
          }
          if (snapshot.hasError) {
            return ErrorView(
              message: '${snapshot.error}',
              onRetry: _refresh,
            );
          }
          final data = snapshot.data!;
          return RefreshIndicator(
            onRefresh: () async => _refresh(),
            child: ListView(
              padding: const EdgeInsets.all(16),
              children: [
                _SosBanner(
                  activeCount:
                      data.sosEvents.where((e) => e.isActive).length,
                ),
                const SizedBox(height: 16),
                _QuickActions(onCheckInsOpened: _refresh),
                const SizedBox(height: 16),
                Row(
                  children: [
                    Expanded(
                      child: _StatCard(
                        icon: Icons.task_alt,
                        label: 'Open check-ins',
                        value: '${data.openCheckIns.length}',
                        color: theme.colorScheme.primary,
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
                        color: theme.colorScheme.tertiary,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 16),
                SectionCard(
                  title: 'Next check-in',
                  child: data.openCheckIns.isEmpty
                      ? Text(
                          'No open check-ins. Set one before you head out.',
                          style: theme.textTheme.bodyMedium?.copyWith(
                            color: theme.colorScheme.onSurfaceVariant,
                          ),
                        )
                      : _NextCheckInTile(checkIn: data.openCheckIns.first),
                ),
                const SizedBox(height: 16),
                SectionCard(
                  title: 'Recent SOS activity',
                  trailing: TextButton(
                    onPressed: () => Navigator.of(context).push(
                      MaterialPageRoute<void>(builder: (_) => const SosScreen()),
                    ),
                    child: const Text('Open'),
                  ),
                  child: data.sosEvents.isEmpty
                      ? Text(
                          'No SOS incidents recorded. Stay safe out there.',
                          style: theme.textTheme.bodyMedium?.copyWith(
                            color: theme.colorScheme.onSurfaceVariant,
                          ),
                        )
                      : _SosTile(event: data.sosEvents.first),
                ),
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
  });

  final List<CheckIn> openCheckIns;
  final List<SosEvent> sosEvents;
  final List<TrustedContact> contacts;
}

class _SosBanner extends StatelessWidget {
  const _SosBanner({required this.activeCount});

  final int activeCount;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final hasActive = activeCount > 0;
    final bg = hasActive ? AppTheme.danger : theme.colorScheme.primaryContainer;
    final fg = hasActive
        ? Colors.white
        : theme.colorScheme.onPrimaryContainer;

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(16),
      ),
      child: Row(
        children: [
          Icon(
            hasActive ? Icons.warning_amber_rounded : Icons.shield_outlined,
            color: fg,
            size: 32,
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  hasActive ? 'Active SOS: $activeCount' : 'You are protected',
                  style: theme.textTheme.titleMedium?.copyWith(
                    color: fg,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  hasActive
                      ? 'Open Safe Mode to manage or resolve.'
                      : 'Safe Mode and SOS are one tap away.',
                  style: theme.textTheme.bodySmall?.copyWith(color: fg),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _QuickActions extends StatelessWidget {
  const _QuickActions({required this.onCheckInsOpened});

  final VoidCallback onCheckInsOpened;

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
              onCheckInsOpened();
            },
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: _QuickAction(
            icon: Icons.crisis_alert,
            label: 'SOS',
            danger: true,
            onTap: () => Navigator.of(context).push(
              MaterialPageRoute<void>(builder: (_) => const SosScreen()),
            ),
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
    this.danger = false,
  });

  final IconData icon;
  final String label;
  final VoidCallback onTap;
  final bool danger;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final color = danger ? AppTheme.danger : theme.colorScheme.primary;
    return Material(
      color: color.withValues(alpha: 0.10),
      borderRadius: BorderRadius.circular(16),
      child: InkWell(
        borderRadius: BorderRadius.circular(16),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 20, horizontal: 12),
          child: Column(
            children: [
              Icon(icon, color: color, size: 28),
              const SizedBox(height: 8),
              Text(
                label,
                style: theme.textTheme.titleSmall?.copyWith(
                  color: color,
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
                style: theme.textTheme.headlineMedium?.copyWith(
                  fontWeight: FontWeight.w800,
                ),
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
      ],
    );
  }
}

class _SosTile extends StatelessWidget {
  const _SosTile({required this.event});

  final SosEvent event;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final (label, color) = switch (event.status) {
      SosStatus.active => ('ACTIVE', AppTheme.danger),
      SosStatus.resolved => ('Resolved', theme.colorScheme.primary),
      SosStatus.cancelled => ('Cancelled', theme.colorScheme.outline),
      _ => (event.status.name, theme.colorScheme.outline),
    };
    return Column(
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
          const SizedBox(height: 8),
          Text(event.description!, style: theme.textTheme.bodyMedium),
        ],
      ],
    );
  }
}
