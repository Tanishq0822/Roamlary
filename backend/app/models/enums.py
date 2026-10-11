"""Status values for the Phase 2 domain models.

Plain language: these are the ONLY allowed values for the status
columns. Using a Python enum (instead of loose strings) means a typo
like "savfe" fails immediately instead of silently entering the
database. The database additionally enforces the same values through
CHECK constraints defined in the model files.
"""

from enum import StrEnum


class CheckInStatus(StrEnum):
    """Lifecycle of a safety check-in."""

    PENDING = "pending"  # scheduled, waiting for the user's answer
    SAFE = "safe"  # user confirmed they are safe
    NEEDS_HELP = "needs_help"  # user indicated they need help
    EXPIRED = "expired"  # deadline passed without an answer


class SosStatus(StrEnum):
    """Lifecycle of a (simulated) SOS incident."""

    ACTIVE = "active"  # just triggered
    ACKNOWLEDGED = "acknowledged"  # someone saw it / took over
    RESOLVED = "resolved"  # handled successfully
    FALSE_ALARM = "false_alarm"  # cancelled / accidental


class ReportStatus(StrEnum):
    """Moderation state of a community safety report."""

    PENDING = "pending"  # submitted, not yet reviewed
    APPROVED = "approved"  # visible to the community
    REJECTED = "rejected"  # declined during review
