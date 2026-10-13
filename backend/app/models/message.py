"""Persistent chat message table (Phase 8, text-only).

Plain language: one row = one text message inside an accepted
conversation. The sender is ALWAYS the authenticated account (derived
from the token's `sub` - never from the request body, so identity cannot
be forged). Messages are ordered by (created_at, id): the id tie-breaker
keeps pagination stable when two messages share a timestamp.

Deletion is SOFT and sender-only: deleting sets `is_deleted`/`deleted_at`
and reads return `body=None`; the row (and its place in history) is
never removed, so history is never silently rewritten. There is no edit
(the product does not require it).
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Text, Uuid, false
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.conversation import Conversation
    from app.models.user import User

# Longest message body the API accepts (validated at the schema layer).
MAX_MESSAGE_LENGTH = 2000


class ChatMessage(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One text message in a conversation."""

    __tablename__ = "messages"
    __table_args__ = (
        # History page shape: newest/oldest-first pages over (time, id).
        Index(
            "ix_messages_conversation_time",
            "conversation_id",
            "created_at",
            "id",
        ),
    )

    conversation_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("conversations.id", ondelete="RESTRICT"), index=True
    )

    # The sender. Always the token's account (endpoint-enforced); the
    # column exists so history can attribute each message.
    sender_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )

    body: Mapped[str] = mapped_column(Text, nullable=False)

    # Soft-delete state (sender-only delete). Reads return body=None once
    # set; the row itself is retained.
    is_deleted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    conversation: Mapped[Conversation] = relationship(back_populates="messages")
    sender: Mapped[User] = relationship(foreign_keys=[sender_id])
