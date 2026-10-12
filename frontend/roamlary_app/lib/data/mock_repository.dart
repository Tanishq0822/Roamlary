import 'dart:math';

import '../models/enums.dart';
import '../models/models.dart';
import 'app_repository.dart';

/// In-memory [AppRepository] backed by seeded demo data.
///
/// This is the DEFAULT data source so the app is fully explorable without a
/// running backend — ideal for a hackathon demo. It reproduces the backend's
/// observable behaviour where it matters (statuses, timestamps, ownership) but
/// is deliberately not a byte-for-byte validator. Small artificial latencies
/// make loading states visible in the UI.
class MockRepository implements AppRepository {
  MockRepository() {
    _seed();
  }

  final _rng = Random(42);
  final String _userId = 'u-demo-0001';
  String _token = 'mock-token';

  // Mutable stores.
  final List<TrustedContact> _contacts = [];
  final List<CheckIn> _checkIns = [];
  final List<SosEvent> _sos = [];
  final List<CommunityReport> _reports = [];
  final List<VerificationRequestReview> _reviewQueue = [];
  VerificationStatus _verificationStatus = VerificationStatus.unverified;
  VerificationRequest? _latestRequest;
  bool _socialRequiresVerification = true;

  UserProfile _profile = UserProfile(
    id: 'u-demo-0001',
    displayName: 'Demo Traveller',
    email: 'demo@roamlary.app',
    createdAt: DateTime.utc(2026, 1, 1),
    updatedAt: DateTime.utc(2026, 1, 1),
  );

  int _seq = 100;
  String _nextId(String prefix) => '$prefix-${_seq++}';

  Future<void> _delay([int ms = 350]) =>
      Future<void>.delayed(Duration(milliseconds: ms));

  void _seed() {
    final now = DateTime.now().toUtc();

    _contacts.addAll([
      TrustedContact(
        id: _nextId('tc'),
        userId: _userId,
        name: 'Aarav Sharma',
        phone: '+919876543210',
        relationship: 'Brother',
        email: 'aarav@example.com',
        createdAt: now.subtract(const Duration(days: 12)),
        updatedAt: now.subtract(const Duration(days: 12)),
      ),
      TrustedContact(
        id: _nextId('tc'),
        userId: _userId,
        name: 'Meera Patel',
        phone: '+919812345678',
        relationship: 'Friend',
        createdAt: now.subtract(const Duration(days: 5)),
        updatedAt: now.subtract(const Duration(days: 5)),
      ),
    ]);

    _checkIns.addAll([
      CheckIn(
        id: _nextId('ci'),
        userId: _userId,
        status: CheckInStatus.pending,
        note: 'Night walk along Marine Drive — back by 10 PM',
        dueAt: now.add(const Duration(hours: 3)),
        createdAt: now.subtract(const Duration(hours: 1)),
        updatedAt: now.subtract(const Duration(hours: 1)),
      ),
      CheckIn(
        id: _nextId('ci'),
        userId: _userId,
        status: CheckInStatus.safe,
        note: 'Airport transfer',
        completedAt: now.subtract(const Duration(days: 1)),
        createdAt: now.subtract(const Duration(days: 1, hours: 2)),
        updatedAt: now.subtract(const Duration(days: 1)),
      ),
    ]);

    _sos.add(
      SosEvent(
        id: _nextId('sos'),
        userId: _userId,
        status: SosStatus.resolved,
        description: 'Test drill — resolved.',
        latitude: 19.0760,
        longitude: 72.8777,
        locationRecordedAt: now.subtract(const Duration(days: 2)),
        createdAt: now.subtract(const Duration(days: 2)),
        updatedAt: now.subtract(const Duration(days: 2)),
        resolvedAt: now.subtract(const Duration(days: 2, minutes: -4)),
      ),
    );

    _reports.addAll([
      CommunityReport(
        id: _nextId('rep'),
        category: ReportCategory.poorLighting,
        status: ReportStatus.pending,
        description: 'Dark stretch behind the station, several lamps broken.',
        latitude: 19.0760,
        longitude: 72.8777,
        createdAt: now.subtract(const Duration(hours: 6)),
        updatedAt: now.subtract(const Duration(hours: 6)),
      ),
      CommunityReport(
        id: _nextId('rep'),
        category: ReportCategory.suspiciousActivity,
        status: ReportStatus.approved,
        description: 'Group loitering near the pier entrance after midnight.',
        latitude: 18.9220,
        longitude: 72.8347,
        createdAt: now.subtract(const Duration(days: 1)),
        updatedAt: now.subtract(const Duration(days: 1)),
      ),
      CommunityReport(
        id: _nextId('rep'),
        category: ReportCategory.roadHazard,
        status: ReportStatus.pending,
        description: 'Deep pothole in the left lane, easy to miss at night.',
        latitude: 19.0896,
        longitude: 72.8656,
        createdAt: now.subtract(const Duration(days: 2)),
        updatedAt: now.subtract(const Duration(days: 2)),
      ),
    ]);

    // Verification queue (Phase 6b) — OTHER applicants only: the demo
    // account may not review its own request, exactly like the backend.
    _reviewQueue.addAll([
      VerificationRequestReview(
        id: _nextId('ver'),
        userId: 'u-demo-0002',
        displayName: 'Ananya Iyer',
        status: VerificationRequestStatus.pending,
        createdAt: now.subtract(const Duration(hours: 4)),
        applicantNote: 'Need social features for a group trip to Leh.',
      ),
      VerificationRequestReview(
        id: _nextId('ver'),
        userId: 'u-demo-0003',
        displayName: 'Rahul Verma',
        status: VerificationRequestStatus.approved,
        createdAt: now.subtract(const Duration(days: 3)),
        reviewedAt: now.subtract(const Duration(days: 2)),
        reviewedBy: _userId,
        applicantNote: 'Frequent solo traveller — happy to be reviewed.',
      ),
    ]);
  }

