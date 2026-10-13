"""Event membership table (Phases 9-10).

Plain language: one row = one user's relationship to one event. Joining,
requesting, approval, decline, leaving, and host removal are all STATES
of this row (UNIQUE per meetup/user - no duplicate memberships, even
racing). A declined/removed/left row may be reopened by an explicit new
join (same rule as chat/travel requests); nothing reopens silently.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import MembershipStatus

if TYPE_CHECKING:
    from app.models.meetup import Meetup
    from app.models.user import User


class MeetupMembership(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One user's membership state in one event."""

    __tablename__ = "meetup_memberships"
    __table_args__ = (
        CheckConstraint(
            "status IN ('requested', 'approved', 'declined', 'removed', 'left')",
            name="status_valid",
        ),
        UniqueConstraint("meetup_id", "user_id", name="uq_meetup_memberships_pair"),
    )

    meetup_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("meetups.id", ondelete="RESTRICT"), index=True
    )
    user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=MembershipStatus.REQUESTED, server_default="requested"
    )
    # Server clock of the last host/member decision; NULL while requested.
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Who decided (host id for approve/decline/remove). Auditability.
    decided_by: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT")
    )

    meetup: Mapped[Meetup] = relationship(back_populates="memberships")
    user: Mapped[User] = relationship(foreign_keys=[user_id])
