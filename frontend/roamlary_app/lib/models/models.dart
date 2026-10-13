import 'enums.dart';

/// A trusted contact — mirrors backend `TrustedContactRead`.
class TrustedContact {
  const TrustedContact({
    required this.id,
    required this.userId,
    required this.name,
    required this.phone,
    this.relationship,
    this.email,
    required this.createdAt,
    required this.updatedAt,
  });

  final String id;
  final String userId;
  final String name;
  final String phone;
  final String? relationship;
  final String? email;
  final DateTime createdAt;
  final DateTime updatedAt;

  factory TrustedContact.fromJson(Map<String, dynamic> json) =>
      TrustedContact(
        id: json['id'] as String,
        userId: json['user_id'] as String,
        name: json['name'] as String,
        phone: json['phone'] as String,
        relationship: json['relationship'] as String?,
        email: json['email'] as String?,
        createdAt: DateTime.parse(json['created_at'] as String),
        updatedAt: DateTime.parse(json['updated_at'] as String),
      );
}

/// A safety check-in — mirrors backend `CheckInRead`.
class CheckIn {
  const CheckIn({
    required this.id,
    required this.userId,
    required this.status,
    this.note,
    this.dueAt,
    this.completedAt,
    required this.createdAt,
    required this.updatedAt,
  });

  final String id;
  final String userId;
  final CheckInStatus status;
  final String? note;
  final DateTime? dueAt;
  final DateTime? completedAt;
  final DateTime createdAt;
  final DateTime updatedAt;

  bool get isOpen => status == CheckInStatus.pending;

  /// Location shared with this check-in, if any.
  ///
  /// The backend's check-in contract has no coordinate fields, so the app
  /// writes a `📍 lat,lng` marker into the (500-char) note and reads it back
  /// here. Keeps every screen in one place: [location] and [noteWithoutLocation].
  CheckInLocation? get location {
    final match = _locationPattern.firstMatch(note ?? '');
    if (match == null) return null;
    final lat = double.tryParse(match.group(1)!);
    final lng = double.tryParse(match.group(2)!);
    if (lat == null || lng == null) return null;
    if (lat < -90 || lat > 90 || lng < -180 || lng > 180) return null;
    return CheckInLocation(lat: lat, lng: lng);
  }

  /// The note with the location marker stripped, for tidy display.
  String? get noteWithoutLocation {
    final stripped = (note ?? '').replaceAll(_locationPattern, '').trim();
    return stripped.isEmpty ? null : stripped;
  }

  static final _locationPattern = RegExp(r'📍\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)');

  factory CheckIn.fromJson(Map<String, dynamic> json) => CheckIn(
        id: json['id'] as String,
        userId: json['user_id'] as String,
        status: CheckInStatus.fromWire(json['status'] as String),
        note: json['note'] as String?,
        dueAt: json['due_at'] == null
            ? null
            : DateTime.parse(json['due_at'] as String),
        completedAt: json['completed_at'] == null
            ? null
            : DateTime.parse(json['completed_at'] as String),
        createdAt: DateTime.parse(json['created_at'] as String),
        updatedAt: DateTime.parse(json['updated_at'] as String),
      );
}

/// A lat/lng pair shared alongside a check-in (parsed from the note marker).
class CheckInLocation {
  const CheckInLocation({required this.lat, required this.lng});

  final double lat;
  final double lng;

  String get mapsUrl => 'https://maps.google.com/?q=$lat,$lng';
}

/// An SOS incident — mirrors backend `SosEventRead`.
class SosEvent {
  const SosEvent({
    required this.id,
    required this.userId,
    required this.status,
    this.description,
    this.latitude,
    this.longitude,
    this.locationRecordedAt,
    required this.createdAt,
    required this.updatedAt,
    this.cancelledAt,
    this.resolvedAt,
    this.acknowledgedAt,
  });

  final String id;
  final String userId;
  final SosStatus status;
  final String? description;
  final double? latitude;
  final double? longitude;
  final DateTime? locationRecordedAt;
  final DateTime createdAt;
  final DateTime updatedAt;
  final DateTime? cancelledAt;
  final DateTime? resolvedAt;
  final DateTime? acknowledgedAt;

