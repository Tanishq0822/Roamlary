import 'enums.dart';

// Re-export the enums so every file that imports the models barrel also
// sees CheckInStatus / SosStatus / ReportCategory (app_repository.dart
// needs them for its method signatures).
export 'enums.dart';

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
