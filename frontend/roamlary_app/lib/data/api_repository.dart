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

  Uri _uri(String path, [Map<String, String>? query]) {
    final normalized = path.startsWith('/') ? path : '/$path';
    return Uri.parse('$_baseUrl$normalized').replace(queryParameters: query);
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
    Map<String, String>? query,
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
        if (relationship != null) 'relationship': relationship,
        if (email != null) 'email': email,
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
        if (note != null) 'note': note,
        if (dueAt != null) 'due_at': dueAt.toUtc().toIso8601String(),
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
        if (description != null) 'description': description,
        if (latitude != null) 'latitude': latitude,
        if (longitude != null) 'longitude': longitude,
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
