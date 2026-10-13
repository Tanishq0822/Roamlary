"""SOS event table.

Plain language: one row = one (SIMULATED) emergency incident. This
prototype does NOT contact emergency services. Location columns are
optional and only stored when a location is intentionally recorded.

Phase 5 lifecycle (enforced by the API and a CHECK constraint):

    active -> cancelled   (user retracted the SOS; terminal)
    active -> resolved    (user marked it handled; terminal)

`acknowledged` and `false_alarm` are Phase 2 values kept for a later
phase but unreachable for now - no responder system exists to
acknowledge an incident.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import SosStatus

if TYPE_CHECKING:
    from app.models.user import User


class SosEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One simulated SOS incident belonging to one user."""

    __tablename__ = "sos_events"
    __table_args__ = (
        # 'cancelled' added in Phase 5 (user-retracted incident).
        CheckConstraint(
            "status IN ('active', 'acknowledged', 'resolved', 'false_alarm', 'cancelled')",
            name="status_valid",
        ),
        # Guard rails against corrupted coordinates (degrees).
        CheckConstraint(
            "latitude IS NULL OR latitude BETWEEN -90 AND 90",
            name="latitude_range",
        ),
        CheckConstraint(
            "longitude IS NULL OR longitude BETWEEN -180 AND 180",
            name="longitude_range",
        ),
    )

    user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )

    status: Mapped[str] = mapped_column(String(20), default=SosStatus.ACTIVE, nullable=False)

    # Optional short note from the user ("ambulance needed at the hostel").
    # Nothing is ever sent anywhere - this only stores text. Phase 5.
    description: Mapped[str | None] = mapped_column(String(500))

    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)

    # When the location above was captured (server clock at activation).
    # Only set if coordinates were provided. Phase 5.
    location_recorded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Set when the incident reaches a final state: resolved_at when the
    # user marked it handled, cancelled_at when the user retracted it.
    # Both are server-clock stamps, never client data. cancelled_at is
    # Phase 5.
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Set when the owner acknowledges the incident (Phase 12: "someone
    # responsible has seen this and is handling it"). Server clock, like
    # every other transition stamp. acknowledged -> resolved/cancelled
    # stays allowed; nothing else moves out of acknowledged.
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(back_populates="sos_events")
