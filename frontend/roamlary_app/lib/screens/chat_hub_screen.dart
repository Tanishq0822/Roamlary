import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/app_theme.dart';
import '../data/app_repository.dart';
import '../models/enums.dart';
import '../models/models.dart';
import '../state/app_state.dart';
import '../widgets/common.dart';
import 'chat_thread_screen.dart';
import 'chat_screen.dart';

/// Social hub: talk to other travellers.
///
/// Three tabs backed by the Phase 7/8 backend:
///  * Chats     — accepted conversations, tap to open the thread
///  * Requests  — incoming/outgoing message requests + buddy requests
///  * Discover  — verified travellers with a compatibility score; send a
///                message request or a travel-buddy request
///
/// The AI companion (previous owner of this nav slot) is reachable from the
/// app bar so nothing is lost.
class ChatHubScreen extends StatefulWidget {
  const ChatHubScreen({super.key});

  @override
  State<ChatHubScreen> createState() => _ChatHubScreenState();
}

class _ChatHubScreenState extends State<ChatHubScreen>
    with SingleTickerProviderStateMixin {
  late final TabController _tabs = TabController(length: 3, vsync: this);

  int get _requestCount => _incoming.length;

  List<Conversation> _incoming = const [];
  List<Conversation> _conversations = const [];
  bool _loading = true;
  Object? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _tabs.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    final repo = context.read<AppState>().repo;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final results = await Future.wait<Object?>([
        repo.listConversations(),
        repo.listChatRequests(direction: 'incoming'),
      ]);
      if (!mounted) return;
      setState(() {
        _conversations = results[0]! as List<Conversation>;
        // direction=incoming includes ACCEPTED rows too (the ask was still
        // "incoming" when it was accepted) — the requests tab only wants
        // ones still awaiting an answer.
        _incoming = (results[1]! as List<Conversation>)
            .where((c) => c.status == ConversationStatus.pending)
            .toList();
        _loading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = e;
        _loading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Connect'),
        actions: [
          IconButton(
            tooltip: 'AI companion',
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute<void>(builder: (_) => const ChatScreen()),
            ),
            icon: const Icon(Icons.auto_awesome_outlined),
          ),
        ],
        bottom: TabBar(
          controller: _tabs,
          labelColor: AppTheme.green,
          unselectedLabelColor: theme.colorScheme.onSurfaceVariant,
          indicatorColor: AppTheme.green,
          indicatorWeight: 3,
          indicatorSize: TabBarIndicatorSize.label,
          tabs: [
            const Tab(text: 'Chats'),
            Tab(
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Text('Requests'),
                  if (_requestCount > 0) ...[
                    const SizedBox(width: 6),
                    _Badge(count: _requestCount),
                  ],
                ],
              ),
            ),
            const Tab(text: 'Discover'),
          ],
        ),
      ),
      body: _loading
          ? const LoadingView(label: 'Loading your network…')
          : _error != null
              ? ErrorView(message: '$_error', onRetry: _load)
              : TabBarView(
                  controller: _tabs,
                  children: [
                    _ChatsTab(conversations: _conversations, onChanged: _load),
                    _RequestsTab(onChanged: _load),
                    const _DiscoverTab(),
                  ],
                ),
    );
  }
}

/// Small count pill for the Requests tab.
class _Badge extends StatelessWidget {
  const _Badge({required this.count});

  final int count;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1),
      decoration: BoxDecoration(
        color: AppTheme.purple,
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(
        '$count',
        style: const TextStyle(
          color: Colors.white,
          fontSize: 11,
          fontWeight: FontWeight.w700,
        ),
      ),
    );
  }
}

/// Circular initial avatar — green/purple brand gradient.
class Avatar extends StatelessWidget {
  const Avatar({super.key, required this.name, this.size = 44});

  final String name;
  final double size;

