"""Trusted contact table.

Plain language: a person the user wants notified during an SOS. Every
contact MUST belong to a user (`user_id` foreign key, not nullable).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.user import User


class TrustedContact(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One emergency contact owned by one user."""

    __tablename__ = "trusted_contacts"

    # RESTRICT: a user with saved contacts cannot be deleted at the
    # database level - deliberate protection of safety data.
    user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )

    name: Mapped[str] = mapped_column(String(80), nullable=False)

    # E.164-style phone numbers fit comfortably in 32 characters.
    phone: Mapped[str] = mapped_column(String(32), nullable=False)

    email: Mapped[str | None] = mapped_column(String(254))

    # The user who owns this contact ("back_populates" connects the two
    # directions of the same relationship defined on User).
    owner: Mapped[User] = relationship(back_populates="trusted_contacts")

    # Optional label for how the contact knows the user ("mother",
    # "friend", "colleague"). Added in Phase 4.
    #
    # IMPORTANT ORDERING NOTE: this column is deliberately declared AFTER
    # the `owner` relationship above. Inside a class body, the name
    # `relationship` refers to whatever was assigned most recently; if
    # this column were declared first, the `owner = relationship(...)`
    # line would try to CALL this column and crash. One concept = one
    # name ("relationship") everywhere: Python, database, and API.
    relationship: Mapped[str | None] = mapped_column(String(50))
