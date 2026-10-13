"""One-to-one message-request conversation table (Phase 8).

Plain language: one row = the messaging relationship between TWO users,
with no direction. The pair is stored canonically (user_low_id <=
user_high_id by UUID value, see app/core/pairing.py) with a UNIQUE
constraint, so repeated requests can NEVER create a duplicate pending
conversation - not even in opposite directions, not even racing. A new
request after rejection/cancellation reuses this same row (back to
pending with the new requester recorded); nothing is ever deleted.

Lifecycle: pending -> accepted | rejected | cancelled, enforced in the
endpoint layer. `requested_by` records who sent the current ask (who may
cancel it); the OTHER party is the recipient (who may accept/reject it).

An ACCEPTED travel-partner request does NOT create or authorize a
conversation: chat needs its own explicit message request and accept.
That rule is enforced by simply never reading travel tables here.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import ConversationStatus

if TYPE_CHECKING:
    from app.models.message import ChatMessage
    from app.models.user import User


class Conversation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """The messaging relationship between exactly two users."""

    __tablename__ = "conversations"
    __table_args__ = (
        CheckConstraint(
            "user_low_id <> user_high_id",
            name="no_self_conversation",
        ),
        CheckConstraint(
            "status IN ('pending', 'accepted', 'rejected', 'cancelled')",
            name="status_valid",
        ),
        # One row per unordered pair, forever: the structural guarantee
        # behind "no duplicate pending conversations" (brief item 4.8).
        UniqueConstraint(
            "user_low_id",
            "user_high_id",
            name="uq_conversations_pair",
        ),
        Index(
            "ix_conversations_low_status",
            "user_low_id",
            "status",
        ),
        Index(
            "ix_conversations_high_status",
            "user_high_id",
            "status",
        ),
    )

    # Canonical unordered pair (low <= high by UUID int value). ALWAYS
    # written through app/core/pairing.canonical_pair - never hand-ordered.
    user_low_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    user_high_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=ConversationStatus.PENDING,
        server_default="pending",
    )

    # Who sent the CURRENT ask. NULL is impossible: every row starts as a
    # request from someone. Updated when a terminal row is re-requested.
    requested_by: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="RESTRICT"))

    # Server clock when the recipient decided (or the requester
    # cancelled). NULL while pending.
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # The two participants exist as relationships for eager loading
    # (display names in list responses). No User-side backref: the two
    # user FKs would make the reverse side ambiguous, and every query
    # selects conversation rows directly (same convention as Phase 7
    # travel-partner requests).
    user_low: Mapped[User] = relationship(foreign_keys=[user_low_id])
    user_high: Mapped[User] = relationship(foreign_keys=[user_high_id])
    requester: Mapped[User] = relationship(foreign_keys=[requested_by])
    messages: Mapped[list[ChatMessage]] = relationship(back_populates="conversation")
