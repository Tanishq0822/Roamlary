"""Status values for the Phase 2 domain models.

Plain language: these are the ONLY allowed values for the status
columns. Using a Python enum (instead of loose strings) means a typo
like "savfe" fails immediately instead of silently entering the
database. The database additionally enforces the same values through
CHECK constraints defined in the model files.
"""

from enum import StrEnum


class CheckInStatus(StrEnum):
    """Lifecycle of a safety check-in.

    Phase 4 adds CANCELLED so a user can abandon a check-in they no
    longer want; the other values are the original Phase 2 design and
    map onto the generic lifecycle as follows:

        active      -> PENDING      (scheduled, waiting for an answer)
        completed   -> SAFE         (user confirmed they are fine)
        (extra)       NEEDS_HELP    (user signalled they are NOT fine)
        cancelled   -> CANCELLED    (user abandoned this check-in)
        (later)       EXPIRED       (deadline passed unanswered - a
                                     future phase sets this via a job;
                                     Phase 4 NEVER sets it automatically)
    """

    PENDING = "pending"  # scheduled, waiting for the user's answer
    SAFE = "safe"  # user confirmed they are safe
    NEEDS_HELP = "needs_help"  # user indicated they need help
    EXPIRED = "expired"  # deadline passed without an answer
    CANCELLED = "cancelled"  # user abandoned this check-in


class SosStatus(StrEnum):
    """Lifecycle of a (simulated) SOS incident.

    Phase 5 adds CANCELLED so a user can retract an SOS that turned out
    to be unnecessary; the other four values are the original Phase 2
    design. `acknowledged` and `false_alarm` remain RESERVED in Phase 5:
    nothing implements them yet (no responder exists to acknowledge an
    incident), exactly like `expired` for check-ins in Phase 4.

        active      -> ACTIVE      (just triggered; the only start state)
        (reserved)    ACKNOWLEDGED (later phase; unreachable now)
        (reserved)    FALSE_ALARM  (later phase; unreachable now)
        resolved    -> RESOLVED    (handled; terminal)
        cancelled   -> CANCELLED   (retracted by the user; terminal)
    """

    ACTIVE = "active"  # just triggered
    ACKNOWLEDGED = "acknowledged"  # reserved: someone saw it / took over
    RESOLVED = "resolved"  # handled successfully (terminal)
    FALSE_ALARM = "false_alarm"  # reserved: cancelled / accidental
    CANCELLED = "cancelled"  # retracted by the user (terminal)


class ReportStatus(StrEnum):
    """Moderation state of a community safety report."""

    PENDING = "pending"  # submitted, not yet reviewed
    APPROVED = "approved"  # visible to the community
    REJECTED = "rejected"  # declined during review
