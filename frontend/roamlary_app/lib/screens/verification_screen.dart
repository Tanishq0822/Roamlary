import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/app_theme.dart';
import '../core/format.dart';
import '../models/enums.dart';
import '../models/models.dart';
import '../state/app_state.dart';
import '../widgets/common.dart';
import 'discovery_screen.dart';
import 'owner_review_screen.dart';

/// Identity-verification hub (Phase 6, second assignment).
///
/// Users always see their OWN account state and may submit a manual-review
/// request (optional short note only — the app NEVER asks for ID numbers or
/// documents, mirroring the backend contract). Owners additionally reach the
/// review queue from here.
class VerificationScreen extends StatefulWidget {
  const VerificationScreen({super.key});

  @override
  State<VerificationScreen> createState() => _VerificationScreenState();
}

class _VerificationScreenState extends State<VerificationScreen> {
  VerificationStatusInfo? _info;
  Object? _error;
  bool _submitting = false;
  final _noteCtrl = TextEditingController();

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _noteCtrl.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() {
      _error = null;
      _info = null;
    });
    try {
      final info = await context.read<AppState>().repo.verificationStatus();
      if (!mounted) return;
      setState(() => _info = info);
    } catch (e) {
      if (!mounted) return;
      setState(() => _error = e);
    }
  }

  Future<void> _submit() async {
    if (_submitting) return;
    setState(() => _submitting = true);
    final repo = context.read<AppState>().repo;
    final note = _noteCtrl.text.trim();
    try {
      await repo.submitVerificationRequest(note: note.isEmpty ? null : note);
      _noteCtrl.clear();
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Request submitted — an owner will review it manually.'),
        ),
      );
      await _load();
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(_message(e))),
      );
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  static String _message(Object error) {
    try {
      final dynamic e = error;
      final String? msg = e.message as String?;
      if (msg != null && msg.isNotEmpty) return msg;
    } catch (_) {}
    return '$error';
  }

  Color _statusColor(VerificationStatus status, ColorScheme scheme) =>
      switch (status) {
        VerificationStatus.unverified => scheme.outline,
        VerificationStatus.pending => AppTheme.purple,
        VerificationStatus.verified => AppTheme.green,
        VerificationStatus.rejected => AppTheme.danger,
      };

  String _explanation(VerificationStatus status) => switch (status) {
        VerificationStatus.unverified =>
          'You have not started verification yet. An app owner reviews '
              'requests manually — no ID documents are ever collected.',
        VerificationStatus.pending =>
          'Your request is under review. The reviewer’s note will '
              'appear here once it is decided.',
        VerificationStatus.verified =>
          'You are verified. Social features are unlocked while the '
              'policy requires verification.',
        VerificationStatus.rejected =>
          'Your last request was declined. You can submit a new one at '
              'any time.',
      };

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    return Scaffold(
      appBar: AppBar(
        title: const Text('Verification'),
        actions: [
          IconButton(
            tooltip: 'Refresh',
            onPressed: _load,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: _error != null
          ? ErrorView(message: '$_error', onRetry: _load)
          : _info == null
              ? const LoadingView(label: 'Loading your verification status…')
              : RefreshIndicator(
                  onRefresh: _load,
                  child: ListView(
                    padding: const EdgeInsets.all(16),
                    children: [
                      SectionCard(
                        title: 'Your account',
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              children: [
                                StatusPill(
                                  label: _info!.verificationStatus.label,
                                  color: _statusColor(
                                    _info!.verificationStatus,
                                    scheme,
                                  ),
                                ),
                                const SizedBox(width: 8),
                                StatusPill(
                                  label: _info!.role.label,
                                  color: _info!.role == UserRole.owner
                                      ? AppTheme.purple
                                      : scheme.outline,
                                ),
                              ],
                            ),
                            const SizedBox(height: 12),
                            Text(
                              _explanation(_info!.verificationStatus),
                              style: theme.textTheme.bodyMedium?.copyWith(
                                color: scheme.onSurfaceVariant,
                              ),
                            ),
                            const SizedBox(height: 8),
                            Text(
                              _info!.socialAccessRequired
                                  ? 'Social features require verification '
                                      'right now.'
                                  : 'Social access is currently open '
                                      '(verification not required).',
                              style: theme.textTheme.bodySmall,
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(height: 12),
                      if (_info!.canSubmitRequest) ...[
                        SectionCard(
                          title: 'Request verification',
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              TextField(
                                controller: _noteCtrl,
                                maxLines: 2,
                                maxLength: 200,
                                decoration: const InputDecoration(
                                  labelText: 'Note for the reviewer (optional)',
                                  hintText: 'e.g. Why do you need '
                                      'verification? No ID documents are '
                                      'collected.',
                                  alignLabelWithHint: true,
                                ),
                              ),
                              const SizedBox(height: 8),
                              FilledButton.icon(
                                onPressed: _submitting ? null : _submit,
                                icon: _submitting
                                    ? const SizedBox(
                                        height: 18,
                                        width: 18,
                                        child: CircularProgressIndicator(
                                          strokeWidth: 2,
                                        ),
                                      )
                                    : const Icon(Icons.send_outlined),
                                label: const Text('Submit request'),
                              ),
                            ],
                          ),
                        ),
                        const SizedBox(height: 12),
                      ],
                      if (_info!.latestRequest != null) ...[
                        SectionCard(
                          title: 'Latest request',
                          child: _RequestDetails(request: _info!.latestRequest!),
                        ),
                        const SizedBox(height: 12),
                      ],
                      SectionCard(
                        title: 'Travel-buddy discovery',
                        child: ListTile(
                          contentPadding: EdgeInsets.zero,
                          leading: Icon(
                            Icons.travel_explore,
                            color: scheme.primary,
                          ),
                          title: const Text('Open the social surface'),
                          subtitle: Text(
                            _info!.socialAccessRequired &&
                                    _info!.verificationStatus !=
                                        VerificationStatus.verified
                                ? 'Locked until you are verified'
                                : 'Available',
                          ),
                          trailing: const Icon(Icons.chevron_right),
                          onTap: () => Navigator.of(context).push(
                            MaterialPageRoute(
                              builder: (_) => const DiscoveryScreen(),
                            ),
                          ),
                        ),
                      ),
                      if (_info!.role == UserRole.owner) ...[
                        const SizedBox(height: 12),
                        SectionCard(
                          title: 'Owner tools',
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                'Review other people’s verification '
                                    'requests and change the social-access '
                                    'policy.',
                                style: theme.textTheme.bodyMedium?.copyWith(
                                  color: scheme.onSurfaceVariant,
                                ),
                              ),
                              const SizedBox(height: 12),
                              FilledButton.icon(
                                onPressed: () => Navigator.of(context).push(
                                  MaterialPageRoute(
                                    builder: (_) => const OwnerReviewScreen(),
                                  ),
                                ),
                                style: FilledButton.styleFrom(
                                  backgroundColor: AppTheme.purple,
                                ),
                                icon: const Icon(Icons.gavel_outlined),
                                label: const Text('Open review queue'),
                              ),
                            ],
                          ),
                        ),
                      ],
                      const SizedBox(height: 24),
                    ],
                  ),
                ),
    );
  }
}

/// Read-only detail block for the caller's latest request.
class _RequestDetails extends StatelessWidget {
  const _RequestDetails({required this.request});

  final VerificationRequest request;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final color = switch (request.status) {
      VerificationRequestStatus.pending => AppTheme.purple,
      VerificationRequestStatus.approved => AppTheme.green,
      VerificationRequestStatus.rejected => AppTheme.danger,
    };
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            StatusPill(label: request.status.label, color: color),
            const Spacer(),
            Text(
              formatDateTime(request.createdAt),
              style: theme.textTheme.bodySmall,
            ),
          ],
        ),
        if (request.applicantNote != null) ...[
          const SizedBox(height: 8),
          Text(
            'Your note: ${request.applicantNote}',
            style: theme.textTheme.bodyMedium,
          ),
        ],
        if (request.reviewNote != null) ...[
          const SizedBox(height: 4),
          Text(
            'Reviewer note: ${request.reviewNote}',
            style: theme.textTheme.bodyMedium?.copyWith(
              color: theme.colorScheme.onSurfaceVariant,
            ),
          ),
        ],
      ],
    );
  }
}
