"""User profile table.

Plain language: one row = one Roamlary account. Local accounts store only a
securely hashed password (never the plaintext). `firebase_uid` is an optional
external reference: when Firebase Authentication is integrated in a later
phase, this column stores the identifier Firebase gives the user. A
Firebase-only account may have a NULL password_hash because it never uses a
local password.

Phase 6 (second assignment) adds two authorization columns:

- `verification_status` - the account's identity-verification state
  (default `unverified`; moved only by the submit/review workflow).
- `role` - authorization role (default `user`; `owner` can only be granted
  by the server-side CLI, never by any API request).

Both are guarded by database CHECK constraints that mirror the Python
enums, following the project's two-layer validation convention.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import UserRole, VerificationStatus

if TYPE_CHECKING:
    from app.models.auth_session import AuthSession
    from app.models.check_in import CheckIn
    from app.models.community_report import CommunityReport
    from app.models.identity_verification import IdentityVerification
    from app.models.sos_event import SosEvent
    from app.models.travel_plan import TravelPlan
    from app.models.travel_profile import TravelProfile
    from app.models.trusted_contact import TrustedContact


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """The application user's profile."""

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "verification_status IN ('unverified', 'pending', 'verified', 'rejected')",
            name="verification_status_valid",
        ),
        CheckConstraint("role IN ('user', 'owner')", name="role_valid"),
    )

    # Optional link to an external auth provider (Firebase in a later
    # phase). Unique + indexed because login looks users up by this value.
    firebase_uid: Mapped[str | None] = mapped_column(String(128), unique=True, index=True)

    display_name: Mapped[str] = mapped_column(String(80), nullable=False)

    # Local email/password accounts always have an email, but the column
    # stays nullable so a future Firebase-only account can exist without one.
    # Unique: one account per email. Values are normalized (trimmed +
    # lowercased) in the application layer before saving.
    email: Mapped[str | None] = mapped_column(String(254), unique=True)

    # Argon2id hash of the password for LOCAL accounts only. Nullable so a
    # future Firebase-only account (no local password) can still be a row.
    # NEVER returned by any API response - it is excluded from every schema.
    password_hash: Mapped[str | None] = mapped_column(String(255))

    # Identity-verification state of the ACCOUNT (Phase 6b). NOT NULL with
    # a database default, so every pre-existing account becomes
    # `unverified` the moment this column exists - the secure starting
    # point. Moved only server-side by the submit/review workflow; no
    # request schema ever accepts it (422 if a client tries to send it).
    # The server default matches migration 3e285edb0896 exactly, so the
    # ORM-created and Alembic-created schemas are identical and even raw
    # SQL inserts cannot create a NULL-state account.
    verification_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=VerificationStatus.UNVERIFIED,
        server_default="unverified",
    )

    # Authorization role (Phase 6b). NOT NULL default `user`: registration,
    # email, and signup order never grant `owner`. The server-side CLI is
    # the only supported grant path; no API endpoint writes this column.
    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=UserRole.USER,
        server_default="user",
    )

    # Session-revocation version (Phase 8). Every access token carries
    # this number as its `tv` claim; "revoke all sessions" bumps it, and
    # any token with an older number stops working immediately. Starts at
    # 0 (the migration backfills existing accounts to 0, matching the
    # `tv` that pre-Phase-8 legacy tokens implicitly carry).
    token_version: Mapped[int] = mapped_column(nullable=False, default=0, server_default="0")

    # Relationships ("one user has many X"). Deleting a user who still
    # has safety records is deliberately BLOCKED at the database level
    # (ON DELETE RESTRICT on each child table) so safety history can
    # never disappear by accident.
    trusted_contacts: Mapped[list[TrustedContact]] = relationship(back_populates="owner")
    check_ins: Mapped[list[CheckIn]] = relationship(back_populates="user")
    sos_events: Mapped[list[SosEvent]] = relationship(back_populates="user")
    community_reports: Mapped[list[CommunityReport]] = relationship(back_populates="user")
    verification_requests: Mapped[list[IdentityVerification]] = relationship(
        back_populates="user", foreign_keys="IdentityVerification.user_id"
    )
    # Travel surface (Phase 7). One optional profile (1:1) and many plans.
    # Travel-partner REQUESTS deliberately have no backref here: their two
    # user FKs (requester/recipient) would make the reverse side
    # ambiguous, and every query selects the request rows directly.
    travel_profile: Mapped[TravelProfile | None] = relationship(
        back_populates="user", uselist=False
    )
    travel_plans: Mapped[list[TravelPlan]] = relationship(back_populates="user")
    # Login sessions (Phase 8). One row per login; revoking a row kills
    # the token that points at it. No backrefs from blocks/conversations/
    # messages/travel requests: their user FKs are ambiguous pairs and
    # every query selects those rows directly.
    auth_sessions: Mapped[list[AuthSession]] = relationship(back_populates="user")
