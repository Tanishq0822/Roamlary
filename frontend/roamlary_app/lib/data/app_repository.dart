import '../models/enums.dart';
import '../models/models.dart';

/// Auth token + profile bundle returned by sign-in / register.
class AuthSession {
  const AuthSession({required this.token, required this.profile});
  final String token;
  final UserProfile profile;
}

/// Thrown when the identity-verification gate denies social access (the
/// backend's HTTP 403 for unverified accounts). Both data sources raise
/// this so the UI renders one gate screen regardless of which is active.
class SocialGateDeniedException implements Exception {
  const SocialGateDeniedException();

  @override
  String toString() => 'Verification is required for social access.';
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

  // Verification & social (Phase 6, second assignment) ----------------------
  Future<VerificationStatusInfo> verificationStatus();
  Future<VerificationRequest> submitVerificationRequest({String? note});
  Future<DiscoveryResult> discovery();

  // Owner-only review + policy (the backend answers 403 for ordinary
  // accounts on every method below - the UI just surfaces that honestly).
  Future<List<VerificationRequestReview>> listVerificationRequests({
    VerificationRequestStatus? status,
  });
  Future<VerificationRequestReview> approveVerificationRequest(
    String id, {
    String? reviewNote,
  });
  Future<VerificationRequestReview> rejectVerificationRequest(
    String id, {
    String? reviewNote,
  });
  Future<SocialPolicy> getSocialPolicy();
  Future<SocialPolicy> setSocialPolicy({required bool requiresVerification});

  // Chat: discover -> request -> accepted conversation -> messages --------
  Future<List<DiscoveryCandidate>> discover({int offset = 0, int limit = 20});
  Future<List<Conversation>> listConversations();
  Future<List<Conversation>> listChatRequests({required String direction});
  Future<void> sendChatRequest({required String recipientId});
  Future<Conversation> acceptChatRequest(String id);
  Future<void> rejectChatRequest(String id);
  Future<void> cancelChatRequest(String id);
  Future<List<ChatMessage>> listMessages(String conversationId);
  Future<ChatMessage> sendMessage(String conversationId, String body);

  // Travel-buddy (connect) requests ---------------------------------------
  Future<List<BuddyRequest>> listBuddyRequests({required String direction});
  Future<void> sendBuddyRequest({required String recipientId, String? planId});
  Future<BuddyRequest> acceptBuddyRequest(String id);
  Future<void> rejectBuddyRequest(String id);

  // Blocking (safety switch) ----------------------------------------------
  Future<List<BlockedUser>> listBlocks();
  Future<void> blockUser(String blockedId);
  Future<void> unblockUser(String blockedId);

  // Health -----------------------------------------------------------------
  Future<bool> health();
}
