"""Request and response schemas for community safety reports (Phase 6).

Plain language: a report is one traveller's observation about a PLACE
("dark street behind the station"), not about a person. These schemas
enforce four rules:

1. STRICT BODIES: extra="forbid" means any unexpected field is a 422 -
   clients cannot smuggle in `user_id` (submitter), `status`
   (moderation state), `id`, or any timestamp.

2. CATEGORY: a closed set from the Phase 6 product decision
   (ReportCategory). Unknown categories are rejected with 422; the
   database enforces the same set through a CHECK constraint.

3. COORDINATES: required and range-checked (latitude -90..90,
   longitude -180..180). Every report must say WHERE it applies - that
   is the entire point of a location-based safety report. The server
   never obtains or guesses a location; it only stores what the client
   deliberately sends.

4. DESCRIPTION: required, trimmed, 1..500 characters (matches the
   check-in note / SOS description limits used elsewhere in the API).

PRIVACY: `ReportRead` deliberately EXCLUDES the submitter. The table
stores `user_id` for accountability and abuse follow-up, but the public
API never exposes who filed a report - reports are about places, not
people. Every response carries `status` so clients can distinguish a
plain user-submitted report (`pending`) from a moderated one
(`approved`); `rejected` reports are hidden entirely.
"""

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

from app.models.enums import ReportCategory, ReportStatus


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


class ReportCreate(BaseModel):
    """Body for POST /reports.

    Only `category`, `description`, `latitude`, and `longitude` are
    accepted. The report is created in the `pending` (unreviewed)
    moderation state by the server - there is no field for `user_id`,
    `status`, `id`, or any timestamp.
    """

    model_config = ConfigDict(extra="forbid")

    category: ReportCategory
    description: str = Field(..., min_length=1, max_length=500)
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)

    @field_validator("description")
    @classmethod
    def strip_description(cls, value: str) -> str:
        """Trim; a blank description is REJECTED (not silently dropped).

        A report without words is an empty accusation - the category and
        coordinates already say where and roughly what; the description
        carries the actual observation.
        """
        stripped = value.strip()
        if not stripped:
            raise ValueError("description must not be blank; explain what you observed")
        return stripped


class ReportRead(BaseModel):
    """The public shape of a community safety report.

    NOTE THE ABSENCE OF `user_id`: the submitter's identity is never
    exposed (reports are about places, not people). `reviewed_at` stamps
    the moderation decision for auditability; the reviewer's identity
    stays server-side. Timestamps are returned as UTC.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    category: ReportCategory
    status: ReportStatus
    description: str
    latitude: float | None = None
    longitude: float | None = None
    created_at: datetime
    updated_at: datetime
    reviewed_at: datetime | None = None

    @field_serializer("created_at", "updated_at", "reviewed_at")
    def _serialize_utc(self, value: datetime | None) -> datetime | None:
        """Guarantee every timestamp leaves this API in UTC (see _to_utc)."""
        return _to_utc(value)


class ReportModerate(BaseModel):
    """Body for PATCH /reports/{report_id}/moderate (owner only).

    Exactly one field: the target moderation state. `pending` is not an
    allowed target (review never un-happens); transitions are validated
    against the lifecycle in the endpoint.
    """

    model_config = ConfigDict(extra="forbid")

    status: Literal[ReportStatus.APPROVED, ReportStatus.REJECTED, ReportStatus.RESOLVED]
