import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/app_theme.dart';
import '../state/app_state.dart';
import 'blocked_users_screen.dart';
import 'contacts_screen.dart';
import 'meetups_screen.dart';
import 'notifications_screen.dart';
import 'owner_review_screen.dart';
import 'reports_screen.dart';
import 'trip_shares_screen.dart';
import 'verification_screen.dart';

/// "More" tab: everything that is important but not daily-use — safety
/// surfaces that used to be top-level (Reports, Contacts, Verify) plus the
/// Phase 9-13 additions (Meetups, Notifications, Trip sharing) and session
/// controls.
class MoreScreen extends StatelessWidget {
  const MoreScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final profile = context.watch<AppState>().profile;

    return Scaffold(
      appBar: AppBar(title: const Text('More')),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(16, 8, 16, 32),
        children: [
          // Identity card -------------------------------------------------
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              gradient: LinearGradient(
                colors: [
                  AppTheme.green.withValues(alpha: 0.12),
                  AppTheme.purple.withValues(alpha: 0.10),
                ],
              ),
              borderRadius: BorderRadius.circular(20),
            ),
            child: Row(
              children: [
                CircleAvatar(
                  radius: 26,
                  backgroundColor: AppTheme.green,
                  child: Text(
                    (profile?.displayName ?? 'R').characters.first.toUpperCase(),
                    style: const TextStyle(
                        color: Colors.white,
                        fontSize: 22,
                        fontWeight: FontWeight.w700),
                  ),
                ),
                const SizedBox(width: 14),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        profile?.displayName ?? 'Traveller',
                        style: theme.textTheme.titleMedium
                            ?.copyWith(fontWeight: FontWeight.w700),
                      ),
                      Text(
                        profile?.email ?? '',
                        style: theme.textTheme.bodySmall
                            ?.copyWith(color: theme.colorScheme.onSurfaceVariant),
                        overflow: TextOverflow.ellipsis,
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 20),

          _Section(
            title: 'Community',
            children: [
              _Tile(
                icon: Icons.campaign_outlined,
                selectedIcon: Icons.campaign,
                title: 'Safety reports',
                subtitle: 'See and file hazards near you',
                onTap: () => _push(context, const ReportsScreen()),
              ),
              _Tile(
                icon: Icons.handshake_outlined,
                selectedIcon: Icons.handshake,
                title: 'Meetups',
                subtitle: 'Join hikes, food walks and house parties',
                onTap: () => _push(context, const MeetupsScreen()),
              ),
              _Tile(
                icon: Icons.share_outlined,
                selectedIcon: Icons.share,
                title: 'Trip sharing',
                subtitle: 'Share a read-only itinerary link',
                onTap: () => _push(context, const TripSharesScreen()),
              ),
            ],
          ),
          const SizedBox(height: 16),
          _Section(
            title: 'Safety',
            children: [
              _Tile(
                icon: Icons.people_outline,
                selectedIcon: Icons.people,
                title: 'Trusted contacts',
                subtitle: 'Who gets alerted in an emergency',
                onTap: () => _push(context, const ContactsScreen()),
              ),
              _Tile(
                icon: Icons.notifications_outlined,
                selectedIcon: Icons.notifications,
                title: 'Notifications',
                subtitle: 'Delivery log for every alert we sent',
                onTap: () => _push(context, const NotificationsScreen()),
              ),
              _Tile(
                icon: Icons.block_outlined,
                selectedIcon: Icons.block,
                title: 'Blocked users',
                subtitle: 'Review and unblock people you muted',
                onTap: () => _push(context, const BlockedUsersScreen()),
              ),
              _Tile(
                icon: Icons.verified_user_outlined,
                selectedIcon: Icons.verified_user,
                title: 'Identity verification',
                subtitle: 'Unlock chats, discovery and meetups',
                trailing: const _VerifyChip(),
                onTap: () => _push(context, const VerificationScreen()),
              ),
            ],
          ),
          const SizedBox(height: 16),
          _Section(
            title: 'Account',
            children: [
              _Tile(
                icon: Icons.gavel_outlined,
                selectedIcon: Icons.gavel,
                title: 'Owner review queue',
                subtitle: 'Moderate pending verification requests',
                onTap: () => _push(context, const OwnerReviewScreen()),
              ),
              _Tile(
                icon: Icons.logout,
                title: 'Sign out',
                titleColor: AppTheme.danger,
                onTap: () => _confirmSignOut(context),
              ),
            ],
          ),
        ],
      ),
    );
  }

  static void _push(BuildContext context, Widget screen) {
    Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => screen));
  }

  static Future<void> _confirmSignOut(BuildContext context) async {
    final go = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Sign out?'),
        content: const Text('You will need to sign in again to use Roamlary.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(false),
            child: const Text('Stay'),
          ),
          FilledButton(
            onPressed: () => Navigator.of(dialogContext).pop(true),
            child: const Text('Sign out'),
          ),
        ],
      ),
    );
    if (go == true && context.mounted) {
      context.read<AppState>().signOut();
    }
  }
}

