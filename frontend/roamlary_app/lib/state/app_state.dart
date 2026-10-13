import 'package:flutter/foundation.dart';

import '../core/config.dart';
import '../data/app_repository.dart';
import '../models/models.dart';

/// Session + auth state for the whole app.
///
/// Holds the current [AuthSession] and exposes explicit auth actions. Screens
/// read `profile` / `isSignedIn` reactively via `context.watch<AppState>()`.
class AppState extends ChangeNotifier {
  AppState(this._repo);

  final AppRepository _repo;
  AuthSession? _session;
  bool _busy = false;
  String? _lastError;

  AppRepository get repo => _repo;
  AuthSession? get session => _session;
  UserProfile? get profile => _session?.profile;
  bool get isSignedIn => _session != null;
  bool get busy => _busy;
  String? get lastError => _lastError;

  void _setBusy(bool value) {
    _busy = value;
    notifyListeners();
  }

  void clearError() {
    if (_lastError != null) {
      _lastError = null;
      notifyListeners();
    }
  }

  Future<bool> signIn({required String email, required String password}) async {
    return _runAuth(() => _repo.login(email: email, password: password));
  }

  Future<bool> signUp({
    required String displayName,
    required String email,
    required String password,
  }) async {
    return _runAuth(
      () => _repo.register(
        displayName: displayName,
        email: email,
        password: password,
      ),
    );
  }

  /// Demo / guest entry point — used by the "Explore demo" button.
  ///
  /// The real backend has no anonymous account, so this signs into a seeded
  /// demo account ([AppConfig.demoEmail]) to reach real data. In mock mode
  /// [login] accepts any credentials, so the same call path works for both.
  /// If the account doesn't exist yet (fresh database), it is registered.
  Future<void> continueAsGuest() async {
    _setBusy(true);
    try {
      AuthSession session;
      try {
        session = await _repo.login(
          email: AppConfig.demoEmail,
          password: AppConfig.demoPassword,
        );
      } catch (_) {
        // Account not created yet — register it (register also returns a
        // session, so we land signed-in either way).
        session = await _repo.register(
          displayName: AppConfig.demoDisplayName,
          email: AppConfig.demoEmail,
          password: AppConfig.demoPassword,
        );
      }
      _session = session;
      _lastError = null;
    } catch (e) {
      _lastError = _message(e);
    } finally {
      _setBusy(false);
    }
  }

  Future<bool> _runAuth(Future<AuthSession> Function() action) async {
    _setBusy(true);
    try {
      _session = await action();
      _lastError = null;
      return true;
    } catch (e) {
      _lastError = _message(e);
      return false;
    } finally {
      _setBusy(false);
    }
  }

  void signOut() {
    _session = null;
    notifyListeners();
  }

  static String _message(Object error) {
    // ApiException carries a human-readable `message`; anything else falls back
    // to its toString.
    try {
      final dynamic e = error;
      final String? msg = e.message as String?;
      if (msg != null && msg.isNotEmpty) return msg;
    } catch (_) {}
    return 'Something went wrong. Please try again.';
  }
}
