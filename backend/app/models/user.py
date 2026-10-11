"""User profile table.

Plain language: one row = one Roamlary account. No passwords are stored
here. `firebase_uid` is an optional external reference: when Firebase
Authentication is integrated in a later phase, this column stores the
identifier Firebase gives the user. It stays empty until then.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.check_in import CheckIn
    from app.models.community_report import CommunityReport
    from app.models.sos_event import SosEvent
    from app.models.trusted_contact import TrustedContact


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """The application user's profile."""

    __tablename__ = "users"

    # Optional link to an external auth provider (Firebase in a later
    # phase). Unique + indexed because login looks users up by this value.
    firebase_uid: Mapped[str | None] = mapped_column(String(128), unique=True, index=True)

    display_name: Mapped[str] = mapped_column(String(80), nullable=False)

    # Optional and unique: emails are optional in Phase 2 (no auth yet),
    # but if present they must not collide between accounts.
    email: Mapped[str | None] = mapped_column(String(254), unique=True)

    # Relationships ("one user has many X"). Deleting a user who still
    # has safety records is deliberately BLOCKED at the database level
    # (ON DELETE RESTRICT on each child table) so safety history can
    # never disappear by accident.
    trusted_contacts: Mapped[list[TrustedContact]] = relationship(back_populates="owner")
    check_ins: Mapped[list[CheckIn]] = relationship(back_populates="user")
    sos_events: Mapped[list[SosEvent]] = relationship(back_populates="user")
    community_reports: Mapped[list[CommunityReport]] = relationship(back_populates="user")