  // Auth -------------------------------------------------------------------
  @override
  Future<AuthSession> register({
    required String displayName,
    required String email,
    required String password,
  }) async {
    await _delay(600);
    _profile = UserProfile(
      id: _userId,
      displayName: displayName,
      email: email,
      createdAt: DateTime.now().toUtc(),
      updatedAt: DateTime.now().toUtc(),
    );
    _token = 'mock-token-${_rng.nextInt(1 << 30)}';
    return AuthSession(token: _token, profile: _profile);
  }

  @override
  Future<AuthSession> login({
    required String email,
    required String password,
  }) async {
    await _delay(600);
    _token = 'mock-token-${_rng.nextInt(1 << 30)}';
    return AuthSession(token: _token, profile: _profile);
  }

  @override
  Future<UserProfile> me() async {
    await _delay(150);
    return _profile;
  }

  // Contacts ---------------------------------------------------------------
  @override
  Future<List<TrustedContact>> listContacts() async {
    await _delay();
    return List.unmodifiable(_contacts);
  }

  @override
  Future<TrustedContact> createContact({
    required String name,
    required String phone,
    String? relationship,
    String? email,
  }) async {
    await _delay(500);
    final now = DateTime.now().toUtc();
    final contact = TrustedContact(
      id: _nextId('tc'),
      userId: _userId,
      name: name.trim(),
      phone: phone.replaceAll(RegExp(r'[\s\-\(\)\.]'), ''),
      relationship: _blankToNull(relationship),
      email: _blankToNull(email)?.toLowerCase(),
      createdAt: now,
      updatedAt: now,
    );
    _contacts.add(contact);
    return contact;
  }

  @override
  Future<void> deleteContact(String id) async {
    await _delay(350);
    _contacts.removeWhere((c) => c.id == id);
  }

  // Check-ins --------------------------------------------------------------
  @override
  Future<List<CheckIn>> listCheckIns({CheckInStatus? status}) async {
    await _delay();
    final items = status == null
        ? List<CheckIn>.from(_checkIns)
        : _checkIns.where((c) => c.status == status).toList();
    items.sort((a, b) => b.createdAt.compareTo(a.createdAt));
    return List.unmodifiable(items);
  }

  @override
  Future<CheckIn> createCheckIn({String? note, DateTime? dueAt}) async {
    await _delay(500);
    final now = DateTime.now().toUtc();
    final checkIn = CheckIn(
      id: _nextId('ci'),
      userId: _userId,
      status: CheckInStatus.pending,
      note: _blankToNull(note),
      dueAt: dueAt?.toUtc(),
      createdAt: now,
      updatedAt: now,
    );
    _checkIns.insert(0, checkIn);
    return checkIn;
  }