  bool get isActive => status == SosStatus.active;
  bool get isOpen => status == SosStatus.active ||
      status == SosStatus.acknowledged;

  factory SosEvent.fromJson(Map<String, dynamic> json) => SosEvent(
        id: json['id'] as String,
        userId: json['user_id'] as String,
        status: SosStatus.fromWire(json['status'] as String),
        description: json['description'] as String?,
        latitude: (json['latitude'] as num?)?.toDouble(),
        longitude: (json['longitude'] as num?)?.toDouble(),
        locationRecordedAt: json['location_recorded_at'] == null
            ? null
            : DateTime.parse(json['location_recorded_at'] as String),
        createdAt: DateTime.parse(json['created_at'] as String),
        updatedAt: DateTime.parse(json['updated_at'] as String),
        cancelledAt: json['cancelled_at'] == null
            ? null
            : DateTime.parse(json['cancelled_at'] as String),
        resolvedAt: json['resolved_at'] == null
            ? null
            : DateTime.parse(json['resolved_at'] as String),
        acknowledgedAt: json['acknowledged_at'] == null
            ? null
            : DateTime.parse(json['acknowledged_at'] as String),
      );
}

/// A community safety report — mirrors backend `ReportRead`.
///
/// Note the absence of any owner field: reports are about places, not people.
class CommunityReport {
  const CommunityReport({
    required this.id,
    required this.category,
    required this.status,
    required this.description,
    this.latitude,
    this.longitude,
    required this.createdAt,
    required this.updatedAt,
  });

  final String id;
  final ReportCategory category;
  final ReportStatus status;
  final String description;
  final double? latitude;
  final double? longitude;
  final DateTime createdAt;
  final DateTime updatedAt;

  factory CommunityReport.fromJson(Map<String, dynamic> json) =>
      CommunityReport(
        id: json['id'] as String,
        category: ReportCategory.fromWire(json['category'] as String),
        status: ReportStatus.fromWire(json['status'] as String),
        description: json['description'] as String,
        latitude: (json['latitude'] as num?)?.toDouble(),
        longitude: (json['longitude'] as num?)?.toDouble(),
        createdAt: DateTime.parse(json['created_at'] as String),
        updatedAt: DateTime.parse(json['updated_at'] as String),
      );
}

/// The authenticated user's public profile — mirrors backend `UserProfile`.
class UserProfile {
  const UserProfile({
    required this.id,
    required this.displayName,
    this.email,
    required this.createdAt,
    required this.updatedAt,
  });

  final String id;
  final String displayName;
  final String? email;
  final DateTime createdAt;
  final DateTime updatedAt;

  factory UserProfile.fromJson(Map<String, dynamic> json) => UserProfile(
        id: json['id'] as String,
        displayName: json['display_name'] as String,
        email: json['email'] as String?,
        createdAt: DateTime.parse(json['created_at'] as String),
        updatedAt: DateTime.parse(json['updated_at'] as String),
      );
}

/// One verification request from the CALLER'S OWN account — mirrors backend
/// `VerificationRequestSummary` (Phase 6, second assignment). The only free
/// text is an optional short note: identity documents are NEVER collected.
class VerificationRequest {
  const VerificationRequest({
    required this.id,
    required this.status,
    required this.createdAt,
    this.reviewedAt,
    this.reviewNote,
    this.applicantNote,
  });

  final String id;
  final VerificationRequestStatus status;
  final DateTime createdAt;
  final DateTime? reviewedAt;
  final String? reviewNote;
  final String? applicantNote;

  factory VerificationRequest.fromJson(Map<String, dynamic> json) =>
      VerificationRequest(
        id: json['id'] as String,
        status: VerificationRequestStatus.fromWire(json['status'] as String),
        createdAt: DateTime.parse(json['created_at'] as String),
        reviewedAt: json['reviewed_at'] == null
            ? null
            : DateTime.parse(json['reviewed_at'] as String),
        reviewNote: json['review_note'] as String?,
        applicantNote: json['applicant_note'] as String?,
      );
}

