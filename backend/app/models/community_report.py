"""Community safety report table.

Plain language: a crowd-sourced observation like "street lights broken
on Market Square". Reports are tied to the authenticated user who
submitted them (for accountability), but the content focuses on the
LOCATION and the concern - not on tracking people. Phase 6 makes that
explicit: `user_id` stays in the table (ownership/abuse follow-up) but is
NEVER part of the public API response.

Phase 6 also turns the previously loose `category` string into a fixed
set (ReportCategory) enforced by a CHECK constraint, and defines who can
see a report: everything EXCEPT `status='rejected'` is publicly readable
to authenticated users. `approved`/`rejected` belong to a future
moderation system - no endpoint sets them today.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import ReportStatus

if TYPE_CHECKING:
    from app.models.user import User


class CommunityReport(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One community-submitted safety observation."""

    __tablename__ = "community_reports"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'resolved')",
            name="status_valid",
        ),
        # Phase 6: the category list is now a closed set (was a loose
        # string in Phase 2 - see ReportCategory in models/enums.py).
        CheckConstraint(
            "category IN ('unsafe_area', 'harassment', 'suspicious_activity',"
            " 'road_hazard', 'poor_lighting', 'other')",
            name="category_valid",
        ),
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

    # Short machine-friendly category from the Phase 6 closed set
    # (ReportCategory). Enforced here AND by the DB CHECK above.
    category: Mapped[str] = mapped_column(String(40), nullable=False)

    description: Mapped[str] = mapped_column(Text, nullable=False)

    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)

    status: Mapped[str] = mapped_column(String(20), default=ReportStatus.PENDING, nullable=False)

    # Moderation audit (Phase 11, owner-only writes): who decided and
    # when. NULL while pending (never reviewed).
    reviewed_by: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT")
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(back_populates="community_reports", foreign_keys=[user_id])
