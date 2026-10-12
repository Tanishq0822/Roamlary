/// Status enums mirroring the backend's `app/models/enums.py` exactly.
///
/// The wire values (strings) match the FastAPI/StrEnum values one-for-one so a
/// JSON payload from the backend deserializes with no translation layer.
library;

enum CheckInStatus {
  pending('pending'),
  safe('safe'),
  needsHelp('needs_help'),
  expired('expired'),
  cancelled('cancelled');

  const CheckInStatus(this.wire);
  final String wire;

  static CheckInStatus fromWire(String value) =>
      CheckInStatus.values.firstWhere(
        (e) => e.wire == value,
        orElse: () => CheckInStatus.pending,
      );
}

enum SosStatus {
  active('active'),
  acknowledged('acknowledged'),
  resolved('resolved'),
  falseAlarm('false_alarm'),
  cancelled('cancelled');

  const SosStatus(this.wire);
  final String wire;

  static SosStatus fromWire(String value) => SosStatus.values.firstWhere(
        (e) => e.wire == value,
        orElse: () => SosStatus.active,
      );
}

enum ReportStatus {
  pending('pending'),
  approved('approved'),
  rejected('rejected');

  const ReportStatus(this.wire);
  final String wire;

  static ReportStatus fromWire(String value) => ReportStatus.values.firstWhere(
        (e) => e.wire == value,
        orElse: () => ReportStatus.pending,
      );
}

enum ReportCategory {
  unsafeArea('unsafe_area', 'Unsafe area'),
  harassment('harassment', 'Harassment'),
  suspiciousActivity('suspicious_activity', 'Suspicious activity'),
  roadHazard('road_hazard', 'Road hazard'),
  poorLighting('poor_lighting', 'Poor lighting'),
  other('other', 'Other');

  const ReportCategory(this.wire, this.label);
  final String wire;
  final String label;

  static ReportCategory fromWire(String value) =>
      ReportCategory.values.firstWhere(
        (e) => e.wire == value,
        orElse: () => ReportCategory.other,
      );
}
