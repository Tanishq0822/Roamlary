"""SOS event table.

Plain language: one row = one (SIMULATED) emergency incident. This
prototype does NOT contact emergency services. Location columns are
optional and only stored when a location is intentionally recorded.
The lifecycle (active -> acknowledged -> resolved / false_alarm)
supports the later SOS workflow without implementing its logic yet.
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
        CheckConstraint(
            "status IN ('active', 'acknowledged', 'resolved', 'false_alarm')",
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

    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)

    # Set when the incident reaches a final state (resolved/false_alarm).
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(back_populates="sos_events")
