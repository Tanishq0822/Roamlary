"""Server-side login session table (Phase 8, minimal revocation support).

Plain language: one row = one login that is still meaningful. Stateless
JWTs cannot be "taken back" by themselves, so each login mints a session
row and the token carries its id (`sid` claim). Every request re-checks
that row: a revoked (or missing) session row makes the token stop working
IMMEDIATELY - not at expiry. That is the whole revocation guarantee, and
it is enforced on every authenticated request in get_current_user.

What this table is NOT: no device fingerprinting, no IP tracking, no
user-agent collection. An optional free-form `label` (e.g. "my phone")
lets the user tell their own sessions apart; nothing is collected
automatically.

Logout = stamp `revoked_at` on the current row. "Revoke others" stamps
every row except the current one. "Revoke all" stamps everything AND
bumps users.token_version, which additionally kills pre-Phase-8 legacy
tokens that carry no `sid` (they are governed by the version check).
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.user import User


class AuthSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One login session belonging to one user."""

    __tablename__ = "auth_sessions"
    __table_args__ = (
        Index(
            "ix_auth_sessions_user_revoked",
            "user_id",
            "revoked_at",
        ),
    )

    user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )

    # Optional user-supplied label ("my phone"). Never collected
    # automatically; purely a display aid for the session list.
    label: Mapped[str | None] = mapped_column(String(80))

    # Server clock of revocation. NULL = active.
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(back_populates="auth_sessions")