  @override
  Widget build(BuildContext context) {
    final initials = name
        .trim()
        .split(RegExp(r'\s+'))
        .where((w) => w.isNotEmpty)
        .take(2)
        .map((w) => w[0].toUpperCase())
        .join();
    return Container(
      width: size,
      height: size,
      alignment: Alignment.center,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        gradient: const LinearGradient(
          colors: [AppTheme.lightGreen, AppTheme.lightPurple],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
      ),
      child: Text(
        initials.isEmpty ? '?' : initials,
        style: TextStyle(
          color: AppTheme.green,
          fontSize: size * 0.36,
          fontWeight: FontWeight.w800,
        ),
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Chats tab
// ---------------------------------------------------------------------------

class _ChatsTab extends StatelessWidget {
  const _ChatsTab({required this.conversations, required this.onChanged});

  final List<Conversation> conversations;
  final VoidCallback onChanged;

  @override
  Widget build(BuildContext context) {
    if (conversations.isEmpty) {
      return const EmptyView(
        icon: Icons.chat_bubble_outline,
        title: 'No conversations yet',
        message: 'Find travellers in Discover and send them a message '
            'request — once they accept, you can chat here.',
      );
    }
    return RefreshIndicator(
      onRefresh: () async => onChanged(),
      child: ListView.separated(
        padding: const EdgeInsets.symmetric(vertical: 8),
        itemCount: conversations.length,
        separatorBuilder: (_, _) =>
            const Divider(height: 1, indent: 76, endIndent: 16),
        itemBuilder: (context, i) {
          final c = conversations[i];
          return ListTile(
            contentPadding:
                const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
            leading: Avatar(name: c.otherDisplayName),
            title: Text(
              c.otherDisplayName,
              style: const TextStyle(fontWeight: FontWeight.w700),
            ),
            subtitle: Text(
              'Active ${_relTime(c.updatedAt)}',
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
            trailing: const Icon(Icons.chevron_right,
                color: AppTheme.green),
            onTap: () async {
              await Navigator.of(context).push(
                MaterialPageRoute<void>(
                  builder: (_) => ChatThreadScreen(conversation: c),
                ),
              );
              onChanged();
            },
          );
        },
      ),
    );
  }
}

String _relTime(DateTime t) {
  final diff = DateTime.now().toUtc().difference(t);
  if (diff.inMinutes < 1) return 'just now';
  if (diff.inMinutes < 60) return '${diff.inMinutes}m ago';
  if (diff.inHours < 24) return '${diff.inHours}h ago';
  if (diff.inDays < 7) return '${diff.inDays}d ago';
  return '${t.day}/${t.month}/${t.year}';
}

// ---------------------------------------------------------------------------
// Requests tab
// ---------------------------------------------------------------------------

class _RequestsTab extends StatefulWidget {
  const _RequestsTab({required this.onChanged});

  final VoidCallback onChanged;

  @override
  State<_RequestsTab> createState() => _RequestsTabState();
}

class _RequestsTabState extends State<_RequestsTab> {
  List<Conversation> _incoming = const [];
  List<BuddyRequest> _buddies = const [];
  bool _loading = true;
  Object? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final repo = context.read<AppState>().repo;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final results = await Future.wait<Object?>([
        repo.listChatRequests(direction: 'incoming'),
        repo.listBuddyRequests(direction: 'incoming'),
      ]);
      if (!mounted) return;
      setState(() {
        _incoming = (results[0]! as List<Conversation>)
            .where((c) => c.status == ConversationStatus.pending)
            .toList();
        _buddies = (results[1]! as List<BuddyRequest>)
            .where((b) => b.status == BuddyRequestStatus.pending)
            .toList();
        _loading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = e;
        _loading = false;
      });
    }
  }

  Future<void> _act(Future<void> Function() run) async {
    try {
      await run();
      if (!mounted) return;
      await _load();
      widget.onChanged();
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text('$e')));
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    if (_loading) return const LoadingView(label: 'Loading requests…');
    if (_error != null) return ErrorView(message: '$_error', onRetry: _load);

    if (_incoming.isEmpty && _buddies.isEmpty) {
      return const EmptyView(
        icon: Icons.person_add_alt_outlined,
        title: 'No pending requests',
        message: 'When someone wants to connect, their request shows up '
            'here for you to accept.',
      );
    }

    return RefreshIndicator(
      onRefresh: _load,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          if (_incoming.isNotEmpty) ...[
            Text('Message requests',
                style: theme.textTheme.titleSmall?.copyWith(
                    fontWeight: FontWeight.w800, color: AppTheme.purple)),
            const SizedBox(height: 8),
            ..._incoming.map((c) => Card(
                  margin: const EdgeInsets.only(bottom: 10),
                  child: Padding(
                    padding: const EdgeInsets.all(12),
                    child: Row(
                      children: [
                        Avatar(name: c.otherDisplayName),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(c.otherDisplayName,
                                  style: const TextStyle(
                                      fontWeight: FontWeight.w700)),
                              Text('wants to chat with you',
                                  style: theme.textTheme.bodySmall?.copyWith(
                                      color: theme.colorScheme.onSurfaceVariant)),
                            ],
                          ),
                        ),
                        IconButton(
                          tooltip: 'Decline',
                          onPressed: () =>
                              _act(() => repo0(context).rejectChatRequest(c.id)),
                          icon: Icon(Icons.close,
                              color: theme.colorScheme.outline),
                        ),
                        FilledButton.tonal(
                          onPressed: () =>
                              _act(() => repo0(context).acceptChatRequest(c.id)),
                          style: FilledButton.styleFrom(
                              backgroundColor: AppTheme.greenTint,
                              foregroundColor: AppTheme.green,
                              minimumSize: const Size(84, 40)),
                          child: const Text('Accept'),
                        ),
                      ],
                    ),
                  ),
                )),
          ],
          if (_buddies.isNotEmpty) ...[
            const SizedBox(height: 8),
            Text('Travel-buddy requests',
                style: theme.textTheme.titleSmall?.copyWith(
                    fontWeight: FontWeight.w800, color: AppTheme.purple)),
            const SizedBox(height: 8),
            ..._buddies.map((b) => Card(
                  margin: const EdgeInsets.only(bottom: 10),
                  child: Padding(
                    padding: const EdgeInsets.all(12),
                    child: Row(
                      children: [
                        Avatar(name: b.requesterDisplayName),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(b.requesterDisplayName,
                                  style: const TextStyle(
                                      fontWeight: FontWeight.w700)),
                              Text(
                                b.planDestination == null
                                    ? 'wants to travel with you'
                                    : 'invited you to ${b.planDestination}',
                                style: theme.textTheme.bodySmall?.copyWith(
                                    color: theme.colorScheme.onSurfaceVariant),
                              ),
                            ],
                          ),
                        ),
                        IconButton(
                          tooltip: 'Decline',
                          onPressed: () => _act(
                              () => repo0(context).rejectBuddyRequest(b.id)),
                          icon: Icon(Icons.close,
                              color: theme.colorScheme.outline),
                        ),
                        FilledButton.tonal(
                          onPressed: () => _act(
                              () => repo0(context).acceptBuddyRequest(b.id)),
                          style: FilledButton.styleFrom(
                              backgroundColor: AppTheme.purpleTint,
                              foregroundColor: AppTheme.purple,
                              minimumSize: const Size(84, 40)),
                          child: const Text('Accept'),
                        ),
                      ],
                    ),
                  ),
                )),
          ],
        ],
      ),
    );
  }
}

