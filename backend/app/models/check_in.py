"""Safety check-in table.

Plain language: a check-in is a promise like "ping me by 22:00 or
raise the alarm". `due_at` is the optional deadline; `completed_at` is
when the user actually answered; `status` tracks the lifecycle
(pending -> safe / needs_help, or pending -> expired once the deadline
passes in a later phase).
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import CheckInStatus

if TYPE_CHECKING:
    from app.models.user import User


class CheckIn(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One scheduled safety check-in belonging to one user."""

    __tablename__ = "check_ins"
    __table_args__ = (
        # Belt-and-braces: even raw SQL inserts (bypassing Python) cannot
        # store an invalid status.
        CheckConstraint(
            "status IN ('pending', 'safe', 'needs_help', 'expired')",
            name="status_valid",
        ),
    )

    user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )

    # index=True: the future expiry job repeatedly queries pending
    # check-ins, so this lookup deserves an index.
    status: Mapped[str] = mapped_column(
        String(20), default=CheckInStatus.PENDING, nullable=False, index=True
    )

    # Optional deadline (Phase 0 design allows check-ins without one).
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Set when the user answered (safe / needs_help).
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(back_populates="check_ins")
