import 'package:flutter/material.dart';
import 'package:geolocator/geolocator.dart';
import 'package:provider/provider.dart';

import '../core/app_theme.dart';
import '../state/app_state.dart';
import 'chat_hub_screen.dart';
import 'home_dashboard.dart';
import 'more_screen.dart';
import 'safe_mode_screen.dart';
import 'sos_screen.dart';

/// App shell hosting the bottom navigation across the top-level areas.
///
/// The bar is custom-built (not [NavigationBar]) because the centre slot is a
/// raised, round SOS button — the app's most important action sits under the
/// thumb, always visible, on every tab.
class HomeShell extends StatefulWidget {
  const HomeShell({super.key});

  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> {
  int _index = 0;

  static const _pages = <Widget>[
    HomeDashboard(),
    SafeModeScreen(),
    ChatHubScreen(),
    MoreScreen(),
  ];

  void _select(int i) {
    if (i == _index) return;
    setState(() => _index = i);
  }

  /// Round SOS button in the middle of the bar: opens a confirmation sheet
  /// (never activates on a stray tap) which captures location and description
  /// before raising the incident.
  Future<void> _openSosSheet() async {
    final activated = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (sheetContext) => const _SosQuickSheet(),
    );
    if (!mounted) return;
    if (activated == true) {
      Navigator.of(context).push(
        MaterialPageRoute<void>(builder: (_) => const SosScreen()),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: IndexedStack(index: _index, children: _pages),
      bottomNavigationBar: _BottomBar(
        index: _index,
        onSelect: _select,
        onSos: _openSosSheet,
      ),
    );
  }
}

/// The bar itself: two tabs, the round SOS in the middle, two more tabs.
class _BottomBar extends StatelessWidget {
  const _BottomBar({
    required this.index,
    required this.onSelect,
    required this.onSos,
  });

