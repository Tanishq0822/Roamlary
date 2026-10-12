import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../data/app_repository.dart';
import '../models/models.dart';
import '../state/app_state.dart';
import '../widgets/common.dart';

/// The gated social surface (Phase 6 placeholder).
///
/// Calls GET /social/discovery. If the identity-verification gate denies
/// the caller (HTTP 403 while the policy requires verification), this
/// screen explains WHY and links back to verification — it never pretends
/// the feature exists (discovery itself ships in Phase 7).
class DiscoveryScreen extends StatefulWidget {
  const DiscoveryScreen({super.key});

  @override
  State<DiscoveryScreen> createState() => _DiscoveryScreenState();
}

enum _Phase { loading, denied, ready, failed }

class _DiscoveryScreenState extends State<DiscoveryScreen> {
  _Phase _phase = _Phase.loading;
  DiscoveryResult? _result;
  Object? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _phase = _Phase.loading;
      _error = null;
    });
    try {
      final result = await context.read<AppState>().repo.discovery();
      if (!mounted) return;
      setState(() {
        _result = result;
        _phase = _Phase.ready;
      });
    } on SocialGateDeniedException {
      if (!mounted) return;
      setState(() => _phase = _Phase.denied);
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = e;
        _phase = _Phase.failed;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(title: const Text('Travel-buddy discovery')),
      body: switch (_phase) {
        _Phase.loading => const LoadingView(label: 'Checking access…'),
        _Phase.failed => ErrorView(message: '$_error', onRetry: _load),
        _Phase.denied => ListView(
            padding: const EdgeInsets.all(16),
            children: [
              const SizedBox(height: 40),
              EmptyView(
                icon: Icons.lock_outline,
                title: 'Verification required',
                message:
                    'The policy currently asks for identity verification '
                    'before social access. Submit a verification request '
                    'and try again once an owner approves it.',
                action: OutlinedButton.icon(
                  onPressed: () => Navigator.of(context).pop(),
                  icon: const Icon(Icons.arrow_back),
                  label: const Text('Back to verification'),
                ),
              ),
            ],
          ),
        _Phase.ready => ListView(
            padding: const EdgeInsets.all(16),
            children: [
              SectionCard(
                title: 'Discovery (preview)',
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(_result!.message, style: theme.textTheme.bodyMedium),
                    const SizedBox(height: 12),
                    Text(
                      _result!.profiles.isEmpty
                          ? 'No travellers to show yet — this list '
                              'fills up in Phase 7.'
                          : '${_result!.profiles.length} travellers nearby.',
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: theme.colorScheme.onSurfaceVariant,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
      },
    );
  }
}
