"""Safety-preference and consent records (Phase 15).

Plain language: one row = what ONE user chose for ONE activity at ONE
moment. Each optional feature has its OWN column (trip details,
check-in reminders, SOS notify attempts, location sharing) - one broad
checkbox can never silently authorize every form of data collection.
Both `accepted` AND `declined` are recorded rows: declining is an
explicit, timestamped acknowledgement of the risk disclosure with the
features left off (never the absence of a row).

Tamper-resistant by construction: there are NO update/delete endpoints
- withdrawing or changing consent appends a NEW row, and the current
state is always the latest row per (user, subject). History is never
rewritten. Consent never authorizes what does not exist: unavailable
features (location sharing on this build - no GPS pipeline) are
rejected at write time, and expired rows read as withdrawn.

What this NEVER does: guarantee safety, waive liability, collect
microphone/camera, or track anyone continuously. The disclosure text
says so explicitly (versioned; draft pending legal review).
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, String, Uuid, false
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import ConsentDecision

if TYPE_CHECKING:
    from app.models.user import User

# Disclosure text version recorded on every row. Bumped only with owner
# review; the endpoint refuses stale versions so nobody acknowledges an
# old text unknowingly.
SAFETY_DISCLOSURE_VERSION = "2026-10-15.v1"

SAFETY_DISCLOSURE_TEXT = (
    "Roamlary safety acknowledgement (draft for legal review - not a final waiver). "
    "I understand that Roamlary can provide only the safety-support features explicitly "
    "described and enabled for this activity. If I choose not to enable optional features, "
    "certain protections and notifications may be unavailable. Meeting or travelling with "
    "other users involves risks, and I should take appropriate precautions "
    "(meet in public, tell a trusted person independently, arrange my own transport). "
    "I understand that Roamlary does not guarantee my personal safety, another "
    "participant's conduct, uninterrupted connectivity, or successful delivery of "
    "emergency notifications. I have reviewed the available safety options and understand "
    "which features I have chosen to enable or decline. My consent does not waive any "
    "legal rights, and nothing here limits Roamlary's responsibility for its own platform."
)

# Features the platform can actually offer (brief 15.A: only what is
# implemented). Location sharing is NOT offered: no GPS pipeline exists
# on this build, so consenting to it is refused rather than recorded.
AVAILABLE_FEATURES = frozenset({"share_trip_details", "checkin_reminders", "sos_notify"})


class SafetyConsent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One consent/acknowledgement decision for one user and one activity."""

    __tablename__ = "safety_consents"
    __table_args__ = (
        CheckConstraint(
            "decision IN ('accepted', 'declined')",
            name="decision_valid",
        ),
        Index(
            "ix_safety_consents_subject",
            "user_id",
            "subject_type",
            "subject_id",
            "created_at",
        ),
    )

    user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )

    # 'meetup' (covers house parties - same table) or 'trip_share'.
    subject_type: Mapped[str] = mapped_column(String(20), nullable=False)
    subject_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)

    # One column per optional feature (independent states by design).
    share_trip_details: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    checkin_reminders: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    sos_notify: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )

    decision: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ConsentDecision.DECLINED, server_default="declined"
    )
    disclosure_version: Mapped[str] = mapped_column(String(20), nullable=False)

    # Consent window (optional). Expired rows read as withdrawn.
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(foreign_keys=[user_id])
