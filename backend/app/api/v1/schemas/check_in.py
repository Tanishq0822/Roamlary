"""Request and response schemas for safety check-ins (Phase 4).

Plain language: a check-in is the user's promise, "I'll be back by
<due_at> - if you don't hear from me, worry." These schemas enforce the
two timestamp policies of the API:

1. TIMEZONE: every timestamp the client sends must be timezone-aware
   (ending in 'Z' or carrying an offset like +05:30). A "naive" timestamp
   with no timezone is rejected with 422, because guessing a timezone for
   a safety deadline could be off by hours. Everything is converted to
   UTC before storage, and responses always come back in UTC.

2. PAST DEADLINES: `due_at` must be a future moment. Scheduling a
   check-in whose deadline has already passed is rejected with 422 -
   it would be a promise that was broken before it was made.

`user_id`, `status` (on create), `completed_at`, and all timestamps are
absent from the request schemas and extra="forbid" is set, so clients
cannot forge ownership, pick an initial status, or backdate completion.
"""

from datetime import UTC, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

from app.models.enums import CheckInStatus


def _to_utc(value: datetime | None) -> datetime | None:
    """Normalize a datetime to UTC for the response.

    The API contract says responses come back in UTC. We store UTC, but
    the database driver decides whether it comes back timezone-aware:
    PostgreSQL's timestamptz returns an aware datetime, while SQLite
    returns a naive one. Rather than let the wire format depend on which
    database is running, every outgoing timestamp is normalized here -
    naive values are assumed to already be UTC (because that is what we
    stored), and aware values are converted.
    """
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _ensure_aware(value: datetime | None) -> datetime | None:
    """Reject naive datetimes; convert aware ones to UTC.

    `tzinfo is None` means the string had no zone information at all.
    `utcoffset() is None` catches the rare object that claims a tzinfo
    but still returns no offset. Both are treated as "no timezone
    supplied" and rejected by the caller.
    """
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(
            "timestamp must include a timezone, e.g. 2026-10-12T18:30:00Z "
            "or 2026-10-12T18:30:00+05:30"
        )
    return value.astimezone(UTC)


class CheckInCreate(BaseModel):
    """Body for POST /check-ins.

    Only `note` and `due_at` are accepted. A check-in is created in the
    `pending` status by the server - the client cannot choose a status,
    and there is no field for `user_id`, `id`, or `completed_at`.
    """

    model_config = ConfigDict(extra="forbid")

    note: str | None = Field(None, max_length=500)
    due_at: datetime | None = None

    @field_validator("note")
    @classmethod
    def strip_note(cls, value: str | None) -> str | None:
        """Trim; blank becomes None so responses never show empty strings."""
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("due_at")
    @classmethod
    def validate_due_at(cls, value: datetime | None) -> datetime | None:
        """Must be timezone-aware and in the future (see module docstring)."""
        value = _ensure_aware(value)
        if value is not None and value <= datetime.now(UTC):
            raise ValueError(
                "due_at must be in the future; a check-in cannot be "
                "scheduled with a deadline that has already passed"
            )
        return value


class CheckInUpdate(BaseModel):
    """Body for PATCH /check-ins/{checkin_id}.

    Allowed to change: `note`, `due_at`, and `status`. `status` is
    validated by the route handler against the transition rules (only a
    `pending` check-in may move, and only to safe/needs_help/cancelled);
    here we only enforce that the value is a known status. `completed_at`
    is deliberately absent: it is set by the server when a check-in is
    answered, never by client data.
    """

    model_config = ConfigDict(extra="forbid")

    note: str | None = Field(None, max_length=500)
    due_at: datetime | None = None
    status: CheckInStatus | None = None

    @field_validator("note")
    @classmethod
    def strip_note(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("due_at")
    @classmethod
    def validate_due_at(cls, value: datetime | None) -> datetime | None:
        """Same rule as create: timezone-aware and in the future."""
        value = _ensure_aware(value)
        if value is not None and value <= datetime.now(UTC):
            raise ValueError(
                "due_at must be in the future; a check-in cannot be "
                "scheduled with a deadline that has already passed"
            )
        return value


class CheckInRead(BaseModel):
    """The public shape of a check-in.

    Timestamps are returned as UTC. `user_id` identifies the (only)
    owner, so it is safe to expose - a client can only ever see its own
    records because every query filters by the token's user.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    status: CheckInStatus
    note: str | None = None
    due_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    @field_serializer("due_at", "completed_at", "created_at", "updated_at")
    def _serialize_utc(self, value: datetime | None) -> datetime | None:
        """Guarantee every timestamp leaves this API in UTC (see _to_utc)."""
        return _to_utc(value)
