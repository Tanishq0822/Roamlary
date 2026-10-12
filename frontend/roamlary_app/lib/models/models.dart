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

  bool get isActive => status == SosStatus.active;

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
