/// Central runtime configuration.
///
/// `useMocks` is the single switch that decides whether the app runs against
/// in-memory mock data (default — safe for a backend-less demo) or against the
/// real FastAPI backend. When [useMocks] is false, [apiBaseUrl] must point at
/// the running backend.
class AppConfig {
  AppConfig._();

  /// When true the UI is backed by [MockRepository] and never opens a socket.
  /// Flip to false to talk to the real backend.
  static const bool useMocks = true;

  /// Base URL of the FastAPI backend, including the version prefix.
  ///
  /// Backend defaults (verified in `backend/app/core/config.py`):
  ///   host 127.0.0.1, port 8000, prefix /api/v1.
  ///
  /// From the Android emulator the host machine is reached via `10.0.2.2`, not
  /// `127.0.0.1`. From a physical device you must use your machine's LAN IP.
  static const String apiBaseUrl = 'http://10.0.2.2:8000/api/v1';

  /// Name shown on the splash / app bar.
  static const String appName = 'Roamlary';
}
