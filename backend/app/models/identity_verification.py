"""One submitted identity-verification request (Phase 6, second assignment).

Plain language: when an account wants social access, it submits a
verification REQUEST. A human reviewer (the platform owner) later approves
or rejects it. Every submission is one row here, so the full history
survives: what was submitted, when, who reviewed it, when, and the note
they left.

DELIBERATELY STORES NO IDENTITY DOCUMENTS: no Aadhaar numbers, no ID
images, no scans, nothing sensitive. This phase implements a clearly
labelled DEVELOPMENT/MANUAL-REVIEW workflow - a real identity provider is
still required before this can be called identity verification, and the
review note field is plain text the reviewer chooses to write.

The account-level state (`users.verification_status`) is updated in the
same transaction as the review decision; this table is the history.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import VerificationRequestStatus

if TYPE_CHECKING:
    from app.models.user import User


class IdentityVerification(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One verification submission and its review outcome."""

    __tablename__ = "identity_verifications"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected')",
            name="status_valid",
        ),
    )

    # The account that submitted the request. ON DELETE RESTRICT, like
    # every safety table: verification history can never vanish by
    # accident. Indexed - reviewers list by user, audits look up a user.
    user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )

    # pending -> approved | rejected (reviewer-only transitions; a
    # rejected user may submit a NEW request row, this one stays as
    # history). Mirrors VerificationRequestStatus via a DB CHECK.
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=VerificationRequestStatus.PENDING
    )

    # Server clock when the reviewer decided. NULL while pending.
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Who made the decision (the owner account). RESTRICT, not SET NULL:
    # the audit trail must keep the reviewer's identity.
    reviewed_by: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT")
    )

    # Optional plain-text note the reviewer leaves for the applicant
    # (e.g. why it was rejected). NEVER document contents - free text only.
    review_note: Mapped[str | None] = mapped_column(Text)

    # Optional plain-text note the APPLICANT wrote when submitting, for
    # the reviewer's context (there is no document to inspect in this
    # manual workflow). Kept separate from `review_note` on purpose: one
    # message goes applicant -> reviewer, the other reviewer -> applicant,
    # and mixing them would corrupt both directions.
    applicant_note: Mapped[str | None] = mapped_column(Text)

    # The applicant (first FK). The reviewer (second FK) is deliberately
    # NOT part of this relationship - see User.verification_requests.
    user: Mapped[User] = relationship(
        back_populates="verification_requests", foreign_keys=[user_id]
    )