/// Convenience accessor (context is guaranteed at call sites above).
AppRepository repo0(BuildContext context) => context.read<AppState>().repo;

// ---------------------------------------------------------------------------
// Discover tab
// ---------------------------------------------------------------------------

class _DiscoverTab extends StatefulWidget {
  const _DiscoverTab();

  @override
  State<_DiscoverTab> createState() => _DiscoverTabState();
}

class _DiscoverTabState extends State<_DiscoverTab> {
  List<DiscoveryCandidate> _people = const [];
  bool _loading = true;
  Object? _error;
  final Set<String> _sent = {};

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final people = await context.read<AppState>().repo.discover();
      if (!mounted) return;
      setState(() {
        _people = people;
        _loading = false;
      });
    } on SocialGateDeniedException {
      if (!mounted) return;
      setState(() => _loading = false);
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = e;
        _loading = false;
      });
    }
  }

  Future<void> _send(
      Future<void> Function(String userId) run, String userId) async {
    try {
      await run(userId);
      if (!mounted) return;
      setState(() => _sent.add(userId));
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Request sent!')),
      );
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text('$e')));
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) return const LoadingView(label: 'Finding travellers…');
    if (_error != null) return ErrorView(message: '$_error', onRetry: _load);

    return RefreshIndicator(
      onRefresh: _load,
      child: _people.isEmpty
          ? ListView(children: const [
              SizedBox(height: 60),
              EmptyView(
                icon: Icons.travel_explore_outlined,
                title: 'No travellers yet',
                message: 'People with an active, discoverable travel plan '
                    'show up here. Check back soon.',
              ),
            ])
          : ListView(
              padding: const EdgeInsets.all(16),
              children: [
                ..._people.map((p) => _PersonCard(
                      person: p,
                      sent: _sent.contains(p.userId) ||
                          p.existingRequest != 'none',
                      onMessage: () => _send(
                        (id) => context
                            .read<AppState>()
                            .repo
                            .sendChatRequest(recipientId: id),
                        p.userId,
                      ),
                      onBuddy: () => _send(
                        (id) => context
                            .read<AppState>()
                            .repo
                            .sendBuddyRequest(recipientId: id),
                        p.userId,
                      ),
                    )),
              ],
            ),
    );
  }
}

