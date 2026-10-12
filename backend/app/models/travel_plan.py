"""Travel plan table (Phase 7).

Plain language: one row = "I plan to be in <destination> between <start>
and <end>". Plans are owned by an account; only DISCOVERABLE + ACTIVE +
non-expired plans ever enter discovery. Expiry is evaluated at READ time
(`end_date < today` is excluded from discovery and flagged in API
responses) because the project has no background jobs - documented, not
accidental.

Matching keys: `destination_normalized` / `region_normalized` hold the
lowercased, whitespace-collapsed form written by the application layer.
Discovery COMPARES these strings; it never claims a destination was
externally verified. No GPS coordinates are stored on plans at all -
travel discovery deliberately does not track live position.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    String,
    Uuid,
    false,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import PlanVisibility, TravelPlanStatus

if TYPE_CHECKING:
    from app.models.user import User


class TravelPlan(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One intended trip of one account."""

    __tablename__ = "travel_plans"
    __table_args__ = (
        CheckConstraint(
            "end_date >= start_date",
            name="end_date_after_start",
        ),
        CheckConstraint(
            "status IN ('active', 'paused', 'completed')",
            name="status_valid",
        ),
        CheckConstraint(
            "visibility IN ('private', 'discoverable')",
            name="visibility_valid",
        ),
        # Composite index matching the discovery query shape
        # (normalized destination + eligibility states).
        Index(
            "ix_travel_plans_discovery",
            "destination_normalized",
            "status",
            "visibility",
        ),
        Index("ix_travel_plans_dates", "start_date", "end_date"),
    )

    # The owning account. RESTRICT like every other child table.
    user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )

    # Display form (trimmed, whitespace-collapsed) ...
    destination: Mapped[str] = mapped_column(String(80), nullable=False)
    # ... and the normalized matching key (also lowercased) written by the
    # application layer. Both are stored so the API can show the original
    # spelling while matching stays deterministic.
    destination_normalized: Mapped[str] = mapped_column(String(80), nullable=False)

    # Optional broad region/country + its normalized matching key.
    region: Mapped[str | None] = mapped_column(String(80))
    region_normalized: Mapped[str | None] = mapped_column(String(80))

    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Flexible dates widen this plan's overlap window by a fixed grace
    # period at MATCH time (see app/core/matching.py) - the stored dates
    # are never rewritten.
    flexible_dates: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )

    # Lifecycle (server-interpreted; clients cannot invent states).
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=TravelPlanStatus.ACTIVE, server_default="active"
    )

    # Privacy: plans are PRIVATE unless the owner opts them into discovery.
    visibility: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=PlanVisibility.PRIVATE,
        server_default="private",
    )

    user: Mapped[User] = relationship(back_populates="travel_plans")
