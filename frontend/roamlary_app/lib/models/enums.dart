/// Status enums mirroring the backend's `app/models/enums.py` exactly.
///
/// The wire values (strings) match the FastAPI/StrEnum values one-for-one so a
/// JSON payload from the backend deserializes with no translation layer.
library;

enum CheckInStatus {
  pending('pending'),
  safe('safe'),
  needsHelp('needs_help'),
  expired('expired'),
  cancelled('cancelled');

  const CheckInStatus(this.wire);
  final String wire;

  static CheckInStatus fromWire(String value) =>
      CheckInStatus.values.firstWhere(
        (e) => e.wire == value,
        orElse: () => CheckInStatus.pending,
      );
}

enum SosStatus {
  active('active'),
  acknowledged('acknowledged'),
  resolved('resolved'),
  falseAlarm('false_alarm'),
  cancelled('cancelled');

  const SosStatus(this.wire);
  final String wire;

  static SosStatus fromWire(String value) => SosStatus.values.firstWhere(
        (e) => e.wire == value,
        orElse: () => SosStatus.active,
      );
}

enum ReportStatus {
  pending('pending'),
  approved('approved'),
  rejected('rejected');

  const ReportStatus(this.wire);
  final String wire;

  static ReportStatus fromWire(String value) => ReportStatus.values.firstWhere(
        (e) => e.wire == value,
        orElse: () => ReportStatus.pending,
      );
}

enum ReportCategory {
  unsafeArea('unsafe_area', 'Unsafe area'),
  harassment('harassment', 'Harassment'),
  suspiciousActivity('suspicious_activity', 'Suspicious activity'),
  roadHazard('road_hazard', 'Road hazard'),
  poorLighting('poor_lighting', 'Poor lighting'),
  other('other', 'Other');

  const ReportCategory(this.wire, this.label);
  final String wire;
  final String label;

  static ReportCategory fromWire(String value) =>
      ReportCategory.values.firstWhere(
        (e) => e.wire == value,
        orElse: () => ReportCategory.other,
      );
}

/// Account-level identity-verification state — mirrors backend
/// `app/models/enums.py::VerificationStatus` (Phase 6, second assignment).
enum VerificationStatus {
  unverified('unverified', 'Unverified'),
  pending('pending', 'Pending review'),
  verified('verified', 'Verified'),
  rejected('rejected', 'Rejected');

  const VerificationStatus(this.wire, this.label);
  final String wire;
  final String label;

  static VerificationStatus fromWire(String value) =>
      VerificationStatus.values.firstWhere(
        (e) => e.wire == value,
        orElse: () => VerificationStatus.unverified,
      );
}

/// State of ONE submitted verification request — mirrors backend
/// `VerificationRequestStatus` (note: `approved` request vs `verified`
/// account — the differing names are intentional, like the backend).
enum VerificationRequestStatus {
  pending('pending', 'Pending'),
  approved('approved', 'Approved'),
  rejected('rejected', 'Rejected');

  const VerificationRequestStatus(this.wire, this.label);
  final String wire;
  final String label;

  static VerificationRequestStatus fromWire(String value) =>
      VerificationRequestStatus.values.firstWhere(
        (e) => e.wire == value,
        orElse: () => VerificationRequestStatus.pending,
      );
}

/// Lifecycle of a one-to-one chat conversation / message request — mirrors
/// backend `ConversationStatus` (Phase 8).
enum ConversationStatus {
  pending('pending', 'Pending'),
  accepted('accepted', 'Accepted'),
  rejected('rejected', 'Rejected'),
  cancelled('cancelled', 'Cancelled');

  const ConversationStatus(this.wire, this.label);
  final String wire;
  final String label;

  static ConversationStatus fromWire(String value) =>
      ConversationStatus.values.firstWhere(
        (e) => e.wire == value,
        orElse: () => ConversationStatus.pending,
      );
}

