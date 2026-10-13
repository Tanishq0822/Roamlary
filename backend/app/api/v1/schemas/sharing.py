"""Notification and trip-share schemas (Phase 12).

Plain language: notification reads expose delivery STATE, never
credentials or message content beyond the event facts. Trip-share reads
expose the plan facts a viewer is entitled to - never anyone's private
records.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.enums import NotificationStatus


class NotificationRead(BaseModel):
    """One notification as its recipient sees it."""

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    kind: str
    title: str
    body: str
    channel: str
    status: NotificationStatus
    attempts: int
    last_error: str | None
    read_at: datetime | None
    created_at: datetime


class NotificationList(BaseModel):
    """My notifications, newest first."""

    model_config = ConfigDict(extra="forbid")

    total: int
    offset: int
    limit: int
    results: list[NotificationRead]


class TripShareCreate(BaseModel):
    """Body for POST /trip-shares. An optional plan plus an expiry.

    `expires_at` must be future and at most 90 days out (a share is a
    bounded grant, not a standing permission). Naive datetimes are 422.
    """

    model_config = ConfigDict(extra="forbid")

    plan_id: UUID | None = None
    expires_at: datetime


class TripShareRead(BaseModel):
    """One share grant as its owner sees it."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    plan_id: UUID | None
    plan_destination: str | None
    expires_at: datetime
    revoked_at: datetime | None
    created_at: datetime


class TripShareList(BaseModel):
    """Share grants, newest first."""

    model_config = ConfigDict(extra="forbid")

    total: int
    offset: int
    limit: int
    results: list[TripShareRead]


class SharedItineraryRead(BaseModel):
    """What an accepted travel partner may see of a live share: the plan
    facts plus the owner's display name and the grant window. Never
    messages, SOS records, or anyone else's data."""

    model_config = ConfigDict(extra="forbid")

    share_id: UUID
    owner_display_name: str
    plan_destination: str | None
    plan_start_date: str | None
    plan_end_date: str | None
    expires_at: datetime
