import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/app_theme.dart';
import '../state/app_state.dart';
import '../widgets/common.dart';
import 'checkins_screen.dart';
import 'sos_screen.dart';

/// Safe Mode: a focused "arm your trip" surface that surfaces the safety
/// essentials (SOS + check-ins) behind a single, calm screen.
class SafeModeScreen extends StatefulWidget {
  const SafeModeScreen({super.key});

  @override
  State<SafeModeScreen> createState() => _SafeModeScreenState();
}

class _SafeModeScreenState extends State<SafeModeScreen> {
  bool _armed = false;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(title: const Text('Safe Mode')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Container(
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              color: _armed
                  ? AppTheme.danger.withOpacity(0.10)
                  : theme.colorScheme.primaryContainer,
              borderRadius: BorderRadius.circular(20),
            ),
            child: Column(
              children: [
                Icon(
                  _armed ? Icons.shield : Icons.shield_outlined,
                  size: 64,
                  color: _armed
                      ? AppTheme.danger
                      : theme.colorScheme.onPrimaryContainer,
                ),
                const SizedBox(height: 12),
                Text(
                  _armed ? 'Safe Mode is ON' : 'Safe Mode is OFF',
                  style: theme.textTheme.titleLarge?.copyWith(
                    fontWeight: FontWeight.w800,
                  ),
                ),
                const SizedBox(height: 6),
                Text(
                  _armed
                      ? 'Stay aware. SOS and check-ins are ready below.'
                      : 'Arm Safe Mode before heading out somewhere unfamiliar.',
                  textAlign: TextAlign.center,
                  style: theme.textTheme.bodyMedium?.copyWith(
                    color: theme.colorScheme.onSurfaceVariant,
                  ),
                ),
                const SizedBox(height: 16),
                FilledButton.icon(
                  style: _armed
                      ? FilledButton.styleFrom(
                          backgroundColor: AppTheme.danger,
                          foregroundColor: Colors.white,
                        )
                      : null,
                  onPressed: () => setState(() => _armed = !_armed),
                  icon: Icon(_armed ? Icons.power_settings_new : Icons.shield),
                  label: Text(_armed ? 'Turn off' : 'Arm Safe Mode'),
                ),
              ],
            ),
          ),
          const SizedBox(height: 20),
          _ActionTile(
            icon: Icons.crisis_alert,
            iconColor: AppTheme.danger,
            title: 'Emergency SOS',
            subtitle: 'Record an incident with your location.',
            onTap: () => Navigator.of(context).push(
              MaterialPageRoute<void>(builder: (_) => const SosScreen()),
            ),
          ),
          const SizedBox(height: 12),
          _ActionTile(
            icon: Icons.task_alt,
            title: 'Safety check-ins',
            subtitle: 'Promise to be back by a time — and mark yourself safe.',
            onTap: () => Navigator.of(context).push(
              MaterialPageRoute<void>(builder: (_) => const CheckInsScreen()),
            ),
          ),
          const SizedBox(height: 12),
          _ActionTile(
            icon: Icons.people,
            title: 'Trusted contacts',
            subtitle: 'The people you would want reachable in an emergency.',
            onTap: () => _goToContacts(context),
          ),
        ],
      ),
    );
  }

  void _goToContacts(BuildContext context) {
    // Contacts live in another bottom-nav tab; nudge the user there.
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text('Open the Contacts tab to manage your circle.'),
      ),
    );
  }
}

class _ActionTile extends StatelessWidget {
  const _ActionTile({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.onTap,
    this.iconColor,
  });

  final IconData icon;
  final String title;
  final String subtitle;
  final VoidCallback onTap;
  final Color? iconColor;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Card(
      child: ListTile(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        leading: Icon(icon, color: iconColor ?? theme.colorScheme.primary),
        title: Text(title, style: const TextStyle(fontWeight: FontWeight.w700)),
        subtitle: Text(subtitle),
        trailing: const Icon(Icons.chevron_right),
        onTap: onTap,
      ),
    );
  }
}