/// Owner's queue view of someone's request — mirrors backend
/// `VerificationRequestReview` (adds who submitted + who reviewed). Only
/// owner-gated endpoints ever return this shape.
class VerificationRequestReview {
  const VerificationRequestReview({
    required this.id,
    required this.userId,
    required this.displayName,
    required this.status,
    required this.createdAt,
    this.reviewedAt,
    this.reviewedBy,
    this.reviewNote,
    this.applicantNote,
  });

  final String id;
  final String userId;
  final String displayName;
  final VerificationRequestStatus status;
  final DateTime createdAt;
  final DateTime? reviewedAt;
  final String? reviewedBy;
  final String? reviewNote;
  final String? applicantNote;

  factory VerificationRequestReview.fromJson(Map<String, dynamic> json) =>
      VerificationRequestReview(
        id: json['id'] as String,
        userId: json['user_id'] as String,
        displayName: json['display_name'] as String,
        status: VerificationRequestStatus.fromWire(json['status'] as String),
        createdAt: DateTime.parse(json['created_at'] as String),
        reviewedAt: json['reviewed_at'] == null
            ? null
            : DateTime.parse(json['reviewed_at'] as String),
        reviewedBy: json['reviewed_by'] as String?,
        reviewNote: json['review_note'] as String?,
        applicantNote: json['applicant_note'] as String?,
      );
}

/// The caller's OWN verification picture — mirrors backend
/// `VerificationStatusResponse`. `role` is the caller's OWN role only.
class VerificationStatusInfo {
  const VerificationStatusInfo({
    required this.verificationStatus,
    required this.role,
    required this.socialAccessRequired,
    this.latestRequest,
  });

  final VerificationStatus verificationStatus;
  final UserRole role;
  final bool socialAccessRequired;
  final VerificationRequest? latestRequest;

  /// Submitting is only possible from `unverified` or `rejected`
  /// (mirrors the backend's 409 rules for pending/verified).
  bool get canSubmitRequest =>
      verificationStatus == VerificationStatus.unverified ||
      verificationStatus == VerificationStatus.rejected;

  factory VerificationStatusInfo.fromJson(Map<String, dynamic> json) =>
      VerificationStatusInfo(
        verificationStatus:
            VerificationStatus.fromWire(json['verification_status'] as String),
        role: UserRole.fromWire(json['role'] as String),
        socialAccessRequired: json['social_access_required'] as bool,
        latestRequest: json['latest_request'] == null
            ? null
            : VerificationRequest.fromJson(
                json['latest_request'] as Map<String, dynamic>,
              ),
      );
}

/// Owner-only social-verification policy — mirrors backend `PolicyResponse`.
class SocialPolicy {
  const SocialPolicy({
    required this.key,
    required this.requiresVerification,
    this.updatedAt,
    this.updatedBy,
  });

  final String key;
  final bool requiresVerification;
  final DateTime? updatedAt;
  final String? updatedBy;

  factory SocialPolicy.fromJson(Map<String, dynamic> json) => SocialPolicy(
        key: json['key'] as String,
        requiresVerification: json['requires_verification'] as bool,
        updatedAt: json['updated_at'] == null
            ? null
            : DateTime.parse(json['updated_at'] as String),
        updatedBy: json['updated_by'] as String?,
      );
}

/// Result of the gated social discovery call — mirrors backend
/// `DiscoveryResponse`. Phase 6 ships an honest empty placeholder.
class DiscoveryResult {
  const DiscoveryResult({required this.profiles, required this.message});

  final List<Map<String, dynamic>> profiles;
  final String message;

  factory DiscoveryResult.fromJson(Map<String, dynamic> json) =>
      DiscoveryResult(
        profiles: (json['profiles'] as List<dynamic>? ?? const [])
            .map((e) => Map<String, dynamic>.from(e as Map))
            .toList(),
        message: json['message'] as String? ?? '',
      );
}

/// One chat conversation as a participant sees it — mirrors backend
/// `ConversationRead` (Phase 8). The row stores no direction: "the other
/// user" is resolved relative to the caller.
class Conversation {
  const Conversation({
    required this.id,
    required this.otherUserId,
    required this.otherDisplayName,
    required this.status,
    required this.requestedByMe,
    required this.createdAt,
    required this.updatedAt,
  });