class _PersonCard extends StatelessWidget {
  const _PersonCard({
    required this.person,
    required this.sent,
    required this.onMessage,
    required this.onBuddy,
  });

  final DiscoveryCandidate person;
  final bool sent;
  final VoidCallback onMessage;
  final VoidCallback onBuddy;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final score = person.compatibilityScore;

    return Card(
      margin: const EdgeInsets.only(bottom: 14),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(20),
        side: BorderSide(color: AppTheme.lightGreen.withValues(alpha: 0.7)),
      ),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Avatar(name: person.displayName, size: 52),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(person.displayName,
                          style: theme.textTheme.titleMedium
                              ?.copyWith(fontWeight: FontWeight.w800)),
                      if (person.homeRegion != null)
                        Text(person.homeRegion!,
                            style: theme.textTheme.bodySmall?.copyWith(
                                color: theme.colorScheme.onSurfaceVariant)),
                    ],
                  ),
                ),
                _ScoreRing(score: score),
              ],
            ),
            if (person.bio != null && person.bio!.isNotEmpty) ...[
              const SizedBox(height: 10),
              Text(person.bio!,
                  style: theme.textTheme.bodyMedium
                      ?.copyWith(color: theme.colorScheme.onSurfaceVariant)),
            ],
            const SizedBox(height: 10),
            Wrap(
              spacing: 6,
              runSpacing: 6,
              children: [
                _chip(Icons.flight_takeoff_outlined, person.destination,
                    AppTheme.green),
                ...?person.travelStyles?.take(3).map(
                      (s) => _chip(Icons.luggage_outlined, s.replaceAll('_', ' '),
                          AppTheme.purple),
                    ),
                ...?person.languages?.take(2).map(
                      (l) => _chip(Icons.translate_outlined, l,
                          AppTheme.green),
                    ),
              ],
            ),
            const SizedBox(height: 14),
            Row(
              children: [
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: sent ? null : onMessage,
                    icon: Icon(
                        sent ? Icons.check : Icons.chat_bubble_outline,
                        size: 18),
                    style: OutlinedButton.styleFrom(
                      minimumSize: const Size(0, 42),
                      foregroundColor: AppTheme.green,
                      side: const BorderSide(color: AppTheme.lightGreen),
                    ),
                    label: Text(sent ? 'Request sent' : 'Message'),
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: FilledButton.tonalIcon(
                    onPressed: sent ? null : onBuddy,
                    icon: const Icon(Icons.group_add_outlined, size: 18),
                    style: FilledButton.styleFrom(
                      minimumSize: const Size(0, 42),
                      backgroundColor: AppTheme.purpleTint,
                      foregroundColor: AppTheme.purple,
                    ),
                    label: const Text('Connect'),
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

Widget _chip(IconData icon, String label, Color color) {
  return Container(
    padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 5),
    decoration: BoxDecoration(
      color: color.withValues(alpha: 0.10),
      borderRadius: BorderRadius.circular(999),
    ),
    child: Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: 13, color: color),
        const SizedBox(width: 4),
        Text(
          label,
          style: TextStyle(
              color: color, fontSize: 12, fontWeight: FontWeight.w700),
        ),
      ],
    ),
  );
}

/// Circular compatibility score ring (0-100).
class _ScoreRing extends StatelessWidget {
  const _ScoreRing({required this.score});

  final int score;

  @override
  Widget build(BuildContext context) {
    final color = score >= 70
        ? AppTheme.green
        : score >= 40
            ? AppTheme.purple
            : AppTheme.lightPurple;
    return SizedBox(
      width: 48,
      height: 48,
      child: Stack(
        alignment: Alignment.center,
        children: [
          SizedBox(
            width: 48,
            height: 48,
            child: CircularProgressIndicator(
              value: score / 100,
              strokeWidth: 4,
              backgroundColor: AppTheme.greenTint,
              color: color,
            ),
          ),
          Text(
            '$score',
            style: TextStyle(
                fontSize: 13, fontWeight: FontWeight.w800, color: color),
          ),
        ],
      ),
    );
  }
}