/// State of a travel-buddy (connect) request — mirrors backend
/// `BuddyRequestStatus` (Phase 7).
enum BuddyRequestStatus {
  pending('pending', 'Pending'),
  accepted('accepted', 'Accepted'),
  rejected('rejected', 'Rejected'),
  cancelled('cancelled', 'Cancelled');

  const BuddyRequestStatus(this.wire, this.label);
  final String wire;
  final String label;

  static BuddyRequestStatus fromWire(String value) =>
      BuddyRequestStatus.values.firstWhere(
        (e) => e.wire == value,
        orElse: () => BuddyRequestStatus.pending,
      );
}

/// Category of a community meetup (Phase 9).
enum MeetupCategory {
  hiking('hiking', 'Hiking'),
  food('food', 'Food'),
  culture('culture', 'Culture'),
  adventure('adventure', 'Adventure'),
  leisure('leisure', 'Leisure'),
  nightlife('nightlife', 'Nightlife'),
  other('other', 'Other');

  const MeetupCategory(this.wire, this.label);
  final String wire;
  final String label;

  static MeetupCategory fromWire(String value) =>
      MeetupCategory.values.firstWhere(
        (e) => e.wire == value,
        orElse: () => MeetupCategory.other,
      );
}

/// Lifecycle of a meetup/house-party event (Phase 9).
enum MeetupStatus {
  active('active', 'Active'),
  cancelled('cancelled', 'Cancelled'),
  completed('completed', 'Completed');

  const MeetupStatus(this.wire, this.label);
  final String wire;
  final String label;

  static MeetupStatus fromWire(String value) =>
      MeetupStatus.values.firstWhere(
        (e) => e.wire == value,
        orElse: () => MeetupStatus.active,
      );
}

/// The caller's membership state on one meetup (Phase 9).
enum MembershipStatus {
  none('none', 'Not joined'),
  requested('requested', 'Requested'),
  approved('approved', 'Going'),
  declined('declined', 'Declined'),
  removed('removed', 'Removed'),
  left('left', 'Left');

  const MembershipStatus(this.wire, this.label);
  final String wire;
  final String label;

  static MembershipStatus fromWire(String value) =>
      MembershipStatus.values.firstWhere(
        (e) => e.wire == value,
        orElse: () => MembershipStatus.none,
      );
}

/// Delivery state of one outbound notification attempt (Phase 11).
enum NotificationStatus {
  queued('queued', 'Queued'),
  attempted('attempted', 'Attempted'),
  delivered('delivered', 'Delivered'),
  failed('failed', 'Failed'),
  unavailable('unavailable', 'Unavailable'),
  unknown('unknown', 'Unknown');

  const NotificationStatus(this.wire, this.label);
  final String wire;
  final String label;

  static NotificationStatus fromWire(String value) =>
      NotificationStatus.values.firstWhere(
        (e) => e.wire == value,
        orElse: () => NotificationStatus.unknown,
      );
}

/// Authorization role — mirrors backend `UserRole`. The server is the only
/// thing that can grant `owner`; the UI merely displays what it is told.
enum UserRole {
  user('user', 'Member'),
  owner('owner', 'Owner');

  const UserRole(this.wire, this.label);
  final String wire;
  final String label;

  static UserRole fromWire(String value) => UserRole.values.firstWhere(
        (e) => e.wire == value,
        orElse: () => UserRole.user,
      );
}

/// Lifecycle of a house-party invitation — mirrors backend
/// `InvitationStatus` (Phase 10). accepted/declined/revoked/expired are
/// terminal for that invitation; the host may always invite again.
enum InvitationStatus {
  pending('pending', 'Awaiting your reply'),
  accepted('accepted', 'Accepted'),
  declined('declined', 'Declined'),
  revoked('revoked', 'Withdrawn'),
  expired('expired', 'Expired'),
  unknown('unknown', 'Unknown');

  const InvitationStatus(this.wire, this.label);
  final String wire;
  final String label;

  bool get isPending => this == InvitationStatus.pending;

  static InvitationStatus fromWire(String value) =>
      InvitationStatus.values.firstWhere(
        (e) => e.wire == value,
        orElse: () => InvitationStatus.unknown,
      );
}
