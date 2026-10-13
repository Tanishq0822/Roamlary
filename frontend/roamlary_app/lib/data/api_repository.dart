import 'dart:convert';

import 'package:http/http.dart' as http;

import '../core/config.dart';
import '../models/enums.dart';
import '../models/models.dart';
import 'app_repository.dart';

/// Thrown when the backend returns a non-2xx response. Carries the status code
/// and, when present, the FastAPI `detail` message.
class ApiException implements Exception {
  ApiException(this.statusCode, this.message);
  final int statusCode;
  final String message;

  @override
  String toString() => 'ApiException($statusCode): $message';
}

/// Real [AppRepository] backed by the FastAPI backend at `/api/v1`.
///
/// Every path and payload below was verified against `backend/app/api/v1/`.
/// Wire field names (snake_case) are parsed explicitly in the models, so no
/// codegen is required. Requests beyond 2xx throw [ApiException] carrying the
/// FastAPI `detail` string when available.
///
/// NOTE: this is unused while `AppConfig.useMocks` is true, but it is kept
/// compile-clean and contract-correct so integration is a one-line flip.
class ApiRepository implements AppRepository {
  ApiRepository({http.Client? client, String? baseUrl})
      : _client = client ?? http.Client(),
        _baseUrl = baseUrl ?? AppConfig.apiBaseUrl;

  final http.Client _client;
  final String _baseUrl;
  String? _token;

  void setToken(String? token) => _token = token;

  Uri _uri(String path, [Map<String, dynamic>? query]) {
    final normalized = path.startsWith('/') ? path : '/$path';
    final base = Uri.parse('$_baseUrl$normalized');
    if (query == null || query.isEmpty) return base;
    // Build the query by hand so a value may be a String OR a List of
    // Strings (repeated params, e.g. `interests=a&interests=b`), which
    // FastAPI parses into list-valued Query params.
    final parts = <String>[];
    query.forEach((key, value) {
      final values = value is Iterable && value is! String
          ? value
          : <Object?>[value];
      for (final v in values) {
        if (v == null) continue;
        parts.add(
          '${Uri.encodeQueryComponent(key)}=${Uri.encodeQueryComponent('$v')}',
        );
      }
    });
    if (parts.isEmpty) return base;
    return Uri.parse('$base?${parts.join('&')}');
  }

  Map<String, String> _headers({bool auth = true}) {
    return <String, String>{
      'Content-Type': 'application/json',
      if (auth && _token != null) 'Authorization': 'Bearer $_token',
    };
  }

  Future<dynamic> _send(
    String method,
    String path, {
    Map<String, dynamic>? query,
    Object? body,
    bool auth = true,
  }) async {
    final uri = _uri(path, query);
    final encoded = body == null ? null : jsonEncode(body);
    final request = http.Request(method, uri);
    request.headers.addAll(_headers(auth: auth));
    if (encoded != null) {
      request.body = encoded;
    }
    final streamed =
        await _client.send(request).timeout(const Duration(seconds: 20));
    final response = await http.Response.fromStream(streamed);

    if (response.body.isEmpty) {
      if (_success(response.statusCode)) return null;
      throw ApiException(response.statusCode, 'Request failed');
    }

    dynamic decoded;
    try {
      decoded = jsonDecode(response.body);
    } catch (_) {
      decoded = null;
    }

    if (!_success(response.statusCode)) {
      var message = 'Request failed (${response.statusCode})';
      if (decoded is Map && decoded['detail'] is String) {
        message = decoded['detail'] as String;
      }
      throw ApiException(response.statusCode, message);
    }
    return decoded;
  }

  static bool _success(int code) => code >= 200 && code < 300;

  // Auth -------------------------------------------------------------------
  @override
  Future<AuthSession> register({
    required String displayName,
    required String email,
    required String password,
  }) async {
    final token = await _send(
      'POST',
      '/auth/register',
      body: {
        'display_name': displayName,
        'email': email,
        'password': password,
      },
      auth: false,
    ) as Map<String, dynamic>;
    _token = token['access_token'] as String;
    final profile = await me();
    return AuthSession(token: _token!, profile: profile);
  }

  @override
  Future<AuthSession> login({
    required String email,
    required String password,
  }) async {
    final token = await _send(
      'POST',
      '/auth/login',
      body: {'email': email, 'password': password},
      auth: false,
    ) as Map<String, dynamic>;
    _token = token['access_token'] as String;
    final profile = await me();
    return AuthSession(token: _token!, profile: profile);
  }