class _Section extends StatelessWidget {
  const _Section({required this.title, required this.children});

  final String title;
  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.only(left: 4, bottom: 8),
          child: Text(
            title.toUpperCase(),
            style: theme.textTheme.labelSmall?.copyWith(
              color: theme.colorScheme.onSurfaceVariant,
              fontWeight: FontWeight.w700,
              letterSpacing: 1.1,
            ),
          ),
        ),
        // Material (not a bare decorated Container) so the ListTiles'
        // ink effects paint on a real Material ancestor.
        Material(
          color: theme.colorScheme.surface,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(18),
            side: BorderSide(color: theme.dividerColor),
          ),
          clipBehavior: Clip.antiAlias,
          child: Column(
            children: [
              for (var i = 0; i < children.length; i++) ...[
                if (i > 0) const Divider(height: 1),
                children[i],
              ],
            ],
          ),
        ),
      ],
    );
  }
}

class _Tile extends StatelessWidget {
  const _Tile({
    required this.icon,
    this.selectedIcon,
    required this.title,
    this.subtitle,
    this.trailing,
    this.titleColor,
    required this.onTap,
  });

  final IconData icon;
  final IconData? selectedIcon;
  final String title;
  final String? subtitle;
  final Widget? trailing;
  final Color? titleColor;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return ListTile(
      onTap: onTap,
      leading: Icon(icon, color: titleColor ?? AppTheme.green),
      title: Text(
        title,
        style: TextStyle(
          fontWeight: FontWeight.w600,
          color: titleColor,
        ),
      ),
      subtitle: subtitle == null
          ? null
          : Text(subtitle!,
              style: theme.textTheme.bodySmall
                  ?.copyWith(color: theme.colorScheme.onSurfaceVariant)),
      trailing: trailing ?? const Icon(Icons.chevron_right, size: 20),
    );
  }
}

/// Small status pill so verification state is visible before you open the
/// screen.
class _VerifyChip extends StatefulWidget {
  const _VerifyChip();

  @override
  State<_VerifyChip> createState() => _VerifyChipState();
}

class _VerifyChipState extends State<_VerifyChip> {
  Object? _status;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final info =
          await context.read<AppState>().repo.verificationStatus();
      if (mounted) setState(() => _status = info.verificationStatus.wire);
    } catch (e) {
      if (mounted) setState(() => _status = 'unknown');
    }
  }

  @override
  Widget build(BuildContext context) {
    final wire = _status as String?;
    final (label, color) = switch (wire) {
      'verified' => ('Verified', AppTheme.green),
      'pending' => ('Pending', Colors.orange.shade800),
      'rejected' => ('Rejected', AppTheme.danger),
      _ => ('Unverified', Colors.grey),
    };
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(
        label,
        style: TextStyle(
          fontSize: 11,
          fontWeight: FontWeight.w700,
          color: color,
        ),
      ),
    );
  }
}
