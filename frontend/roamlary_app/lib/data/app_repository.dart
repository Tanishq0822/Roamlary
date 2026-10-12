import '../models/models.dart';

/// Auth token + profile bundle returned by sign-in / register.
class AuthSession {
  const AuthSession({required this.token, required this.profile});
  final String token;
  final UserProfile profile;
}

/// Data-access contract used by the UI.
///
/// The UI only ever talks to this interface, never to a concrete backend, so
/// swapping the mock for the real FastAPI service is a one-line change at the
/// composition root (see `lib/core/di.dart`). Method names and argument shapes
/// mirror the verified backend endpoints under `/api/v1`.
abstract class AppRepository {
  // Auth -------------------------------------------------------------------
  Future<AuthSession> register({
    required String displayName,
    required String email,
    required String password,
  });
  Future<AuthSession> login({required String email, required String password});
  Future<UserProfile> me();

  // Trusted contacts -------------------------------------------------------
  Future<List<TrustedContact>> listContacts();
  Future<TrustedContact> createContact({
    required String name,
    required String phone,
    String? relationship,
    String? email,
  });
  Future<void> deleteContact(String id);

  // Check-ins --------------------------------------------------------------
  Future<List<CheckIn>> listCheckIns({CheckInStatus? status});
  Future<CheckIn> createCheckIn({String? note, DateTime? dueAt});
  Future<CheckIn> completeCheckIn(String id);
  Future<CheckIn> updateCheckInStatus(String id, CheckInStatus status);

  // SOS --------------------------------------------------------------------
  Future<List<SosEvent>> listSosEvents();
  Future<SosEvent> createSos({String? description, double? latitude, double? longitude});
  Future<SosEvent> cancelSos(String id);
  Future<SosEvent> resolveSos(String id);

  // Community reports ------------------------------------------------------
  Future<List<CommunityReport>> listReports({ReportCategory? category, int offset = 0, int limit = 20});
  Future<CommunityReport> createReport({
    required ReportCategory category,
    required String description,
    required double latitude,
    required double longitude,
  });

  // Health -----------------------------------------------------------------
  Future<bool> health();
}