  @override
  Future<UserProfile> me() async {
    final data =
        await _send('GET', '/users/me') as Map<String, dynamic>;
    return UserProfile.fromJson(data);
  }

  // Contacts ---------------------------------------------------------------
  @override
  Future<List<TrustedContact>> listContacts() async {
    final data = await _send('GET', '/trusted-contacts/') as List<dynamic>;
    return data
        .map((e) => TrustedContact.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  @override
  Future<TrustedContact> createContact({
    required String name,
    required String phone,
    String? relationship,
    String? email,
  }) async {
    final data = await _send(
      'POST',
      '/trusted-contacts/',
      body: {
        'name': name,
        'phone': phone,
        'relationship': ?relationship,
        'email': ?email,
      },
    ) as Map<String, dynamic>;
    return TrustedContact.fromJson(data);
  }

  @override
  Future<void> deleteContact(String id) async {
    await _send('DELETE', '/trusted-contacts/$id');
  }

  // Check-ins --------------------------------------------------------------
  @override
  Future<List<CheckIn>> listCheckIns({CheckInStatus? status}) async {
    final data = await _send(
      'GET',
      '/check-ins/',
      query: status == null ? null : {'status': status.wire},
    ) as List<dynamic>;
    return data
        .map((e) => CheckIn.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  @override
  Future<CheckIn> createCheckIn({String? note, DateTime? dueAt}) async {
    final data = await _send(
      'POST',
      '/check-ins/',
      body: {
        'note': ?note,
        'due_at': ?dueAt?.toUtc().toIso8601String(),
      },
    ) as Map<String, dynamic>;
    return CheckIn.fromJson(data);
  }

  @override
  Future<CheckIn> completeCheckIn(String id) async {
    final data = await _send('POST', '/check-ins/$id/complete')
        as Map<String, dynamic>;
    return CheckIn.fromJson(data);
  }

  @override
  Future<CheckIn> updateCheckInStatus(String id, CheckInStatus status) async {
    final data = await _send(
      'PATCH',
      '/check-ins/$id',
      body: {'status': status.wire},
    ) as Map<String, dynamic>;
    return CheckIn.fromJson(data);
  }

  @override
  Future<CheckIn> updateCheckInNote(String id, {required String note}) async {
    final data = await _send(
      'PATCH',
      '/check-ins/$id',
      body: {'note': note},
    ) as Map<String, dynamic>;
    return CheckIn.fromJson(data);
  }

  // SOS --------------------------------------------------------------------
  @override
  Future<List<SosEvent>> listSosEvents() async {
    final data = await _send('GET', '/sos') as List<dynamic>;
    return data
        .map((e) => SosEvent.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  @override
  Future<SosEvent> createSos({
    String? description,
    double? latitude,
    double? longitude,
  }) async {
    final data = await _send(
      'POST',
      '/sos',
      body: {
        'description': ?description,
        'latitude': ?latitude,
        'longitude': ?longitude,
      },
    ) as Map<String, dynamic>;
    return SosEvent.fromJson(data);
  }

  @override
  Future<SosEvent> cancelSos(String id) async {
    final data = await _send('POST', '/sos/$id/cancel') as Map<String, dynamic>;
    return SosEvent.fromJson(data);
  }

  @override
  Future<SosEvent> resolveSos(String id) async {
    final data =
        await _send('POST', '/sos/$id/resolve') as Map<String, dynamic>;
    return SosEvent.fromJson(data);
  }

  // Reports ----------------------------------------------------------------
  @override
  Future<List<CommunityReport>> listReports({
    ReportCategory? category,
    int offset = 0,
    int limit = 20,
  }) async {
    final data = await _send(
      'GET',
      '/reports',
      query: {
        if (category != null) 'category': category.wire,
        'offset': '$offset',
        'limit': '$limit',
      },
    ) as List<dynamic>;
    return data
        .map((e) => CommunityReport.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  @override
  Future<CommunityReport> createReport({
    required ReportCategory category,
    required String description,
    required double latitude,
    required double longitude,
  }) async {
    final data = await _send(
      'POST',
      '/reports',
      body: {
        'category': category.wire,
        'description': description,
        'latitude': latitude,
        'longitude': longitude,
      },
    ) as Map<String, dynamic>;
    return CommunityReport.fromJson(data);
  }

  // Verification & social (Phase 6, second assignment) ----------------------
  @override
  Future<VerificationStatusInfo> verificationStatus() async {
    final data =
        await _send('GET', '/verification/status') as Map<String, dynamic>;
    return VerificationStatusInfo.fromJson(data);
  }

  @override
  Future<VerificationRequest> submitVerificationRequest({String? note}) async {
    final data = await _send(
      'POST',
      '/verification/requests',
      body: {'note': ?note},
    ) as Map<String, dynamic>;
    return VerificationRequest.fromJson(data);
  }

  @override
  Future<DiscoveryResult> discovery() async {
    try {
      final data =
          await _send('GET', '/social/discovery') as Map<String, dynamic>;
      return DiscoveryResult.fromJson(data);
    } on ApiException catch (e) {
      // The gate answers 403 for unverified accounts while the policy
      // requires verification - translate to the shared gate exception.
      if (e.statusCode == 403) {
        throw const SocialGateDeniedException();
      }
      rethrow;
    }
  }

  @override
  Future<List<VerificationRequestReview>> listVerificationRequests({
    VerificationRequestStatus? status,
  }) async {
    final data = await _send(
      'GET',
      '/admin/verification-requests',
      query: {
        if (status != null) 'status': status.wire,
        'offset': '0',
        'limit': '100',
      },
    ) as List<dynamic>;
    return data
        .map((e) => VerificationRequestReview.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  @override
  Future<VerificationRequestReview> approveVerificationRequest(
    String id, {
    String? reviewNote,
  }) async {
    final data = await _send(
      'POST',
      '/admin/verification-requests/$id/approve',
      body: {'review_note': ?reviewNote},
    ) as Map<String, dynamic>;
    return VerificationRequestReview.fromJson(data);
  }

  @override
  Future<VerificationRequestReview> rejectVerificationRequest(
    String id, {
    String? reviewNote,
  }) async {
    final data = await _send(
      'POST',
      '/admin/verification-requests/$id/reject',
      body: {'review_note': ?reviewNote},
    ) as Map<String, dynamic>;
    return VerificationRequestReview.fromJson(data);
  }

  @override
  Future<SocialPolicy> getSocialPolicy() async {
    final data = await _send('GET', '/admin/policy/social-verification')
        as Map<String, dynamic>;
    return SocialPolicy.fromJson(data);
  }

  @override
  Future<SocialPolicy> setSocialPolicy({
    required bool requiresVerification,
  }) async {
    final data = await _send(
      'PATCH',
      '/admin/policy/social-verification',
      body: {'requires_verification': requiresVerification},
    ) as Map<String, dynamic>;
    return SocialPolicy.fromJson(data);
  }

  // Chat (Phase 8) ----------------------------------------------------------
  @override
  Future<List<DiscoveryCandidate>> discover({
    int offset = 0,
    int limit = 20,
  }) async {
    try {
      final data = await _send(
        'GET',
        '/travel-buddies/discover',
        query: {'offset': '$offset', 'limit': '$limit'},
      ) as Map<String, dynamic>;
      return (data['results'] as List<dynamic>? ?? const [])
          .map((e) =>
              DiscoveryCandidate.fromJson(e as Map<String, dynamic>))
          .toList();
    } on ApiException catch (e) {
      if (e.statusCode == 403) throw const SocialGateDeniedException();
      rethrow;
    }
  }

  @override
  Future<List<Conversation>> listConversations() async {
    final data = await _send('GET', '/chat/conversations')
        as Map<String, dynamic>;
    return (data['results'] as List<dynamic>? ?? const [])
        .map((e) => Conversation.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  @override
  Future<List<Conversation>> listChatRequests({
    required String direction,
  }) async {
    final data = await _send(
      'GET',
      '/chat/requests',
      query: {'direction': direction},
    ) as Map<String, dynamic>;
    return (data['results'] as List<dynamic>? ?? const [])
        .map((e) => Conversation.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  @override
  Future<void> sendChatRequest({required String recipientId}) async {
    await _send('POST', '/chat/requests', body: {'recipient_id': recipientId});
  }

  @override
  Future<Conversation> acceptChatRequest(String id) async {
    final data =
        await _send('POST', '/chat/requests/$id/accept') as Map<String, dynamic>;
    return Conversation.fromJson(data);
  }

  @override
  Future<void> rejectChatRequest(String id) async {
    await _send('POST', '/chat/requests/$id/reject');
  }

  @override
  Future<void> cancelChatRequest(String id) async {
    await _send('POST', '/chat/requests/$id/cancel');
  }

  @override
  Future<List<ChatMessage>> listMessages(String conversationId) async {
    final data = await _send(
      'GET',
      '/chat/conversations/$conversationId/messages',
      query: {'limit': '100'},
    ) as Map<String, dynamic>;
    return (data['results'] as List<dynamic>? ?? const [])
        .map((e) => ChatMessage.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  @override
  Future<ChatMessage> sendMessage(String conversationId, String body) async {
    final data = await _send(
      'POST',
      '/chat/conversations/$conversationId/messages',
      body: {'body': body},
    ) as Map<String, dynamic>;
    return ChatMessage.fromJson(data);
  }

  // Travel-buddy requests (Phase 7) ------------------------------------------
  @override
  Future<List<BuddyRequest>> listBuddyRequests({
    required String direction,
  }) async {
    final data = await _send(
      'GET',
      '/travel-buddies/requests',
      query: {'direction': direction, 'limit': '50'},
    ) as Map<String, dynamic>;
    return (data['results'] as List<dynamic>? ?? const [])
        .map((e) => BuddyRequest.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  @override
  Future<void> sendBuddyRequest({
    required String recipientId,
    String? planId,
  }) async {
    await _send('POST', '/travel-buddies/requests', body: {
      'recipient_id': recipientId,
      'plan_id': ?planId,
    });
  }

  @override
  Future<BuddyRequest> acceptBuddyRequest(String id) async {
    final data = await _send('POST', '/travel-buddies/requests/$id/accept')
        as Map<String, dynamic>;
    return BuddyRequest.fromJson(data);
  }

  @override
  Future<void> rejectBuddyRequest(String id) async {
    await _send('POST', '/travel-buddies/requests/$id/reject');
  }

  // Blocking ----------------------------------------------------------------
  @override
  Future<List<BlockedUser>> listBlocks() async {
    final data = await _send('GET', '/blocks') as Map<String, dynamic>;
    return (data['blocks'] as List<dynamic>? ?? const [])
        .map((e) => BlockedUser.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  @override
  Future<void> blockUser(String blockedId) async {
    await _send('POST', '/blocks', body: {'blocked_id': blockedId});
  }

  @override
  Future<void> unblockUser(String blockedId) async {
    await _send('DELETE', '/blocks/$blockedId');
  }

  // SOS workflow (Phase 10) --------------------------------------------------
  @override
  Future<SosEvent> acknowledgeSos(String id) async {
    final data = await _send('POST', '/sos/$id/acknowledge')
        as Map<String, dynamic>;
    return SosEvent.fromJson(data);
  }

  @override
  Future<List<AppNotification>> retrySosNotifications(String id) async {
    final data = await _send('POST', '/sos/$id/notify-retry') as List<dynamic>;
    return data
        .map((e) => AppNotification.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  @override
  Future<List<AppNotification>> listSosNotifications(String id) async {
    final data = await _send('GET', '/sos/$id/notifications') as List<dynamic>;
    return data
        .map((e) => AppNotification.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  // Check-ins: overdue view (Phase 12) ---------------------------------------
  @override
  Future<List<CheckIn>> listOverdueCheckIns() async {
    final data = await _send('GET', '/check-ins/overdue') as List<dynamic>;
    return data
        .map((e) => CheckIn.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  // Meetups & house parties (Phase 9) ----------------------------------------
  @override
  Future<List<Meetup>> listMeetups() async {
    final data = await _send('GET', '/meetups', query: {'limit': '50'})
        as Map<String, dynamic>;
    return (data['results'] as List<dynamic>? ?? const [])
        .map((e) => Meetup.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  @override
  Future<Meetup> createMeetup({
    required String title,
    String? description,
    required MeetupCategory category,
    required DateTime startAt,
    required DateTime endAt,
    String? locationText,
    int capacity = 20,
  }) async {
    final data = await _send(
      'POST',
      '/meetups',
      body: {
        'title': title,
        'description': ?description,
        'category': category.wire,
        'start_at': startAt.toUtc().toIso8601String(),
        'end_at': endAt.toUtc().toIso8601String(),
        'capacity': capacity,
        'location_text': ?locationText,
      },
    ) as Map<String, dynamic>;
    return Meetup.fromJson(data);
  }

  @override
  Future<void> joinMeetup(String id) async {
    await _send('POST', '/meetups/$id/join');
  }

  @override
  Future<void> leaveMeetup(String id) async {
    await _send('POST', '/meetups/$id/leave');
  }

  @override
  Future<void> cancelMeetup(String id) async {
    await _send('POST', '/meetups/$id/cancel');
  }

  // House-party invitations (Phase 10) ----------------------------------------
  @override
  Future<List<Invitation>> listInvitations({int offset = 0, int limit = 20}) async {
    final data = await _send(
      'GET',
      '/invitations',
      query: {'offset': '$offset', 'limit': '$limit'},
    ) as Map<String, dynamic>;
    return (data['results'] as List<dynamic>? ?? const [])
        .map((e) => Invitation.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  @override
  Future<Invitation> acceptInvitation(String id) async {
    final data = await _send('POST', '/invitations/$id/accept')
        as Map<String, dynamic>;
    return Invitation.fromJson(data);
  }

  @override
  Future<Invitation> declineInvitation(String id) async {
    final data = await _send('POST', '/invitations/$id/decline')
        as Map<String, dynamic>;
    return Invitation.fromJson(data);
  }

  // Notifications inbox (Phase 11) --------------------------------------------
  @override
  Future<List<AppNotification>> listNotifications() async {
    final data = await _send(
      'GET',
      '/notifications',
      query: {'limit': '50'},
    ) as Map<String, dynamic>;
    return (data['results'] as List<dynamic>? ?? const [])
        .map((e) => AppNotification.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  @override
  Future<void> markNotificationRead(String id) async {
    await _send('POST', '/notifications/$id/read');
  }

  // Trip sharing (Phase 11) ---------------------------------------------------
  @override
  Future<List<TripShare>> listTripShares() async {
    final data =
        await _send('GET', '/trip-shares', query: {'limit': '50'})
            as Map<String, dynamic>;
    return (data['results'] as List<dynamic>? ?? const [])
        .map((e) => TripShare.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  @override
  Future<TripShare> createTripShare({
    String? planId,
    required DateTime expiresAt,
  }) async {
    final data = await _send(
      'POST',
      '/trip-shares',
      body: {
        'plan_id': ?planId,
        'expires_at': expiresAt.toUtc().toIso8601String(),
      },
    ) as Map<String, dynamic>;
    return TripShare.fromJson(data);
  }

  @override
  Future<void> revokeTripShare(String id) async {
    await _send('DELETE', '/trip-shares/$id');
  }

  @override
  Future<List<SharedItinerary>> listSharedWithMe() async {
    final data = await _send(
      'GET',
      '/trip-shares/shared-with-me',
      query: {'limit': '50'},
    ) as Map<String, dynamic>;
    return (data['results'] as List<dynamic>? ?? const [])
        .map((e) => SharedItinerary.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  // AI companion (Phase 13) ----------------------------------------------------
  @override
  Future<AiStatus> aiStatus() async {
    final data = await _send('GET', '/ai/status') as Map<String, dynamic>;
    return AiStatus.fromJson(data);
  }

  @override
  Future<AiAnswer> askAi(String message) async {
    try {
      final data = await _send(
        'POST',
        '/ai/chat',
        body: {'message': message},
      ) as Map<String, dynamic>;
      return AiAnswer.fromJson(data);
    } on ApiException catch (e) {
      // The chat gate answers 403 for unverified accounts.
      if (e.statusCode == 403) throw const SocialGateDeniedException();
      rethrow;
    }
  }

  // Filtered discovery ---------------------------------------------------------
  @override
  Future<List<DiscoveryCandidate>> discoverFiltered({
    String? destination,
    String? travelStyle,
    String? language,
    List<String> interests = const [],
    int minScore = 0,
    int limit = 20,
  }) async {
    try {
      final data = await _send(
        'GET',
        '/travel-buddies/discover',
        query: {
          if (destination != null && destination.isNotEmpty)
            'destination': destination,
          if (travelStyle != null && travelStyle.isNotEmpty)
            'travel_style': travelStyle,
          if (language != null && language.isNotEmpty) 'language': language,
          if (interests.isNotEmpty) 'interests': interests,
          'min_score': '$minScore',
          'offset': '0',
          'limit': '$limit',
        },
      ) as Map<String, dynamic>;
      return (data['results'] as List<dynamic>? ?? const [])
          .map((e) => DiscoveryCandidate.fromJson(e as Map<String, dynamic>))
          .toList();
    } on ApiException catch (e) {
      if (e.statusCode == 403) throw const SocialGateDeniedException();
      rethrow;
    }
  }

  // Health -----------------------------------------------------------------
  @override
  Future<bool> health() async {
    try {
      final data =
          await _send('GET', '/health', auth: false) as Map<String, dynamic>;
      return data['status'] == 'ok';
    } catch (_) {
      return false;
    }
  }
}
