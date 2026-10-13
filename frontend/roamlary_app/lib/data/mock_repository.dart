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
  final List<AppNotification> _sosNotifications = [];
  final List<AppNotification> _inbox = [];
  final List<Meetup> _meetups = [];

/// Seeded house-party invitations — `/meetups` never returns these rows.
final List<Invitation> _invitations = [
  Invitation(
    id: 'inv-mock-1',
    meetupId: 'meetup-mock-1',
    eventTitle: 'Rooftop dinner in Lisbon',
    inviterId: 'u-mock-sofia',
    inviteeId: 'me',
    inviteeDisplayName: 'You',
    status: InvitationStatus.pending,
    createdAt: DateTime.now().toUtc(),
  ),
];
  final List<TripShare> _tripShares = [];
  final List<SharedItinerary> _sharedWithMe = [];
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

    // Social seed (Phase 7/8): one accepted conversation with history, one
    // incoming request, and a pending buddy request so the chat UI has
    // content in mock mode too.
    final convAccepted = Conversation(
      id: _nextId('cv'),
      otherUserId: 'u-demo-1001',
      otherDisplayName: 'Aarav Mehta',
      status: ConversationStatus.accepted,
      requestedByMe: false,
      createdAt: now.subtract(const Duration(days: 2)),
      updatedAt: now.subtract(const Duration(hours: 3)),
    );
    _conversations.addAll([
      convAccepted,
      Conversation(
        id: _nextId('cv'),
        otherUserId: 'u-demo-1002',
        otherDisplayName: 'Sofia Reyes',
        status: ConversationStatus.pending,
        requestedByMe: false,
        createdAt: now.subtract(const Duration(hours: 6)),
        updatedAt: now.subtract(const Duration(hours: 6)),
      ),
    ]);
    _messages.addAll([
      ChatMessage(
        id: _nextId('msg'),
        conversationId: convAccepted.id,
        senderId: 'u-demo-1001',
        mine: false,
        body: "Hey! Saw you're heading to Goa too - want to share a cab "
            'from the airport?',
        isDeleted: false,
        createdAt: now.subtract(const Duration(hours: 4)),
      ),
      ChatMessage(
        id: _nextId('msg'),
        conversationId: convAccepted.id,
        senderId: _userId,
        mine: true,
        body: 'Yes please! I land at 6pm on the 20th.',
        isDeleted: false,
        createdAt: now.subtract(const Duration(hours: 3, minutes: 50)),
      ),
      ChatMessage(
        id: _nextId('msg'),
        conversationId: convAccepted.id,
        senderId: 'u-demo-1001',
        mine: false,
        body: "Perfect. I'll book it and send the details here.",
        isDeleted: false,
        createdAt: now.subtract(const Duration(hours: 3)),
      ),
    ]);
    _buddyRequests.add(
      BuddyRequest(
        id: _nextId('br'),
        requesterId: 'u-demo-1001',
        requesterDisplayName: 'Aarav Mehta',
        recipientId: _userId,
        recipientDisplayName: _profile.displayName,
        status: BuddyRequestStatus.pending,
        createdAt: now.subtract(const Duration(hours: 5)),
        planDestination: 'Manali',
      ),
    );

    // Phase 9-13 seed: meetups, notifications inbox, trip shares.
    _meetups.addAll([
      Meetup(
        id: _nextId('mtp'),
        hostId: 'u-demo-1002',
        hostDisplayName: 'Sofia Reyes',
        title: 'Sunrise hike at Annapurna base',
        description: 'Early start, moderate pace, coffee after.',
        category: MeetupCategory.hiking,
        startAt: now.add(const Duration(days: 4)).add(const Duration(hours: 5)),
        endAt: now.add(const Duration(days: 4)).add(const Duration(hours: 11)),
        capacity: 12,
        approvedCount: 5,
        participation: 'open',
        status: MeetupStatus.active,
        locationText: 'Pokhara, Nepal',
        myMembership: MembershipStatus.none,
        kind: 'meetup',
      ),
      Meetup(
        id: _nextId('mtp'),
        hostId: 'u-demo-1001',
        hostDisplayName: 'Aarav Mehta',
        title: 'Old-town food walk',
        description: 'Six stops, vegetarians welcome.',
        category: MeetupCategory.food,
        startAt: now.add(const Duration(days: 2)).add(const Duration(hours: 18)),
        endAt: now.add(const Duration(days: 2)).add(const Duration(hours: 21)),
        capacity: 8,
        approvedCount: 8,
        participation: 'approval',
        status: MeetupStatus.active,
        locationText: 'Jaipur, India',
        myMembership: MembershipStatus.none,
        kind: 'meetup',
      ),
    ]);

    _inbox.addAll([
      AppNotification(
        id: _nextId('ntf'),
        kind: 'chat_request',
        title: 'New chat request',
        body: 'Sofia Reyes would like to chat with you.',
        channel: 'in_app',
        status: NotificationStatus.delivered,
        attempts: 1,
        createdAt: now.subtract(const Duration(hours: 6)),
      ),
      AppNotification(
        id: _nextId('ntf'),
        kind: 'checkin_due',
        title: 'Check-in due soon',
        body: 'Your check-in "Night walk along Marine Drive" is due in 3 hours.',
        channel: 'in_app',
        status: NotificationStatus.delivered,
        attempts: 1,
        createdAt: now.subtract(const Duration(hours: 1)),
      ),
      AppNotification(
        id: _nextId('ntf'),
        kind: 'buddy_request',
        title: 'Travel-buddy request',
        body: 'Aarav Mehta wants to join your Manali leg.',
        channel: 'in_app',
        status: NotificationStatus.delivered,
        attempts: 1,
        createdAt: now.subtract(const Duration(minutes: 42)),
        readAt: now.subtract(const Duration(minutes: 30)),
      ),
    ]);

    _tripShares.add(
      TripShare(
        id: _nextId('shr'),
        shareUrl: 'https://roamlary.app/s/k-demo-7f3a',
        expiresAt: now.add(const Duration(days: 6)),
        planDestination: 'Manali',
        createdAt: now.subtract(const Duration(hours: 8)),
      ),
    );

    _sharedWithMe.add(
      SharedItinerary(
        id: _nextId('shi'),
        ownerDisplayName: 'Sofia Reyes',
        shareUrl: 'https://roamlary.app/s/k-demo-9b2c',
        expiresAt: now.add(const Duration(days: 2)),
        planDestination: 'Jaipur',
        createdAt: now.subtract(const Duration(days: 1)),
      ),
    );
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

  @override
  Future<CheckIn> updateCheckInNote(String id, {required String note}) async {
    await _delay(350);
    final index = _checkIns.indexWhere((c) => c.id == id);
    if (index == -1) throw StateError('Check-in not found');
    final current = _checkIns[index];
    final updated = CheckIn(
      id: current.id,
      userId: current.userId,
      status: current.status,
      note: _blankToNull(note),
      dueAt: current.dueAt,
      completedAt: current.completedAt,
      createdAt: current.createdAt,
      updatedAt: DateTime.now().toUtc(),
    );
    _checkIns[index] = updated;
    return updated;
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

  /// Backend CAS rules: `active` may move anywhere; `acknowledged` may still
  /// go to resolved/cancelled. Anything else is a 409.
  Future<SosEvent> _closeSos(String id, SosStatus target) async {
    await _delay(400);
    final index = _sos.indexWhere((e) => e.id == id);
    if (index == -1) {
      throw StateError('SOS incident not found');
    }
    final current = _sos[index];
    if (current.status != SosStatus.active &&
        current.status != SosStatus.acknowledged) {
      throw StateError(
          'This SOS incident is already closed (${current.status.wire})');
    }
    final now = DateTime.now().toUtc();
    final updated = _copySos(
      current,
      status: target,
      updatedAt: now,
      cancelledAt: target == SosStatus.cancelled ? now : null,
      resolvedAt: target == SosStatus.resolved ? now : null,
    );
    _sos[index] = updated;
    return updated;
  }

  SosEvent _copySos(
    SosEvent e, {
    SosStatus? status,
    DateTime? updatedAt,
    DateTime? cancelledAt,
    DateTime? resolvedAt,
    DateTime? acknowledgedAt,
  }) =>
      SosEvent(
        id: e.id,
        userId: e.userId,
        status: status ?? e.status,
        description: e.description,
        latitude: e.latitude,
        longitude: e.longitude,
        locationRecordedAt: e.locationRecordedAt,
        createdAt: e.createdAt,
        updatedAt: updatedAt ?? e.updatedAt,
        cancelledAt: cancelledAt,
        resolvedAt: resolvedAt,
        acknowledgedAt: acknowledgedAt ?? e.acknowledgedAt,
      );

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

  // Chat (Phase 8) ----------------------------------------------------------
  final List<Conversation> _conversations = [];
  final List<ChatMessage> _messages = [];
  final List<BuddyRequest> _buddyRequests = [];
  final List<BlockedUser> _blocks = [];

  @override
  Future<List<DiscoveryCandidate>> discover({
    int offset = 0,
    int limit = 20,
  }) async {
    await _delay();
    if (_socialRequiresVerification &&
        _verificationStatus != VerificationStatus.verified) {
      throw const SocialGateDeniedException();
    }
    return [
      DiscoveryCandidate(
        userId: 'u-demo-1001',
        displayName: 'Aarav Mehta',
        bio: 'Backpacking through India for 6 months.',
        homeRegion: 'Goa, India',
        languages: const ['English', 'Hindi'],
        travelStyles: const ['backpacker', 'solo'],
        interests: const ['hiking', 'food', 'photography'],
        destination: 'Manali',
        compatibilityScore: 85,
        existingRequest: 'none',
      ),
      DiscoveryCandidate(
        userId: 'u-demo-1002',
        displayName: 'Sofia Reyes',
        bio: 'Slow travel + street food.',
        homeRegion: 'Barcelona, Spain',
        languages: const ['Spanish', 'English'],
        travelStyles: const ['slow_travel', 'cultural'],
        interests: const ['food', 'history', 'museums'],
        destination: 'Jaipur',
        compatibilityScore: 72,
        existingRequest: 'pending_received',
      ),
      DiscoveryCandidate(
        userId: 'u-demo-1003',
        displayName: 'Kenji Tanaka',
        bio: 'Photographer chasing sunrises.',
        homeRegion: 'Tokyo, Japan',
        languages: const ['Japanese', 'English'],
        travelStyles: const ['road_trip', 'adventure'],
        interests: const ['photography', 'wildlife'],
        destination: 'Ladakh',
        compatibilityScore: 64,
        existingRequest: 'pending_sent',
      ),
    ];
  }

  @override
  Future<List<Conversation>> listConversations() async {
    await _delay();
    return List.unmodifiable(_conversations
        .where((c) => c.status == ConversationStatus.accepted));
  }

  @override
  Future<List<Conversation>> listChatRequests({
    required String direction,
  }) async {
    await _delay();
    return List.unmodifiable(_conversations.where((c) =>
        c.status == ConversationStatus.pending &&
        (direction == 'incoming' ? !c.requestedByMe : c.requestedByMe)));
  }

  @override
  Future<void> sendChatRequest({required String recipientId}) async {
    await _delay();
    _conversations.insert(
      0,
      Conversation(
        id: _nextId('cv'),
        otherUserId: recipientId,
        otherDisplayName: 'Traveller',
        status: ConversationStatus.pending,
        requestedByMe: true,
        createdAt: DateTime.now().toUtc(),
        updatedAt: DateTime.now().toUtc(),
      ),
    );
  }

  @override
  Future<Conversation> acceptChatRequest(String id) async {
    await _delay();
    final i = _conversations.indexWhere((c) => c.id == id);
    if (i < 0) throw StateError('Request not found');
    final updated = Conversation(
      id: _conversations[i].id,
      otherUserId: _conversations[i].otherUserId,
      otherDisplayName: _conversations[i].otherDisplayName,
      status: ConversationStatus.accepted,
      requestedByMe: _conversations[i].requestedByMe,
      createdAt: _conversations[i].createdAt,
      updatedAt: DateTime.now().toUtc(),
    );
    _conversations[i] = updated;
    return updated;
  }

  @override
  Future<void> rejectChatRequest(String id) async {
    await _delay();
    _conversations.removeWhere((c) => c.id == id);
  }

  @override
  Future<void> cancelChatRequest(String id) async {
    await _delay();
    _conversations.removeWhere((c) => c.id == id);
  }

  @override
  Future<List<ChatMessage>> listMessages(String conversationId) async {
    await _delay(150);
    return List.unmodifiable(
        _messages.where((m) => m.conversationId == conversationId));
  }

  @override
  Future<ChatMessage> sendMessage(String conversationId, String body) async {
    await _delay(150);
    final msg = ChatMessage(
      id: _nextId('msg'),
      conversationId: conversationId,
      senderId: _userId,
      mine: true,
      body: body,
      isDeleted: false,
      createdAt: DateTime.now().toUtc(),
    );
    _messages.add(msg);
    return msg;
  }

  // Travel-buddy requests (Phase 7) ------------------------------------------
  @override
  Future<List<BuddyRequest>> listBuddyRequests({
    required String direction,
  }) async {
    await _delay();
    return List.unmodifiable(_buddyRequests.where((r) =>
        direction == 'incoming' ? r.recipientId == _userId
                                : r.requesterId == _userId));
  }

  @override
  Future<void> sendBuddyRequest({
    required String recipientId,
    String? planId,
  }) async {
    await _delay();
    _buddyRequests.insert(
      0,
      BuddyRequest(
        id: _nextId('br'),
        requesterId: _userId,
        requesterDisplayName: _profile.displayName,
        recipientId: recipientId,
        recipientDisplayName: 'Traveller',
        status: BuddyRequestStatus.pending,
        createdAt: DateTime.now().toUtc(),
      ),
    );
  }

  @override
  Future<BuddyRequest> acceptBuddyRequest(String id) async {
    await _delay();
    final i = _buddyRequests.indexWhere((r) => r.id == id);
    if (i < 0) throw StateError('Request not found');
    final updated = BuddyRequest(
      id: _buddyRequests[i].id,
      requesterId: _buddyRequests[i].requesterId,
      requesterDisplayName: _buddyRequests[i].requesterDisplayName,
      recipientId: _buddyRequests[i].recipientId,
      recipientDisplayName: _buddyRequests[i].recipientDisplayName,
      status: BuddyRequestStatus.accepted,
      createdAt: _buddyRequests[i].createdAt,
      planDestination: _buddyRequests[i].planDestination,
    );
    _buddyRequests[i] = updated;
    return updated;
  }

  @override
  Future<void> rejectBuddyRequest(String id) async {
    await _delay();
    _buddyRequests.removeWhere((r) => r.id == id);
  }

  // Blocking ----------------------------------------------------------------
  @override
  Future<List<BlockedUser>> listBlocks() async {
    await _delay();
    return List.unmodifiable(_blocks);
  }

  @override
  Future<void> blockUser(String blockedId) async {
    await _delay();
    if (_blocks.any((b) => b.blockedId == blockedId)) return;
    _blocks.insert(
      0,
      BlockedUser(
        id: _nextId('blk'),
        blockedId: blockedId,
        blockedDisplayName: 'Traveller',
        createdAt: DateTime.now().toUtc(),
      ),
    );
  }

  @override
  Future<void> unblockUser(String blockedId) async {
    await _delay();
    _blocks.removeWhere((b) => b.blockedId == blockedId);
  }

  // SOS workflow (Phase 10) ---------------------------------------------------
  @override
  Future<SosEvent> acknowledgeSos(String id) async {
    await _delay(400);
    final i = _sos.indexWhere((e) => e.id == id);
    if (i < 0) throw StateError('SOS incident not found');
    final current = _sos[i];
    if (current.status != SosStatus.active) {
      throw StateError('Only an active SOS incident can be acknowledged');
    }
    final now = DateTime.now().toUtc();
    final updated = _copySos(
      current,
      status: SosStatus.acknowledged,
      acknowledgedAt: now,
      updatedAt: now,
    );
    _sos[i] = updated;
    return updated;
  }

  @override
  Future<List<AppNotification>> retrySosNotifications(String id) async {
    await _delay(400);
    final i = _sos.indexWhere((e) => e.id == id);
    if (i < 0) throw StateError('SOS incident not found');
    // Simulate a re-attempt landing: queued -> delivered.
    return _sosNotifications
        .map((n) => AppNotification(
              id: n.id,
              kind: n.kind,
              title: n.title,
              body: n.body,
              channel: n.channel,
              status: NotificationStatus.delivered,
              attempts: n.attempts + 1,
              lastError: null,
              readAt: n.readAt,
              createdAt: n.createdAt,
            ))
        .toList();
  }

  @override
  Future<List<AppNotification>> listSosNotifications(String id) async {
    await _delay(200);
    if (_sosNotifications.isEmpty) {
      final now = DateTime.now().toUtc();
      _sosNotifications.addAll([
        AppNotification(
          id: _nextId('ntf'),
          kind: 'sos_contact',
          title: 'SOS relay to trusted contacts',
          body: 'Meera Patel was notified by SMS.',
          channel: 'sms',
          status: NotificationStatus.delivered,
          attempts: 1,
          createdAt: now,
        ),
        AppNotification(
          id: _nextId('ntf'),
          kind: 'sos_contact',
          title: 'SOS relay to trusted contacts',
          body: 'Aarav Sharma email could not be delivered.',
          channel: 'email',
          status: NotificationStatus.failed,
          attempts: 2,
          lastError: 'Mailbox unavailable',
          createdAt: now.add(const Duration(seconds: 30)),
        ),
      ]);
    }
    return List.unmodifiable(_sosNotifications);
  }

  // Check-ins: overdue view (Phase 12) ----------------------------------------
  @override
  Future<List<CheckIn>> listOverdueCheckIns() async {
    await _delay();
    final now = DateTime.now().toUtc();
    final items = _checkIns
        .where((c) =>
            c.status == CheckInStatus.pending &&
            c.dueAt != null &&
            c.dueAt!.isBefore(now))
        .toList()
      ..sort((a, b) => a.dueAt!.compareTo(b.dueAt!));
    return List.unmodifiable(items);
  }

  // Meetups & house parties (Phase 9) -----------------------------------------
  @override
  Future<List<Meetup>> listMeetups() async {
    await _delay();
    return List.unmodifiable(_meetups);
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
    await _delay(500);
    final meetup = Meetup(
      id: _nextId('mtp'),
      hostId: _userId,
      hostDisplayName: _profile.displayName,
      title: title.trim(),
      description: _blankToNull(description),
      category: category,
      startAt: startAt.toUtc(),
      endAt: endAt.toUtc(),
      capacity: capacity,
      approvedCount: 0,
      participation: 'open',
      status: MeetupStatus.active,
      locationText: _blankToNull(locationText),
      myMembership: MembershipStatus.approved,
      kind: 'meetup',
    );
    _meetups.insert(0, meetup);
    return meetup;
  }

  @override
  Future<void> joinMeetup(String id) async {
    await _delay(400);
    final i = _meetups.indexWhere((m) => m.id == id);
    if (i < 0) throw StateError('Meetup not found');
    final m = _meetups[i];
    _meetups[i] = _copyMeetup(
      m,
      approvedCount: m.approvedCount + 1,
      myMembership: MembershipStatus.approved,
    );
  }

  @override
  Future<void> leaveMeetup(String id) async {
    await _delay(400);
    final i = _meetups.indexWhere((m) => m.id == id);
    if (i < 0) throw StateError('Meetup not found');
    final m = _meetups[i];
    _meetups[i] = _copyMeetup(
      m,
      approvedCount: m.approvedCount > 0 ? m.approvedCount - 1 : 0,
      myMembership: MembershipStatus.left,
    );
  }

  @override
  Future<void> cancelMeetup(String id) async {
    await _delay(400);
    final i = _meetups.indexWhere((m) => m.id == id);
    if (i < 0) throw StateError('Meetup not found');
    _meetups[i] = _copyMeetup(_meetups[i], status: MeetupStatus.cancelled);
  }

  // House-party invitations (Phase 10) ----------------------------------------
  @override
  Future<List<Invitation>> listInvitations({int offset = 0, int limit = 20}) async {
    await _delay();
    return List.unmodifiable(_invitations);
  }

  @override
  Future<Invitation> acceptInvitation(String id) async =>
      _answerInvitation(id, InvitationStatus.accepted);

  @override
  Future<Invitation> declineInvitation(String id) async =>
      _answerInvitation(id, InvitationStatus.declined);

  Invitation _answerInvitation(String id, InvitationStatus status) {
    final i = _invitations.indexWhere((v) => v.id == id);
    if (i < 0) throw StateError('Invitation not found');
    final old = _invitations[i];
    if (!old.isPending) {
      throw StateError('This invitation has already been answered.');
    }
    final updated = Invitation(
      id: old.id,
      meetupId: old.meetupId,
      eventTitle: old.eventTitle,
      inviterId: old.inviterId,
      inviteeId: old.inviteeId,
      inviteeDisplayName: old.inviteeDisplayName,
      status: status,
      respondedAt: DateTime.now().toUtc(),
      createdAt: old.createdAt,
    );
    _invitations[i] = updated;
    return updated;
  }

  Meetup _copyMeetup(
    Meetup m, {
    MeetupStatus? status,
    int? approvedCount,
    MembershipStatus? myMembership,
  }) =>
      Meetup(
        id: m.id,
        hostId: m.hostId,
        hostDisplayName: m.hostDisplayName,
        title: m.title,
        description: m.description,
        category: m.category,
        startAt: m.startAt,
        endAt: m.endAt,
        capacity: m.capacity,
        approvedCount: approvedCount ?? m.approvedCount,
        participation: m.participation,
        status: status ?? m.status,
        locationText: m.locationText,
        myMembership: myMembership ?? m.myMembership,
        kind: m.kind,
      );

  // Notifications inbox (Phase 11) ---------------------------------------------
  @override
  Future<List<AppNotification>> listNotifications() async {
    await _delay();
    return List.unmodifiable(_inbox);
  }

  @override
  Future<void> markNotificationRead(String id) async {
    await _delay(200);
    final i = _inbox.indexWhere((n) => n.id == id);
    if (i < 0) return;
    final n = _inbox[i];
    _inbox[i] = AppNotification(
      id: n.id,
      kind: n.kind,
      title: n.title,
      body: n.body,
      channel: n.channel,
      status: n.status,
      attempts: n.attempts,
      lastError: n.lastError,
      readAt: DateTime.now().toUtc(),
      createdAt: n.createdAt,
    );
  }

  // Trip sharing (Phase 11) ----------------------------------------------------
  @override
  Future<List<TripShare>> listTripShares() async {
    await _delay();
    return List.unmodifiable(_tripShares);
  }

  @override
  Future<TripShare> createTripShare({
    String? planId,
    required DateTime expiresAt,
  }) async {
    await _delay(400);
    final share = TripShare(
      id: _nextId('shr'),
      shareUrl: 'https://roamlary.app/s/${_nextId('k')}',
      expiresAt: expiresAt.toUtc(),
      planId: planId,
      planDestination: 'Manali',
      createdAt: DateTime.now().toUtc(),
    );
    _tripShares.insert(0, share);
    return share;
  }

  @override
  Future<void> revokeTripShare(String id) async {
    await _delay(300);
    final i = _tripShares.indexWhere((s) => s.id == id);
    if (i < 0) return;
    final s = _tripShares[i];
    _tripShares[i] = TripShare(
      id: s.id,
      shareUrl: s.shareUrl,
      expiresAt: s.expiresAt,
      planId: s.planId,
      planDestination: s.planDestination,
      revokedAt: DateTime.now().toUtc(),
      createdAt: s.createdAt,
    );
  }

  @override
  Future<List<SharedItinerary>> listSharedWithMe() async {
    await _delay();
    return List.unmodifiable(_sharedWithMe);
  }

  // AI companion (Phase 13) -----------------------------------------------------
  @override
  Future<AiStatus> aiStatus() async {
    await _delay(150);
    return const AiStatus(provider: 'mock', configured: false);
  }

  @override
  Future<AiAnswer> askAi(String message) async {
    await _delay(700);
    return AiAnswer(
      answer: 'In mock mode the AI companion is not connected, so this is a '
          'canned reply: "$message". Run against the backend for real answers.',
      verified: false,
      honestyFooter: 'Canned demo reply — not AI-generated travel advice.',
      generatedAt: DateTime.now().toUtc(),
    );
  }

  // Filtered discovery ----------------------------------------------------------
  @override
  Future<List<DiscoveryCandidate>> discoverFiltered({
    String? destination,
    String? travelStyle,
    String? language,
    List<String> interests = const [],
    int minScore = 0,
    int limit = 20,
  }) async {
    var items = await discover(limit: limit);
    if (destination != null && destination.isNotEmpty) {
      items = items
          .where((c) =>
              c.destination.toLowerCase().contains(destination.toLowerCase()))
          .toList();
    }
    if (travelStyle != null && travelStyle.isNotEmpty) {
      items = items
          .where((c) => (c.travelStyles ?? [])
              .any((s) => s.toLowerCase() == travelStyle.toLowerCase()))
          .toList();
    }
    if (language != null && language.isNotEmpty) {
      items = items
          .where((c) =>
              (c.languages ?? []).any((l) => l.toLowerCase() == language.toLowerCase()))
          .toList();
    }
    for (final interest in interests) {
      items = items
          .where((c) =>
              (c.interests ?? []).any((i) => i.toLowerCase() == interest.toLowerCase()))
          .toList();
    }
    items = items.where((c) => c.compatibilityScore >= minScore).toList();
    return items.take(limit).toList();
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
