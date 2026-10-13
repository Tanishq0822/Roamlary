"""Meetup and house-party event table (Phases 9-10, shared foundation).

Plain language: one row = one group activity with a host. Meetups are
publicly discoverable with open or approval-based joining; house
parties share the SAME table and lifecycle but are invitation-only and
never appear in public discovery (kind + access rules switch; the
lifecycle does not fork - the brief forbids a second incompatible
event system).

Safety-shaped fields: capacity is CHECK-guarded (2-500) and enforced
against overbooking at join time; end must be after start; a cancelled
or completed event freezes joins/invites/announcements; the exact venue
(`venue_details`) is stored but NEVER served to the public - only the
host and approved participants of a private event may read it (the
public `location_text` carries at most an area for parties).
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import MeetupKind, MeetupStatus, MeetupVisibility, ParticipationPolicy

if TYPE_CHECKING:
    from app.models.event_invitation import EventInvitation
    from app.models.meetup_announcement import MeetupAnnouncement
    from app.models.meetup_membership import MeetupMembership
    from app.models.user import User

# Closed activity set, mirrored by the database CHECK below and the
# migration DDL exactly.
_CATEGORY_SQL = (
    "category IN ('hiking', 'food', 'culture', 'adventure', 'leisure', 'nightlife', 'other')"
)


class Meetup(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One group activity (meetup) or invitation-only house party."""

    __tablename__ = "meetups"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('meetup', 'house_party')",
            name="kind_valid",
        ),
        CheckConstraint(
            "status IN ('active', 'cancelled', 'completed')",
            name="status_valid",
        ),
        CheckConstraint(
            "visibility IN ('public', 'private')",
            name="visibility_valid",
        ),
        CheckConstraint(
            "participation IN ('open', 'approval')",
            name="participation_valid",
        ),
        CheckConstraint("end_at > start_at", name="end_after_start"),
        CheckConstraint(_CATEGORY_SQL, name="category_valid"),
        CheckConstraint(
            "capacity IS NULL OR (capacity >= 2 AND capacity <= 500)",
            name="capacity_range",
        ),
        Index(
            "ix_meetups_discovery",
            "kind",
            "status",
            "visibility",
            "start_at",
        ),
    )

    host_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )

    kind: Mapped[str] = mapped_column(
        String(20), nullable=False, default=MeetupKind.MEETUP, server_default="meetup"
    )
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    # Closed activity set (validated at the schema layer too).
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # IANA timezone name for display ("Asia/Kolkata"); storage stays UTC.
    timezone: Mapped[str | None] = mapped_column(String(60))
    capacity: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=20, server_default="20"
    )
    visibility: Mapped[str] = mapped_column(
        String(20), nullable=False, default=MeetupVisibility.PUBLIC, server_default="public"
    )
    participation: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ParticipationPolicy.APPROVAL, server_default="approval"
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=MeetupStatus.ACTIVE, server_default="active"
    )
    # Public meeting point / area. For house parties this must stay an
    # AREA (endpoint guidance); the exact address lives in venue_details.
    location_text: Mapped[str | None] = mapped_column(String(200))
    # Exact venue/address. NEVER served publicly (endpoint-enforced).
    venue_details: Mapped[str | None] = mapped_column(Text)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    host: Mapped[User] = relationship(foreign_keys=[host_id])
    memberships: Mapped[list[MeetupMembership]] = relationship(back_populates="meetup")
    invitations: Mapped[list[EventInvitation]] = relationship(back_populates="meetup")
    announcements: Mapped[list[MeetupAnnouncement]] = relationship(back_populates="meetup")