  final String id;
  final String otherUserId;
  final String otherDisplayName;
  final ConversationStatus status;
  final bool requestedByMe;
  final DateTime createdAt;
  final DateTime updatedAt;

  /// Accepted conversations are the ones you can actually message in.
  bool get isOpen => status == ConversationStatus.accepted;

  factory Conversation.fromJson(Map<String, dynamic> json) => Conversation(
        id: json['id'] as String,
        otherUserId: json['other_user_id'] as String,
        otherDisplayName: json['other_display_name'] as String,
        status: ConversationStatus.fromWire(json['status'] as String),
        requestedByMe: json['requested_by_me'] as bool,
        createdAt: DateTime.parse(json['created_at'] as String),
        updatedAt: DateTime.parse(json['updated_at'] as String),
      );
}

/// One message inside a conversation — mirrors backend `MessageRead`.
/// A soft-deleted message keeps its place with a null [body].
class ChatMessage {
  const ChatMessage({
    required this.id,
    required this.conversationId,
    required this.senderId,
    required this.mine,
    required this.body,
    required this.isDeleted,
    required this.createdAt,
  });

  final String id;
  final String conversationId;
  final String senderId;
  final bool mine;
  final String? body;
  final bool isDeleted;
  final DateTime createdAt;

  factory ChatMessage.fromJson(Map<String, dynamic> json) => ChatMessage(
        id: json['id'] as String,
        conversationId: json['conversation_id'] as String,
        senderId: json['sender_id'] as String,
        mine: json['mine'] as bool,
        body: json['body'] as String?,
        isDeleted: json['is_deleted'] as bool,
        createdAt: DateTime.parse(json['created_at'] as String),
      );
}

/// A discovery candidate: limited public travel profile + best plan +
/// compatibility score — mirrors backend `DiscoveryCandidateRead`.
/// Never carries email, phone, role or verification state.
class DiscoveryCandidate {
  const DiscoveryCandidate({
    required this.userId,
    required this.displayName,
    this.bio,
    this.homeRegion,
    this.languages,
    this.travelStyles,
    this.interests,
    this.groupSizePref,
    required this.destination,
    this.startDate,
    this.endDate,
    required this.compatibilityScore,
    required this.existingRequest,
  });

  final String userId;
  final String displayName;
  final String? bio;
  final String? homeRegion;
  final List<String>? languages;
  final List<String>? travelStyles;
  final List<String>? interests;
  final int? groupSizePref;
  final String destination;
  final DateTime? startDate;
  final DateTime? endDate;
  final int compatibilityScore;
  final String existingRequest; // none | pending_sent | pending_received

  factory DiscoveryCandidate.fromJson(Map<String, dynamic> json) {
    final plan = (json['plan'] as Map<String, dynamic>?) ?? const {};
    return DiscoveryCandidate(
      userId: json['user_id'] as String,
      displayName: json['display_name'] as String,
      bio: json['bio'] as String?,
      homeRegion: json['home_region'] as String?,
      languages: (json['languages'] as List<dynamic>?)
          ?.map((e) => e as String)
          .toList(),
      travelStyles: (json['travel_styles'] as List<dynamic>?)
          ?.map((e) => e as String)
          .toList(),
      interests: (json['interests'] as List<dynamic>?)
          ?.map((e) => e as String)
          .toList(),
      groupSizePref: json['group_size_pref'] as int?,
      destination: plan['destination'] as String? ?? '',
      startDate: plan['start_date'] == null
          ? null
          : DateTime.tryParse(plan['start_date'] as String),
      endDate: plan['end_date'] == null
          ? null
          : DateTime.tryParse(plan['end_date'] as String),
      compatibilityScore: json['compatibility_score'] as int? ?? 0,
      existingRequest: json['existing_request'] as String? ?? 'none',
    );
  }
}

/// A travel-buddy request between two users — mirrors backend
/// `BuddyRequestRead`.
class BuddyRequest {
  const BuddyRequest({
    required this.id,
    required this.requesterId,
    required this.requesterDisplayName,
    required this.recipientId,
    required this.recipientDisplayName,
    required this.status,
    required this.createdAt,
    this.planDestination,
  });