  @override
  Future<CheckIn> completeCheckIn(String id) async {
    await _delay(400);
    return _transitionCheckIn(id, CheckInStatus.safe);
  }

  @override
  Future<CheckIn> updateCheckInStatus(String id, CheckInStatus status) async {
    await _delay(400);
    return _transitionCheckIn(id, status);
  }

  CheckIn _transitionCheckIn(String id, CheckInStatus target) {
    final index = _checkIns.indexWhere((c) => c.id == id);
    if (index == -1) {
      throw StateError('Check-in not found');
    }
    final current = _checkIns[index];
    if (current.status != CheckInStatus.pending) {
      // Mirror the backend: only a pending check-in may move.
      throw StateError('Only a pending check-in can be answered');
    }
    final now = DateTime.now().toUtc();
    final updated = CheckIn(
      id: current.id,
      userId: current.userId,
      status: target,
      note: current.note,
      dueAt: current.dueAt,
      completedAt: target == CheckInStatus.safe ||
              target == CheckInStatus.needsHelp
          ? now
          : null,
      createdAt: current.createdAt,
      updatedAt: now,
    );
    _checkIns[index] = updated;
    return updated;
  }

  // SOS --------------------------------------------------------------------
  @override
  Future<List<SosEvent>> listSosEvents() async {
    await _delay();
    final items = List<SosEvent>.from(_sos);
    items.sort((a, b) => b.createdAt.compareTo(a.createdAt));
    return List.unmodifiable(items);
  }

  @override
  Future<SosEvent> createSos({
    String? description,
    double? latitude,
    double? longitude,
  }) async {
    await _delay(500);
    final now = DateTime.now().toUtc();
    final event = SosEvent(
      id: _nextId('sos'),
      userId: _userId,
      status: SosStatus.active,
      description: _blankToNull(description),
      latitude: latitude,
      longitude: longitude,
      locationRecordedAt: latitude != null ? now : null,
      createdAt: now,
      updatedAt: now,
    );
    _sos.insert(0, event);
    return event;
  }

  @override
  Future<SosEvent> cancelSos(String id) => _closeSos(id, SosStatus.cancelled);

  @override
  Future<SosEvent> resolveSos(String id) => _closeSos(id, SosStatus.resolved);

  Future<SosEvent> _closeSos(String id, SosStatus target) async {
    await _delay(400);
    final index = _sos.indexWhere((e) => e.id == id);
    if (index == -1) {
      throw StateError('SOS incident not found');
    }
    final current = _sos[index];
    if (current.status != SosStatus.active) {
      throw StateError('Only an active SOS can be closed');
    }
    final now = DateTime.now().toUtc();
    final updated = SosEvent(
      id: current.id,
      userId: current.userId,
      status: target,
      description: current.description,
      latitude: current.latitude,
      longitude: current.longitude,
      locationRecordedAt: current.locationRecordedAt,
      createdAt: current.createdAt,
      updatedAt: now,
      cancelledAt: target == SosStatus.cancelled ? now : null,
      resolvedAt: target == SosStatus.resolved ? now : null,
    );
    _sos[index] = updated;
    return updated;
  }

  // Reports ----------------------------------------------------------------
  @override
  Future<List<CommunityReport>> listReports({
    ReportCategory? category,
    int offset = 0,
    int limit = 20,
  }) async {
    await _delay();
    var items = _reports
        .where((r) => r.status != ReportStatus.rejected)
        .toList();
    if (category != null) {
      items = items.where((r) => r.category == category).toList();
    }
    items.sort((a, b) => b.createdAt.compareTo(a.createdAt));
    final page = items.skip(offset).take(limit).toList();
    return List.unmodifiable(page);
  }

  @override
  Future<CommunityReport> createReport({
    required ReportCategory category,
    required String description,
    required double latitude,
    required double longitude,
  }) async {
    await _delay(500);
    final now = DateTime.now().toUtc();
    final report = CommunityReport(
      id: _nextId('rep'),
      category: category,
      status: ReportStatus.pending,
      description: description.trim(),
      latitude: latitude,
      longitude: longitude,
      createdAt: now,
      updatedAt: now,
    );
    _reports.insert(0, report);
    return report;
  }

