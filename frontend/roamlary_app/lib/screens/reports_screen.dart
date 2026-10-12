import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/format.dart';
import '../models/enums.dart';
import '../models/models.dart';
import '../state/app_state.dart';
import '../widgets/common.dart';

/// Community safety reports: browse by category and file a new observation
/// about a place. Mirrors the backend's `/reports` list + create. Reports are
/// about locations, never people, and are user opinions — the UI says so.
class ReportsScreen extends StatefulWidget {
  const ReportsScreen({super.key});

  @override
  State<ReportsScreen> createState() => _ReportsScreenState();
}

class _ReportsScreenState extends State<ReportsScreen> {
  ReportCategory? _filter;
  List<CommunityReport>? _reports;
  Object? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _error = null;
      _reports = null;
    });
    try {
      final items =
          await context.read<AppState>().repo.listReports(category: _filter);
      if (!mounted) return;
      setState(() => _reports = items);
    } catch (e) {
      if (!mounted) return;
      setState(() => _error = e);
    }
  }

  Future<void> _openCreate() async {
    final created = await showDialog<bool>(
      context: context,
      builder: (_) => const _CreateReportDialog(),
    );
    if (created == true && mounted) {
      await _load();
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Community reports'),
        actions: [
          IconButton(
            tooltip: 'Refresh',
            onPressed: _load,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _openCreate,
        icon: const Icon(Icons.add_location_alt_outlined),
        label: const Text('Report'),
      ),
      body: Column(
        children: [
          SizedBox(
            height: 56,
            child: ListView(
              scrollDirection: Axis.horizontal,
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              children: [
                _FilterChip(
                  label: 'All',
                  selected: _filter == null,
                  onTap: () => _applyFilter(null),
                ),
                ...ReportCategory.values.map(
                  (c) => _FilterChip(
                    label: c.label,
                    selected: _filter == c,
                    onTap: () => _applyFilter(c),
                  ),
                ),
              ],
            ),
          ),
          Expanded(
            child: _error != null
                ? ErrorView(message: '$_error', onRetry: _load)
                : _reports == null
                    ? const LoadingView(label: 'Loading reports…')
                    : RefreshIndicator(
                        onRefresh: _load,
                        child: _reports!.isEmpty
                            ? ListView(
                                padding: const EdgeInsets.all(16),
                                children: const [
                                  SizedBox(height: 60),
                                  EmptyView(
                                    icon: Icons.map_outlined,
                                    title: 'No reports here',
                                    message:
                                        'Be the first to share an observation '
                                        'about a place.',
                                  ),
                                ],
                              )
                            : ListView.builder(
                                padding:
                                    const EdgeInsets.fromLTRB(16, 8, 16, 88),
                                itemCount: _reports!.length,
                                itemBuilder: (context, i) =>
                                    _ReportCard(report: _reports![i]),
                              ),
                      ),
          ),
        ],
      ),
    );
  }

  void _applyFilter(ReportCategory? category) {
    if (_filter == category) return;
    setState(() => _filter = category);
    _load();
  }
}

class _FilterChip extends StatelessWidget {
  const _FilterChip({
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

class _ReportCard extends StatelessWidget {
  const _ReportCard({required this.report});

  final CommunityReport report;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final verified = report.status == ReportStatus.approved;

    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                StatusPill(
                  label: report.category.label,
                  color: theme.colorScheme.primary,
                ),
                const SizedBox(width: 8),
                if (verified)
                  StatusPill(
                    label: 'Approved',
                    color: theme.colorScheme.tertiary,
                  ),
                const Spacer(),
                Text(
                  formatDateTime(report.createdAt),
                  style: theme.textTheme.bodySmall,
                ),
              ],
            ),
            const SizedBox(height: 10),
            Text(report.description, style: theme.textTheme.bodyMedium),
            if (report.latitude != null && report.longitude != null) ...[
              const SizedBox(height: 8),
              Row(
                children: [
                  const Icon(Icons.location_on_outlined, size: 16),
                  const SizedBox(width: 4),
                  Text(
                    '${report.latitude!.toStringAsFixed(4)}, '
                    '${report.longitude!.toStringAsFixed(4)}',
                    style: theme.textTheme.bodySmall,
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

class _CreateReportDialog extends StatefulWidget {
  const _CreateReportDialog();

  @override
  State<_CreateReportDialog> createState() => _CreateReportDialogState();
}

class _CreateReportDialogState extends State<_CreateReportDialog> {
  final _formKey = GlobalKey<FormState>();
  final _descriptionCtrl = TextEditingController();
  final _latCtrl = TextEditingController();
  final _lngCtrl = TextEditingController();
  ReportCategory _category = ReportCategory.unsafeArea;
  bool _saving = false;

  @override
  void dispose() {
    _descriptionCtrl.dispose();
    _latCtrl.dispose();
    _lngCtrl.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    if (!(_formKey.currentState?.validate() ?? false)) return;
    if (_saving) return;
    setState(() => _saving = true);
    final repo = context.read<AppState>().repo;
    try {
      await repo.createReport(
        category: _category,
        description: _descriptionCtrl.text.trim(),
        latitude: double.parse(_latCtrl.text.trim()),
        longitude: double.parse(_lngCtrl.text.trim()),
      );
      if (mounted) Navigator.of(context).pop(true);
    } catch (e) {
      if (!mounted) return;
      setState(() => _saving = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('$e')),
      );
    }
  }

  String? _validateCoord(String? value, double min, double max, String label) {
    final parsed = double.tryParse((value ?? '').trim());
    if (parsed == null) return 'Enter a valid $label';
    if (parsed < min || parsed > max) {
      return '$label must be $min…$max';
    }
    return null;
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('File a report'),
      content: SizedBox(
        width: 320,
        child: Form(
          key: _formKey,
          child: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                DropdownButtonFormField<ReportCategory>(
                  value: _category,
                  decoration: const InputDecoration(labelText: 'Category'),
                  items: ReportCategory.values
                      .map((c) => DropdownMenuItem(
                            value: c,
                            child: Text(c.label),
                          ))
                      .toList(),
                  onChanged: (v) => setState(() => _category = v!),
                ),
                const SizedBox(height: 12),
                TextFormField(
                  controller: _descriptionCtrl,
                  maxLines: 3,
                  maxLength: 500,
                  decoration: const InputDecoration(
                    labelText: 'What did you observe?',
                    hintText: 'e.g. Dark street behind the station',
                    alignLabelWithHint: true,
                  ),
                  validator: (v) {
                    final t = (v ?? '').trim();
                    if (t.isEmpty) return 'Describe what you observed';
                    if (t.length > 500) return 'Keep it under 500 characters';
                    return null;
                  },
                ),
                const SizedBox(height: 12),
                Row(
                  children: [
                    Expanded(
                      child: TextFormField(
                        controller: _latCtrl,
                        keyboardType: const TextInputType.numberWithOptions(
                          decimal: true,
                          signed: true,
                        ),
                        decoration: const InputDecoration(labelText: 'Latitude'),
                        validator: (v) => _validateCoord(v, -90, 90, 'latitude'),
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: TextFormField(
                        controller: _lngCtrl,
                        keyboardType: const TextInputType.numberWithOptions(
                          decimal: true,
                          signed: true,
                        ),
                        decoration:
                            const InputDecoration(labelText: 'Longitude'),
                        validator: (v) =>
                            _validateCoord(v, -180, 180, 'longitude'),
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
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
              : const Text('Submit'),
        ),
      ],
    );
  }
}