  final String id;
  final String requesterId;
  final String requesterDisplayName;
  final String recipientId;
  final String recipientDisplayName;
  final BuddyRequestStatus status;
  final DateTime createdAt;
  final String? planDestination;

  bool get isIncoming => status == BuddyRequestStatus.pending;

  factory BuddyRequest.fromJson(Map<String, dynamic> json) => BuddyRequest(
        id: json['id'] as String,
        requesterId: json['requester_id'] as String,
        requesterDisplayName: json['requester_display_name'] as String,
        recipientId: json['recipient_id'] as String,
        recipientDisplayName: json['recipient_display_name'] as String,
        status: BuddyRequestStatus.fromWire(json['status'] as String),
        createdAt: DateTime.parse(json['created_at'] as String),
        planDestination: json['plan_destination'] as String?,
      );
}

/// One blocked account as the blocker sees it — mirrors `BlockRead`.
class BlockedUser {
  const BlockedUser({
    required this.id,
    required this.blockedId,
    required this.blockedDisplayName,
    required this.createdAt,
  });

  final String id;
  final String blockedId;
  final String blockedDisplayName;
  final DateTime createdAt;

  factory BlockedUser.fromJson(Map<String, dynamic> json) => BlockedUser(
        id: json['id'] as String,
        blockedId: json['blocked_id'] as String,
        blockedDisplayName: json['blocked_display_name'] as String,
        createdAt: DateTime.parse(json['created_at'] as String),
      );
}

/// A community meetup / house party — mirrors backend `MeetupRead`
/// (Phase 9).
class Meetup {
  const Meetup({
    required this.id,
    required this.hostId,
    required this.hostDisplayName,
    required this.title,
    this.description,
    required this.category,
    required this.startAt,
    required this.endAt,
    required this.capacity,
    required this.approvedCount,
    required this.participation,
    required this.status,
    this.locationText,
    required this.myMembership,
    required this.kind,
  });

  final String id;
  final String hostId;
  final String hostDisplayName;
  final String title;
  final String? description;
  final MeetupCategory category;
  final DateTime startAt;
  final DateTime endAt;
  final int capacity;
  final int approvedCount;
  final String participation; // open | approval
  final MeetupStatus status;
  final String? locationText;
  final MembershipStatus myMembership;
  final String kind; // meetup | house_party

  bool get canJoin =>
      status == MeetupStatus.active &&
      myMembership != MembershipStatus.approved &&
      myMembership != MembershipStatus.requested &&
      approvedCount < capacity;

  factory Meetup.fromJson(Map<String, dynamic> json) => Meetup(
        id: json['id'] as String,
        hostId: json['host_id'] as String,
        hostDisplayName: json['host_display_name'] as String,
        title: json['title'] as String,
        description: json['description'] as String?,
        category: MeetupCategory.fromWire(json['category'] as String),
        startAt: DateTime.parse(json['start_at'] as String),
        endAt: DateTime.parse(json['end_at'] as String),
        capacity: json['capacity'] as int,
        approvedCount: json['approved_count'] as int,
        participation: json['participation'] as String? ?? 'open',
        status: MeetupStatus.fromWire(json['status'] as String),
        locationText: json['location_text'] as String?,
        myMembership: MembershipStatus.fromWire(
            json['my_membership'] as String? ?? 'none'),
        kind: json['kind'] as String? ?? 'meetup',
      );
}

/// One notification row — mirrors backend `NotificationRead` (Phase 11).
/// Also used for per-SOS contact-attempt rows.
class AppNotification {
  const AppNotification({
    required this.id,
    required this.kind,
    required this.title,
    required this.body,
    required this.channel,
    required this.status,
    required this.attempts,
    this.lastError,
    this.readAt,
    required this.createdAt,
  });

  final String id;
  final String kind;
  final String title;
  final String body;
  final String channel;
  final NotificationStatus status;
  final int attempts;
  final String? lastError;
  final DateTime? readAt;
  final DateTime createdAt;

  bool get isRead => readAt != null;

