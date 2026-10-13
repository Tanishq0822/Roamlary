"""Meetup, membership, invitation, and announcement schemas (Phases 9-10).

Plain language: events are read through ONE privacy rule — the public
shape never carries the exact venue (`venue_details`); that field is
populated only for the host and approved participants of private
events, and is always None everywhere else (discovery, lists, public
reads). Membership reads carry display names (needed to manage a guest
list) but never emails, roles, or verification states.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.enums import (
    InvitationStatus,
    MeetupCategory,
    MeetupStatus,
    MeetupVisibility,
    MembershipStatus,
    ParticipationPolicy,
)


class MeetupCreate(BaseModel):
    """Body for POST /meetups (and POST /parties, which forces the party
    kind and private visibility server-side)."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(..., min_length=1, max_length=100)
    description: str | None = Field(None, max_length=1000)
    category: MeetupCategory
    start_at: datetime
    end_at: datetime
    timezone: str | None = Field(None, max_length=60)
    capacity: int = Field(20, ge=2, le=500)
    visibility: MeetupVisibility = MeetupVisibility.PUBLIC
    participation: ParticipationPolicy = ParticipationPolicy.APPROVAL
    location_text: str | None = Field(None, max_length=200)
    venue_details: str | None = Field(None, max_length=500)

    @field_validator("title")
    @classmethod
    def title_must_be_nonblank(cls, value: str) -> str:
        """A blank title is a 422 here (not a NULL that dies at the
        database): after-validators are not re-validated, so this field
        gets its own rejecting validator instead of the blank-to-NULL
        cleaner below."""
        stripped = value.strip()
        if not stripped:
            raise ValueError("title must not be blank")
        return stripped

    @field_validator("description", "location_text", "venue_details", "timezone")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        """Trim text; blank optionals become NULL."""
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("start_at", "end_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        """Naive datetimes are refused: event times without a zone start
        flame wars about whose midnight it is (the Phase 4 convention)."""
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("event times must carry a timezone (ISO 8601 with Z/offset)")
        return value

    @model_validator(mode="after")
    def end_after_start(self) -> "MeetupCreate":
        """End must be after start (the database CHECK agrees)."""
        if self.end_at <= self.start_at:
            raise ValueError("end_at must be after start_at")
        return self


class MeetupPatch(BaseModel):
    """Body for PATCH (host only). Every field optional; kind is
    immutable (a meetup never morphs into a party or vice versa)."""

    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = Field(None, max_length=1000)
    category: MeetupCategory | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    timezone: str | None = Field(None, max_length=60)
    capacity: int | None = Field(None, ge=2, le=500)
    visibility: MeetupVisibility | None = None
    participation: ParticipationPolicy | None = None
    location_text: str | None = Field(None, max_length=200)
    venue_details: str | None = Field(None, max_length=500)

    @field_validator("title")
    @classmethod
    def title_must_be_nonblank(cls, value: str | None) -> str | None:
        """An explicitly blank title is 422 (None = not provided, which
        is fine and leaves the stored title alone)."""
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("title must not be blank")
        return stripped

    @field_validator("description", "location_text", "venue_details", "timezone")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("start_at", "end_at")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("event times must carry a timezone (ISO 8601 with Z/offset)")
        return value


class MeetupRead(BaseModel):
    """One event as the caller may see it.

    `venue_details` is populated ONLY for the host and approved
    participants of private events - everywhere else it is None BY
    CONSTRUCTION (the endpoint builds this shape, never the row).
    `my_membership` is the caller's own membership state (or "none").
    """

    model_config = ConfigDict(extra="forbid")

    id: UUID
    host_id: UUID
    host_display_name: str
    kind: str
    title: str
    description: str | None
    category: MeetupCategory
    start_at: datetime
    end_at: datetime
    timezone: str | None
    capacity: int
    approved_count: int
    visibility: MeetupVisibility
    participation: ParticipationPolicy
    status: MeetupStatus
    location_text: str | None
    venue_details: str | None
    my_membership: str
    created_at: datetime
    updated_at: datetime


class MembershipRead(BaseModel):
    """One guest-list row (display name for management; nothing private)."""

    model_config = ConfigDict(extra="forbid")

    user_id: UUID
    display_name: str
    status: MembershipStatus
    decided_at: datetime | None


class InvitationCreate(BaseModel):
    """Body for POST /parties/{id}/invite. Exactly one field: who."""

    model_config = ConfigDict(extra="forbid")

    invitee_id: UUID


class InvitationRead(BaseModel):
    """One invitation as host or invitee sees it."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    meetup_id: UUID
    event_title: str
    inviter_id: UUID
    invitee_id: UUID
    invitee_display_name: str
    status: InvitationStatus
    responded_at: datetime | None
    created_at: datetime


class InvitationList(BaseModel):
    """My incoming invitations, newest first."""

    model_config = ConfigDict(extra="forbid")

    total: int
    offset: int
    limit: int
    results: list[InvitationRead]


class AnnouncementCreate(BaseModel):
    """Body for POST .../announcements (host only). One bulletin."""

    model_config = ConfigDict(extra="forbid")

    body: str = Field(..., min_length=1, max_length=500)

    @field_validator("body")
    @classmethod
    def strip_nonblank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("body must not be blank")
        return stripped


class AnnouncementRead(BaseModel):
    """One host bulletin as a participant reads it."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    meetup_id: UUID
    author_display_name: str
    body: str
    created_at: datetime