  // Verification & social (Phase 6, second assignment) ----------------------
  // The seeded demo account is an OWNER so the moderation UI is explorable
  // offline; the real backend defaults every account to `user` and only the
  // server-side CLI can grant `owner`.
  @override
  Future<VerificationStatusInfo> verificationStatus() async {
    await _delay(150);
    return VerificationStatusInfo(
      verificationStatus: _verificationStatus,
      role: UserRole.owner,
      socialAccessRequired: _socialRequiresVerification,
      latestRequest: _latestRequest,
    );
  }

  @override
  Future<VerificationRequest> submitVerificationRequest({String? note}) async {
    await _delay(500);
    if (_verificationStatus == VerificationStatus.verified) {
      throw StateError('Account is already verified; no new request is possible.');
    }
    if (_verificationStatus == VerificationStatus.pending) {
      throw StateError('A verification request is already under review.');
    }
    final now = DateTime.now().toUtc();
    final request = VerificationRequest(
      id: _nextId('ver'),
      status: VerificationRequestStatus.pending,
      createdAt: now,
      applicantNote: _blankToNull(note),
    );
    _latestRequest = request;
    _verificationStatus = VerificationStatus.pending;
    return request;
  }

  @override
  Future<DiscoveryResult> discovery() async {
    await _delay(350);
    if (_socialRequiresVerification &&
        _verificationStatus != VerificationStatus.verified) {
      throw const SocialGateDeniedException();
    }
    return const DiscoveryResult(
      profiles: [],
      message: 'Travel-buddy discovery is not implemented yet (planned for '
          'Phase 7+). This screen exists to demonstrate the identity-'
          'verification gate.',
    );
  }

  @override
  Future<List<VerificationRequestReview>> listVerificationRequests({
    VerificationRequestStatus? status,
  }) async {
    await _delay();
    var items = List<VerificationRequestReview>.from(_reviewQueue);
    if (status != null) {
      items = items.where((r) => r.status == status).toList();
    }
    // Oldest submitted first, like the backend's FIFO queue.
    items.sort((a, b) => a.createdAt.compareTo(b.createdAt));
    return List.unmodifiable(items);
  }

  @override
  Future<VerificationRequestReview> approveVerificationRequest(
    String id, {
    String? reviewNote,
  }) =>
      _review(id, approve: true, reviewNote: reviewNote);

  @override
  Future<VerificationRequestReview> rejectVerificationRequest(
    String id, {
    String? reviewNote,
  }) =>
      _review(id, approve: false, reviewNote: reviewNote);

  Future<VerificationRequestReview> _review(
    String id, {
    required bool approve,
    required String? reviewNote,
  }) async {
    await _delay(400);
    final index = _reviewQueue.indexWhere((r) => r.id == id);
    if (index == -1) {
      throw StateError('Verification request not found');
    }
    final current = _reviewQueue[index];
    if (current.userId == _userId) {
      // Mirror the backend: self-review is refused, owner included.
      throw StateError('You cannot review your own verification request.');
    }
    if (current.status != VerificationRequestStatus.pending) {
      throw StateError('Only pending requests can be reviewed.');
    }
    final updated = VerificationRequestReview(
      id: current.id,
      userId: current.userId,
      displayName: current.displayName,
      status: approve
          ? VerificationRequestStatus.approved
          : VerificationRequestStatus.rejected,
      createdAt: current.createdAt,
      reviewedAt: DateTime.now().toUtc(),
      reviewedBy: _userId,
      reviewNote: _blankToNull(reviewNote),
      applicantNote: current.applicantNote,
    );
    _reviewQueue[index] = updated;
    return updated;
  }

  @override
  Future<SocialPolicy> getSocialPolicy() async {
    await _delay(150);
    return SocialPolicy(
      key: 'social_requires_verification',
      requiresVerification: _socialRequiresVerification,
      updatedAt: DateTime.now().toUtc().subtract(const Duration(hours: 20)),
      updatedBy: _userId,
    );
  }

  @override
  Future<SocialPolicy> setSocialPolicy({
    required bool requiresVerification,
  }) async {
    await _delay(400);
    _socialRequiresVerification = requiresVerification;
    return SocialPolicy(
      key: 'social_requires_verification',
      requiresVerification: requiresVerification,
      updatedAt: DateTime.now().toUtc(),
      updatedBy: _userId,
    );
  }

  // Health -----------------------------------------------------------------
  @override
  Future<bool> health() async => true;

  static String? _blankToNull(String? value) {
    if (value == null) return null;
    final trimmed = value.trim();
    return trimmed.isEmpty ? null : trimmed;
  }
}
