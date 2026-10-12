import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/app_theme.dart';
import '../core/format.dart';
import '../models/enums.dart';
import '../models/models.dart';
import '../state/app_state.dart';
import '../widgets/common.dart';

/// Owner-only moderation surface (Phase 6, second assignment).
///
/// Lists verification requests (oldest submitted first, like the backend
/// queue), lets the owner approve/reject with an optional note, and exposes
/// the social-access policy switch. Server-side rules still apply and are
/// surfaced honestly: self-review is refused (409) and policy writes are
/// rate-limited (429).
class OwnerReviewScreen extends StatefulWidget {
  const OwnerReviewScreen({super.key});

  @override
  State<OwnerReviewScreen> createState() => _OwnerReviewScreenState();
}

class _OwnerReviewScreenState extends State<OwnerReviewScreen> {
  VerificationRequestStatus? _filter = VerificationRequestStatus.pending;
  List<VerificationRequestReview>? _rows;
  SocialPolicy? _policy;
  Object? _error;
  bool _acting = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _error = null;
      _rows = null;
    });
    final repo = context.read<AppState>().repo;
    try {
      final rows = await repo.listVerificationRequests(status: _filter);
      final policy = await repo.getSocialPolicy();
      if (!mounted) return;
      setState(() {
        _rows = rows;
        _policy = policy;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() => _error = e);
    }
  }

  Future<void> _decide(
    VerificationRequestReview row, {
    required bool approve,
  }) async {
    if (_acting) return;
    final decision = await showDialog<({bool confirmed, String? note})>(
      context: context,
      builder: (_) => _ReviewNoteDialog(
        approve: approve,
        displayName: row.displayName,
      ),
    );
    if (decision == null || !decision.confirmed || !mounted) return;
    setState(() => _acting = true);
    final repo = context.read<AppState>().repo;
    final note = (decision.note ?? '').trim();
    try {
      if (approve) {
        await repo.approveVerificationRequest(
          row.id,
          reviewNote: note.isEmpty ? null : note,
        );
      } else {
        await repo.rejectVerificationRequest(
          row.id,
          reviewNote: note.isEmpty ? null : note,
        );
      }
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            approve
                ? 'Approved — the applicant is now verified.'
                : 'Rejected — the applicant may apply again.',
          ),
        ),
      );
      await _load();
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(_message(e))),
      );
    } finally {
      if (mounted) setState(() => _acting = false);
    }
  }

  Future<void> _togglePolicy(bool value) async {
    if (_acting) return;
    setState(() => _acting = true);
    final repo = context.read<AppState>().repo;
    try {
      final policy = await repo.setSocialPolicy(requiresVerification: value);
      if (!mounted) return;
      setState(() => _policy = policy);
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(_message(e))),
      );
      await _load();
    } finally {
      if (mounted) setState(() => _acting = false);
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

  void _applyFilter(VerificationRequestStatus? status) {
    if (_filter == status) return;
    setState(() => _filter = status);
    _load();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(
        title: const Text('Owner review'),
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
          : _rows == null
              ? const LoadingView(label: 'Loading the queue…')
              : RefreshIndicator(
                  onRefresh: _load,
                  child: ListView(
                    padding: const EdgeInsets.all(16),
                    children: [
                      SectionCard(
                        title: 'Social access policy',
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            SwitchListTile(
                              value: _policy?.requiresVerification ?? true,
                              onChanged: _acting ? null : _togglePolicy,
                              contentPadding: EdgeInsets.zero,
                              title: const Text(
                                'Require verification for social access',
                              ),
                              subtitle: const Text(
                                'When on, only verified accounts can use '
                                    'social features. Every change is '
                                    'audited server-side and rate-limited.',
                              ),
                            ),
                            if (_policy?.updatedAt != null)
                              Text(
                                'Last changed ${formatDateTime(_policy!.updatedAt!)}',
                                style: theme.textTheme.bodySmall?.copyWith(
                                  color: theme.colorScheme.onSurfaceVariant,
                                ),
                              ),
                          ],
                        ),
                      ),
                      const SizedBox(height: 12),
                      SizedBox(
                        height: 56,
                        child: ListView(
                          scrollDirection: Axis.horizontal,
                          padding: const EdgeInsets.symmetric(vertical: 8),
                          children: [
                            _StatusChip(
                              label: 'All',
                              selected: _filter == null,
                              onTap: () => _applyFilter(null),
                            ),
                            ...VerificationRequestStatus.values.map(
                              (s) => _StatusChip(
                                label: s.label,
                                selected: _filter == s,
                                onTap: () => _applyFilter(s),
                              ),
                            ),
                          ],
                        ),
                      ),
                      if (_rows!.isEmpty)
                        const Padding(
                          padding: EdgeInsets.only(top: 40),
                          child: EmptyView(
                            icon: Icons.inbox_outlined,
                            title: 'Nothing here yet',
                            message:
                                'Requests submitted by users will appear '
                                    'in this queue, oldest first.',
                          ),
                        )
                      else
                        ..._rows!.map(
                          (row) => _RequestCard(
                            row: row,
                            busy: _acting,
                            onDecide: (approve) =>
                                _decide(row, approve: approve),
                          ),
                        ),
                      const SizedBox(height: 24),
                    ],
                  ),
                ),
    );
  }
}

