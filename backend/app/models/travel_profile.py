"""Travel profile table (Phase 7).

Plain language: one row = the traveller-facing identity a user chooses to
publish for travel-buddy discovery - a nickname, a short bio, a broad home
region, languages, interests, travel styles, and an optional group-size
preference. It is STRICTLY separate from the account (`users`): discovery
responses are built from THIS table plus a public display name, so email,
phone, password hash, role, and verification state can never leak through
it.

Privacy defaults: `discoverable` is FALSE - a profile exists but stays
hidden until its owner opts in. Profile COMPLETION is computed by the API
from the filled fields; it is never stored, and it never implies identity
verification (those are separate states by design).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    ForeignKey,
    SmallInteger,
    String,
    Uuid,
    false,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.user import User


class TravelProfile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """The travel-oriented social profile of one account."""

    __tablename__ = "travel_profiles"
    __table_args__ = (
        CheckConstraint(
            "group_size_pref IS NULL OR group_size_pref BETWEEN 2 AND 12",
            name="group_size_pref_range",
        ),
    )

    # One profile per account (UNIQUE + indexed). RESTRICT like every
    # other child table: profile history never vanishes by accident.
    user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT"), unique=True, index=True
    )

    # Optional travel nickname. The public display name falls back to the
    # account's `display_name` when this is NULL (never the email).
    travel_nickname: Mapped[str | None] = mapped_column(String(40))

    # Short self-description; plain text, bounded length.
    bio: Mapped[str | None] = mapped_column(String(200))

    # Broad region/city the traveller calls home - voluntarily supplied,
    # deliberately BROAD (never a precise address; no GPS here).
    home_region: Mapped[str | None] = mapped_column(String(80))

    # String lists (languages / interests / travel styles), stored as JSON
    # arrays of short strings. Membership is validated in the application
    # layer (travel styles against a closed set); JSON contents cannot be
    # CHECK-constrained portably across PostgreSQL and SQLite - see the
    # documented limitation in report.md. NULL means "not specified" and
    # simply contributes no matching signal.
    languages: Mapped[list | None] = mapped_column(JSON)
    interests: Mapped[list | None] = mapped_column(JSON)
    travel_styles: Mapped[list | None] = mapped_column(JSON)

    # Optional preferred companion group size (2-12); NULL = no preference.
    group_size_pref: Mapped[int | None] = mapped_column(SmallInteger)

    # Discoverability switch - SECURE DEFAULT: hidden. A profile enters
    # discovery only when this is TRUE, alongside the live verification
    # policy and an eligible plan (all enforced in the query layer).
    discoverable: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )

    user: Mapped[User] = relationship(back_populates="travel_profile")
