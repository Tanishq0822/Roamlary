"""Request and response schemas for SOS incidents (Phase 5).

Plain language: an SOS incident is the user's "help me" record. These
schemas enforce three rules:

1. STRICT BODIES: extra="forbid" means any unexpected field is a 422 -
   clients cannot smuggle in `user_id` (ownership), `status` (lifecycle),
   or any server-controlled timestamp (`created_at`, `updated_at`,
   `cancelled_at`, `resolved_at`, `location_recorded_at`).

2. COORDINATES: latitude and longitude are optional but ALL-OR-NOTHING
   (one without the other is a 422), each range-checked (latitude
   -90..90, longitude -180..180). The server never obtains or guesses a
   user's location; it only stores what the client deliberately sends.

3. DESCRIPTION: optional; when provided it must be non-blank after
   trimming and at most 500 characters.

`location_recorded_at` is set by the SERVER clock when coordinates are
supplied (the moment of activation) - there is no client field for it.
"""

from datetime import UTC, datetime
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)

from app.models.enums import SosStatus


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


class SosEventCreate(BaseModel):
    """Body for POST /sos.

    Only `description`, `latitude`, and `longitude` are accepted. The
    incident is created in the `active` status by the server - there is
    no field for `user_id`, `id`, `status`, or any timestamp.
    """

    model_config = ConfigDict(extra="forbid")

    description: str | None = Field(None, max_length=500)
    latitude: float | None = Field(None, ge=-90, le=90)
    longitude: float | None = Field(None, ge=-180, le=180)

    @field_validator("description")
    @classmethod
    def strip_description(cls, value: str | None) -> str | None:
        """Trim; a blank description is REJECTED (not silently dropped).

        Unlike a check-in's optional note, an SOS description is a
        deliberate statement ("two men following me on the pier"). An
        empty or whitespace-only string is almost certainly a mistake,
        so it is refused with 422 instead of stored as NULL.
        """
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError(
                "description must not be blank; provide a short note or omit the field entirely"
            )
        return stripped

    @model_validator(mode="after")
    def coordinates_are_all_or_nothing(self) -> "SosEventCreate":
        """Latitude and longitude must be provided together or not at all.

        A single coordinate cannot locate anything on a map, so silently
        storing one would create misleading half-location data.
        """
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be provided together or omitted entirely")
        return self


class SosEventRead(BaseModel):
    """The public shape of an SOS incident.

    Timestamps are returned as UTC. `user_id` identifies the (only)
    owner, so it is safe to expose - a client can only ever see its own
    incidents because every query filters by the token's user.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    status: SosStatus
    description: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    location_recorded_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    cancelled_at: datetime | None = None
    resolved_at: datetime | None = None

    @field_serializer(
        "location_recorded_at",
        "created_at",
        "updated_at",
        "cancelled_at",
        "resolved_at",
    )
    def _serialize_utc(self, value: datetime | None) -> datetime | None:
        """Guarantee every timestamp leaves this API in UTC (see _to_utc)."""
        return _to_utc(value)
