"""Host announcement table (Phases 9-10, event communication).

Plain language: the host's one-way bulletin for an event ("meet at gate
2, not gate 1"). Announcements are host-posted and participant-read;
there are deliberately NO replies here (Phase 8 chat stays 1:1 - no
group chat is created as a shortcut). Participants are exactly the host
plus approved members; announcements freeze with cancelled/completed
events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.meetup import Meetup
    from app.models.user import User


class MeetupAnnouncement(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One host-posted notice for one event."""

    __tablename__ = "meetup_announcements"

    meetup_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("meetups.id", ondelete="RESTRICT"), index=True
    )
    # Always the host (endpoint-enforced); stored for attribution.
    author_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="RESTRICT"))
    body: Mapped[str] = mapped_column(Text, nullable=False)

    meetup: Mapped[Meetup] = relationship(back_populates="announcements")
    author: Mapped[User] = relationship(foreign_keys=[author_id])
