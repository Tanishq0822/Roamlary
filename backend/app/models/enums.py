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
    """Moderation state of a community safety report.

    Phase 6 note: NO moderation system exists yet, so nothing can move a
    report out of PENDING. `approved` and `rejected` are RESERVED for the
    future moderation phase — the API never accepts a status from
    clients, and ordinary users cannot mark their own reports approved.
    Until then, every submitted report is user-submitted content
    (`pending`), and only `rejected` rows are hidden from the public API.
    """

    PENDING = "pending"  # submitted, not yet reviewed
    APPROVED = "approved"  # visible to the community
    REJECTED = "rejected"  # declined during review


class ReportCategory(StrEnum):
    """Allowed categories for community safety reports (Phase 6).

    The Phase 2 model deliberately kept `category` as a loose string
    ("categories are a Phase 6 product decision"). Phase 6 makes that
    decision: six machine-friendly values, enforced by the API schema AND
    a database CHECK constraint (added by migration). Short snake_case
    keeps every value inside the column's VARCHAR(40).

        unsafe_area         -> general "do not linger here" observation
        harassment          -> someone was harassed at/near this place
        suspicious_activity -> unusual or unsettling behaviour observed
        road_hazard         -> roads/transport danger (potholes, blocked
                               roads, aggressive driving hotspots)
        poor_lighting       -> dark streets, broken lamps, blind corners
        other               -> genuine safety concern that fits nowhere
                               above (description carries the detail)
    """

    UNSAFE_AREA = "unsafe_area"
    HARASSMENT = "harassment"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    ROAD_HAZARD = "road_hazard"
    POOR_LIGHTING = "poor_lighting"
    OTHER = "other"


class VerificationStatus(StrEnum):
    """Account-level identity-verification state (Phase 6, second assignment).

    This is the state OF THE ACCOUNT, not of any single submission:

        unverified -> the account has never completed (or never started)
                      the verification workflow. Every new account starts
                      here (database default).
        pending    -> a verification request was submitted and is waiting
                      for a human reviewer.
        verified   -> a reviewer approved the request. The ONLY value that
                      unlocks social features (when the policy requires
                      verification).
        rejected   -> a reviewer declined the latest request; the user may
                      submit a new one (rejected -> pending).

    Deliberately distinct from registration, email verification, and phone
    verification - none of which exist here or imply identity verification.
    `expired`/`requires_review` are NOT modelled yet: there is no
    background-job infrastructure and no verification provider to time out
    (documented deferral, not an oversight).

    No API path sets this column directly from client input - only the
    submit/review workflow moves it, server-side.
    """

    UNVERIFIED = "unverified"
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"


class VerificationRequestStatus(StrEnum):
    """State of ONE submitted verification request (the history table).

    Distinct from the account-level VerificationStatus: a request is
    `approved`, while the account becomes `verified` - the names differ on
    purpose so "one request was approved" is never confused with "the
    account is verified" during reviews and audits.

        pending  -> submitted, waiting for a reviewer
        approved -> reviewer accepted it (moves the account to `verified`)
        rejected -> reviewer declined it (moves the account to `rejected`)
    """

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class UserRole(StrEnum):
    """Authorization role on the account (Phase 6, second assignment).

    `user` is the default for every account - registration, email
    ownership, or signup order NEVER grant `owner`. The only supported
    way to become `owner` is the server-side CLI
    (`python -m app.cli make-owner <email>`), which requires shell access
    to the machine holding the database credentials. No API endpoint can
    set or change a role.

    `owner` authorizes the policy-management and verification-review
    endpoints (defense: any role value other than `owner` is denied -
    unknown/corrupt values fail closed).
    """

    USER = "user"
    OWNER = "owner"


class TravelPlanStatus(StrEnum):
    """Lifecycle of a travel plan (Phase 7).

        active    -> the trip is planned/open (the ONLY state discovery sees)
        paused    -> temporarily not seeking companions (kept, hidden)
        completed -> over; kept as history, never discovered

    No endpoint moves a plan to `expired` - plans whose `end_date` has
    passed are simply ineligible at read time (the project has no
    background jobs; documented in report.md).
    """

    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"


class PlanVisibility(StrEnum):
    """Who may see a travel plan (Phase 7).

    private      -> owner only (the SECURE DEFAULT)
    discoverable -> eligible to appear in travel-buddy discovery
                    (still subject to profile + account eligibility)
    """

    PRIVATE = "private"
    DISCOVERABLE = "discoverable"


class BuddyRequestStatus(StrEnum):
    """Lifecycle of a travel-partner request (Phase 7).

        pending   -> sent, awaiting the RECIPIENT's decision
        accepted  -> recipient agreed (terminal)
        rejected  -> recipient declined; requester may send a new request
        cancelled -> requester withdrew their own pending request (terminal)

    Transitions are enforced in the endpoint layer; the database adds
    partial UNIQUE constraints so at most one PENDING request exists per
    user pair in either direction.
    """

    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class ConversationStatus(StrEnum):
    """Lifecycle of a one-to-one message-request conversation (Phase 8).

    One row covers the unordered user pair (canonical low/high IDs), so
    the state machine below is the ONLY copy of the relationship state:

        pending   -> request sent, awaiting the RECIPIENT's decision
        accepted  -> recipient agreed; both parties may exchange messages
        rejected  -> recipient declined (terminal for this ask; an
                     explicit NEW request may move it back to pending)
        cancelled -> requester withdrew their own pending ask (same)

    Reopening after rejection/cancellation happens ONLY through an
    explicit new request call - never silently, never by reading history.
    """

    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
