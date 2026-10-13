"""Person-to-person blocking relationship table (Phase 8).

Plain language: one row = "blocker wants nothing from blocked". The
block stops BOTH directions: once A blocks B, neither A->B nor B->A
messaging or message requests are allowed, and B disappears from A's
travel-buddy discovery (and vice versa) plus from new travel-partner
requests. Blocking is independent of discoverability switches and of
identity verification - it is its own layer.

Policy for existing conversations: history STAYS readable to both
participants (no silent deletion of records), but sending new messages
is refused while the block stands. Unblocking restores sending; it never
resurrects deleted rows (nothing was deleted).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.user import User


class UserBlock(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One directed block: blocker_id refuses contact with blocked_id."""

    __tablename__ = "user_blocks"
    __table_args__ = (
        CheckConstraint(
            "blocker_id <> blocked_id",
            name="no_self_block",
        ),
        # No duplicate block records, even racing (brief item: duplicate
        # block records must be prevented - at the database).
        UniqueConstraint(
            "blocker_id",
            "blocked_id",
            name="uq_user_blocks_pair",
        ),
    )

    blocker_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    blocked_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )

    # No User-side backrefs: the two user FKs would make the reverse side
    # ambiguous; every query selects block rows directly (same convention
    # as travel-partner requests and conversations).
    blocker: Mapped[User] = relationship(foreign_keys=[blocker_id])
    blocked: Mapped[User] = relationship(foreign_keys=[blocked_id])
