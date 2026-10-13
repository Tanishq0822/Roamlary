"""House-party invitation table (Phase 10).

Plain language: one row = one host's invitation of one user to one
private event. UNIQUE per (meetup, invitee): re-inviting after a
decline/revoke reuses the row (fresh pending state), so invitation
replay - accepting the same invite twice, or two racing accepts - is
structurally impossible. Invitations reference private events only;
public meetups use the join flow instead (endpoint-enforced).
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import InvitationStatus

if TYPE_CHECKING:
    from app.models.meetup import Meetup
    from app.models.user import User


class EventInvitation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One invitation of one user to one private event."""

    __tablename__ = "event_invitations"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'accepted', 'declined', 'revoked', 'expired')",
            name="status_valid",
        ),
        UniqueConstraint("meetup_id", "invitee_id", name="uq_event_invitations_pair"),
    )

    meetup_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("meetups.id", ondelete="RESTRICT"), index=True
    )
    # The host who sent the current invitation (always the event host).
    inviter_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="RESTRICT"))
    invitee_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=InvitationStatus.PENDING, server_default="pending"
    )
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    meetup: Mapped[Meetup] = relationship(back_populates="invitations")
    invitee: Mapped[User] = relationship(foreign_keys=[invitee_id])
