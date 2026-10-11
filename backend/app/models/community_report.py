"""Community safety report table.

Plain language: a crowd-sourced observation like "street lights broken
on Market Square". Reports are tied to the authenticated user who
submitted them (for accountability), but the content focuses on the
LOCATION and the concern - not on tracking people.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import CheckConstraint, Float, ForeignKey, String, Text, Uuid
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
            "status IN ('pending', 'approved', 'rejected')",
            name="status_valid",
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

    # Short machine-friendly category (e.g. "lighting", "theft", "road").
    # No hard-coded list yet: categories are a Phase 6 product decision.
    category: Mapped[str] = mapped_column(String(40), nullable=False)

    description: Mapped[str] = mapped_column(Text, nullable=False)

    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)

    status: Mapped[str] = mapped_column(String(20), default=ReportStatus.PENDING, nullable=False)

    user: Mapped[User] = relationship(back_populates="community_reports")