class _StatusChip extends StatelessWidget {
  const _StatusChip({
    required this.label,
    required this.selected,
    required this.onTap,
  });

  final String label;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.only(right: 8),
      child: FilterChip(
        label: Text(label),
        selected: selected,
        onSelected: (_) => onTap(),
        selectedColor: theme.colorScheme.primaryContainer,
        checkmarkColor: theme.colorScheme.onPrimaryContainer,
      ),
    );
  }
}

class _RequestCard extends StatelessWidget {
  const _RequestCard({
    required this.row,
    required this.busy,
    required this.onDecide,
  });

  final VerificationRequestReview row;
  final bool busy;
  final ValueChanged<bool> onDecide;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final color = switch (row.status) {
      VerificationRequestStatus.pending => AppTheme.purple,
      VerificationRequestStatus.approved => AppTheme.green,
      VerificationRequestStatus.rejected => AppTheme.danger,
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
                StatusPill(label: row.status.label, color: color),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    row.displayName,
                    style: theme.textTheme.titleMedium?.copyWith(
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ),
                Text(
                  formatDateTime(row.createdAt),
                  style: theme.textTheme.bodySmall,
                ),
              ],
            ),
            if (row.applicantNote != null) ...[
              const SizedBox(height: 8),
              Text(
                'Applicant note: ${row.applicantNote}',
                style: theme.textTheme.bodyMedium,
              ),
            ],
            if (row.reviewNote != null) ...[
              const SizedBox(height: 4),
              Text(
                'Reviewer note: ${row.reviewNote}',
                style: theme.textTheme.bodyMedium?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                ),
              ),
            ],
            if (row.status == VerificationRequestStatus.pending) ...[
              const SizedBox(height: 12),
              Row(
                children: [
                  Expanded(
                    child: FilledButton.icon(
                      onPressed: busy ? null : () => onDecide(true),
                      icon: const Icon(Icons.check, size: 18),
                      label: const Text('Approve'),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: OutlinedButton.icon(
                      onPressed: busy ? null : () => onDecide(false),
                      style: OutlinedButton.styleFrom(
                        foregroundColor: AppTheme.danger,
                        side: const BorderSide(color: AppTheme.danger),
                      ),
                      icon: const Icon(Icons.close, size: 18),
                      label: const Text('Reject'),
                    ),
                  ),
                ],
              ),
            ],
          ],
        ),
      ),
    );
  }
}

/// Ask for an optional reviewer note before applying the decision.
class _ReviewNoteDialog extends StatefulWidget {
  const _ReviewNoteDialog({required this.approve, required this.displayName});

  final bool approve;
  final String displayName;

  @override
  State<_ReviewNoteDialog> createState() => _ReviewNoteDialogState();
}

class _ReviewNoteDialogState extends State<_ReviewNoteDialog> {
  final _noteCtrl = TextEditingController();

  @override
  void dispose() {
    _noteCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: Text(
        widget.approve
            ? 'Approve ${widget.displayName}?'
            : 'Reject ${widget.displayName}?',
      ),
      content: SizedBox(
        width: 320,
        child: TextField(
          controller: _noteCtrl,
          maxLines: 3,
          maxLength: 200,
          decoration: const InputDecoration(
            labelText: 'Note to the applicant (optional)',
            hintText: 'e.g. Verified at the hostel meet-up.',
            alignLabelWithHint: true,
          ),
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('Cancel'),
        ),
        FilledButton(
          style: widget.approve
              ? null
              : FilledButton.styleFrom(
                  backgroundColor: AppTheme.danger,
                ),
          onPressed: () => Navigator.of(context).pop(
            (confirmed: true, note: _noteCtrl.text),
          ),
          child: Text(widget.approve ? 'Approve' : 'Reject'),
        ),
      ],
    );
  }
}