  final int index;
  final ValueChanged<int> onSelect;
  final VoidCallback onSos;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Container(
      decoration: BoxDecoration(
        color: theme.colorScheme.surface,
        border: Border(top: BorderSide(color: theme.dividerColor)),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.06),
            blurRadius: 12,
            offset: const Offset(0, -2),
          ),
        ],
      ),
      child: SafeArea(
        top: false,
        child: SizedBox(
          height: 66,
          child: Row(
            children: [
              _NavItem(
                icon: Icons.home_outlined,
                selectedIcon: Icons.home,
                label: 'Home',
                selected: index == 0,
                onTap: () => onSelect(0),
              ),
              _NavItem(
                icon: Icons.shield_outlined,
                selectedIcon: Icons.shield,
                label: 'Safe',
                selected: index == 1,
                onTap: () => onSelect(1),
              ),
              // Raised above the bar so it reads as the centre button rather
              // than a fifth inline item. The Row still gives every child an
              // equal Expanded slot (2 left / SOS / 2 right), which is what
              // keeps the button mathematically centred on screen.
              Expanded(
                child: Center(
                  child: Transform.translate(
                    offset: const Offset(0, -22),
                    child: _SosButton(onTap: onSos),
                  ),
                ),
              ),
              _NavItem(
                icon: Icons.forum_outlined,
                selectedIcon: Icons.forum,
                label: 'Connect',
                selected: index == 2,
                onTap: () => onSelect(2),
              ),
              _NavItem(
                icon: Icons.menu_outlined,
                selectedIcon: Icons.menu,
                label: 'More',
                selected: index == 3,
                onTap: () => onSelect(3),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _NavItem extends StatelessWidget {
  const _NavItem({
    required this.icon,
    required this.selectedIcon,
    required this.label,
    required this.selected,
    required this.onTap,
  });

  final IconData icon;
  final IconData selectedIcon;
  final String label;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final color = selected
        ? AppTheme.green
        : Theme.of(context).colorScheme.onSurfaceVariant;
    return Expanded(
      child: InkWell(
        onTap: onTap,
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(selected ? selectedIcon : icon, color: color, size: 24),
            const SizedBox(height: 3),
            Text(
              label,
              style: Theme.of(context).textTheme.labelSmall?.copyWith(
                    color: color,
                    fontWeight: selected ? FontWeight.w700 : FontWeight.w500,
                  ),
            ),
          ],
        ),
      ),
    );
  }
}

/// Round, raised SOS button — danger gradient with a soft halo. Static at
/// rest on purpose: an infinite pulse would keep the widget tree permanently
/// animating (and stall `pumpAndSettle` in tests).
class _SosButton extends StatelessWidget {
  const _SosButton({required this.onTap});

  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Semantics(
      button: true,
      label: 'Activate SOS mode',
      child: GestureDetector(
        onTap: onTap,
        child: Container(
          width: 74,
          height: 74,
          alignment: Alignment.center,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            // Opaque ring: once the button floats above the bar this masks
            // whatever scrolls underneath, instead of letting it show
            // through a translucent halo.
            color: theme.colorScheme.surface,
            boxShadow: [
              BoxShadow(
                color: Colors.black.withValues(alpha: 0.10),
                blurRadius: 12,
                offset: const Offset(0, 3),
              ),
            ],
          ),
          child: Container(
            width: 60,
            height: 60,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              gradient: const LinearGradient(
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
                colors: [Color(0xFFEF5350), Color(0xFFD32F2F)],
              ),
              border: Border.all(color: Colors.white, width: 3),
              boxShadow: [
                BoxShadow(
                  color: AppTheme.danger.withValues(alpha: 0.45),
                  blurRadius: 16,
                  offset: const Offset(0, 5),
                ),
              ],
            ),
            child: const Text(
              'SOS',
              textAlign: TextAlign.center,
              style: TextStyle(
                color: Colors.white,
                fontSize: 15,
                fontWeight: FontWeight.w800,
                letterSpacing: 1.2,
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// Confirmation sheet before any SOS is raised: description validation,
/// optional live location, and the honesty note about what the prototype
/// actually does.
class _SosQuickSheet extends StatefulWidget {
  const _SosQuickSheet();

  @override
  State<_SosQuickSheet> createState() => _SosQuickSheetState();
}

class _SosQuickSheetState extends State<_SosQuickSheet> {
  final _descriptionCtrl = TextEditingController();
  bool _withLocation = true;
  bool _submitting = false;
  String? _error;

  @override
  void dispose() {
    _descriptionCtrl.dispose();
    super.dispose();
  }

  Future<void> _activate() async {
    final description = _descriptionCtrl.text.trim();
    if (description.length > 500) {
      setState(() => _error = 'Description must be at most 500 characters.');
      return;
    }
    setState(() {
      _submitting = true;
      _error = null;
    });
    try {
      double? lat;
      double? lng;
      final repo = context.read<AppState>().repo;
      if (_withLocation) {
        try {
          final pos = await Geolocator.getCurrentPosition(
            locationSettings: const LocationSettings(
              accuracy: LocationAccuracy.high,
              timeLimit: Duration(seconds: 10),
            ),
          );
          lat = pos.latitude;
          lng = pos.longitude;
        } catch (_) {
          // Permission denied or timeout — the incident still activates,
          // just without coordinates (the backend allows that).
        }
      }
      await repo.createSos(
            description: description.isEmpty ? null : description,
            latitude: lat,
            longitude: lng,
          );
      if (!mounted) return;
      Navigator.of(context).pop(true);
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _submitting = false;
        _error = e.toString();
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Padding(
      padding: EdgeInsets.only(
        left: 20,
        right: 20,
        bottom: MediaQuery.viewInsetsOf(context).bottom + 24,
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text('Raise SOS', style: theme.textTheme.titleLarge),
          const SizedBox(height: 6),
          Text(
            'Your trusted contacts are alerted with your last known location. '
            'You can acknowledge, resolve, or cancel the incident afterwards.',
            style: theme.textTheme.bodyMedium
                ?.copyWith(color: theme.colorScheme.onSurfaceVariant),
          ),
          const SizedBox(height: 16),
          TextField(
            controller: _descriptionCtrl,
            maxLength: 500,
            maxLines: 3,
            textInputAction: TextInputAction.done,
            decoration: const InputDecoration(
              labelText: 'What is happening? (optional)',
              hintText: 'e.g. Lost at the station, phone at 12%',
              border: OutlineInputBorder(),
            ),
          ),
          SwitchListTile(
            contentPadding: EdgeInsets.zero,
            title: const Text('Attach my live location'),
            subtitle: const Text('Coordinates recorded at activation time'),
            value: _withLocation,
            onChanged: (v) => setState(() => _withLocation = v),
          ),
          if (_error != null) ...[
            const SizedBox(height: 4),
            Text(
              _error!,
              style: TextStyle(color: theme.colorScheme.error),
            ),
          ],
          const SizedBox(height: 16),
          FilledButton(
            style: FilledButton.styleFrom(
              backgroundColor: AppTheme.danger,
              padding: const EdgeInsets.symmetric(vertical: 16),
            ),
            onPressed: _submitting ? null : _activate,
            child: _submitting
                ? const SizedBox(
                    width: 20,
                    height: 20,
                    child: CircularProgressIndicator(
                        strokeWidth: 2, color: Colors.white),
                  )
                : const Text('Activate SOS'),
          ),
          const SizedBox(height: 8),
          TextButton(
            onPressed: _submitting ? null : () => Navigator.of(context).pop(),
            child: const Text('Cancel'),
          ),
        ],
      ),
    );
  }
}