  factory AppNotification.fromJson(Map<String, dynamic> json) =>
      AppNotification(
        id: json['id'] as String,
        kind: json['kind'] as String? ?? '',
        title: json['title'] as String? ?? '',
        body: json['body'] as String? ?? '',
        channel: json['channel'] as String? ?? '',
        status: NotificationStatus.fromWire(
            json['status'] as String? ?? 'unknown'),
        attempts: json['attempts'] as int? ?? 0,
        lastError: json['last_error'] as String?,
        readAt: json['read_at'] == null
            ? null
            : DateTime.parse(json['read_at'] as String),
        createdAt: DateTime.parse(json['created_at'] as String),
      );
}

/// A shareable link to one of my travel plans — mirrors `TripShareRead`
/// (Phase 11). Anyone holding `shareUrl` can view the plan until
/// `expiresAt` (or until revoked).
class TripShare {
  const TripShare({
    required this.id,
    required this.shareUrl,
    required this.expiresAt,
    this.planId,
    this.planDestination,
    this.revokedAt,
    required this.createdAt,
  });

  final String id;
  final String shareUrl;
  final DateTime expiresAt;
  final String? planId;
  final String? planDestination;
  final DateTime? revokedAt;
  final DateTime createdAt;

  bool get isActive => revokedAt == null && DateTime.now().isBefore(expiresAt);

  factory TripShare.fromJson(Map<String, dynamic> json) => TripShare(
        id: json['id'] as String,
        shareUrl: json['share_url'] as String? ?? '',
        expiresAt: DateTime.parse(json['expires_at'] as String),
        planId: json['plan_id'] as String?,
        planDestination: json['plan_destination'] as String?,
        revokedAt: json['revoked_at'] == null
            ? null
            : DateTime.parse(json['revoked_at'] as String),
        createdAt: DateTime.parse(json['created_at'] as String),
      );
}

/// Someone else's plan shared with me — mirrors `SharedItineraryRead`.
class SharedItinerary {
  const SharedItinerary({
    required this.id,
    required this.ownerDisplayName,
    required this.shareUrl,
    required this.expiresAt,
    this.planDestination,
    this.revokedAt,
    required this.createdAt,
  });

  final String id;
  final String ownerDisplayName;
  final String shareUrl;
  final DateTime expiresAt;
  final String? planDestination;
  final DateTime? revokedAt;
  final DateTime createdAt;

  bool get isActive => revokedAt == null && DateTime.now().isBefore(expiresAt);

  factory SharedItinerary.fromJson(Map<String, dynamic> json) =>
      SharedItinerary(
        id: json['id'] as String,
        ownerDisplayName: json['owner_display_name'] as String? ?? 'Someone',
        shareUrl: json['share_url'] as String? ?? '',
        expiresAt: DateTime.parse(json['expires_at'] as String),
        planDestination: json['plan_destination'] as String?,
        revokedAt: json['revoked_at'] == null
            ? null
            : DateTime.parse(json['revoked_at'] as String),
        createdAt: DateTime.parse(json['created_at'] as String),
      );
}

/// AI companion configuration state — `GET /ai/status` (Phase 13).
/// `configured` is a boolean: the API never returns the key itself.
class AiStatus {
  const AiStatus({required this.provider, required this.configured});

  final String provider;
  final bool configured;

  factory AiStatus.fromJson(Map<String, dynamic> json) => AiStatus(
        provider: json['provider'] as String? ?? 'unavailable',
        configured: json['configured'] as bool? ?? false,
      );
}

/// One AI answer — `POST /ai/chat` (Phase 13). `verified` is false when
/// the provider is unconfigured; the UI must show the honesty footer.
class AiAnswer {
  const AiAnswer({
    required this.answer,
    required this.verified,
    this.honestyFooter,
    this.emergencyFooter,
    required this.generatedAt,
  });

  final String answer;
  final bool verified;
  final String? honestyFooter;
  final String? emergencyFooter;
  final DateTime generatedAt;

  factory AiAnswer.fromJson(Map<String, dynamic> json) => AiAnswer(
        answer: json['answer'] as String? ?? '',
        verified: json['verified'] as bool? ?? false,
        honestyFooter: json['honesty_footer'] as String?,
        emergencyFooter: json['emergency_footer'] as String?,
        generatedAt: json['generated_at'] == null
            ? DateTime.now().toUtc()
            : DateTime.parse(json['generated_at'] as String),
      );
}
