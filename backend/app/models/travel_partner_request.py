"""Travel-partner request table (Phase 7).

Plain language: one row = "A wants to travel with B" - optionally about
B's published plan X (the context they saw in discovery). Lifecycle:
pending -> accepted | rejected | cancelled, enforced in the endpoint
layer. The database adds three structural guarantees:

1. CHECK `requester_id <> recipient_id` - self-requests cannot exist.
2. partial UNIQUE (requester_id, recipient_id) WHERE status='pending'
3. partial UNIQUE (recipient_id, requester_id) WHERE status='pending'
   -> at most one pending row per DIRECTION of a pair (each index locks
   its own ordered pair, so two racing identical sends lose at the
   database (IntegrityError), not in a read-then-write race). The
   CROSS-direction duplicate (A->B and B->A both pending) has different
   keys in both indexes and is therefore blocked by the endpoint's
   either-direction pre-check - that boundary and its residual
   concurrent window are documented in report.md.

An accepted request is a social connection ONLY: it grants no bypass of
the verification policy, discoverability switches, or any restriction a
later phase adds. `plan_id` points at the RECIPIENT's plan (context) and
is RESTRICT: history keeps pointing at a real plan.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import BuddyRequestStatus

if TYPE_CHECKING:
    from app.models.travel_plan import TravelPlan
    from app.models.user import User

# The single window in which a pair may have an open request.
_PENDING_PREDICATE = "status = 'pending'"


class TravelPartnerRequest(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One travel-partner request between two accounts."""

    __tablename__ = "travel_partner_requests"
    __table_args__ = (
        CheckConstraint(
            "requester_id <> recipient_id",
            name="no_self_request",
        ),
        CheckConstraint(
            "status IN ('pending', 'accepted', 'rejected', 'cancelled')",
            name="status_valid",
        ),
        Index(
            "uq_travel_partner_requests_pending_pair_ab",
            "requester_id",
            "recipient_id",
            unique=True,
            postgresql_where=text(_PENDING_PREDICATE),
            sqlite_where=text(_PENDING_PREDICATE),
        ),
        Index(
            "uq_travel_partner_requests_pending_pair_ba",
            "recipient_id",
            "requester_id",
            unique=True,
            postgresql_where=text(_PENDING_PREDICATE),
            sqlite_where=text(_PENDING_PREDICATE),
        ),
        Index(
            "ix_travel_partner_requests_recipient_status",
            "recipient_id",
            "status",
        ),
        Index(
            "ix_travel_partner_requests_requester_status",
            "requester_id",
            "status",
        ),
    )

    requester_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )

    recipient_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )

    # Optional context: the recipient's plan as seen in discovery. NULL =
    # a plan-agnostic "let's travel together" request.
    plan_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("travel_plans.id", ondelete="RESTRICT")
    )

    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=BuddyRequestStatus.PENDING, server_default="pending"
    )

    # Server clock when the recipient decided (or the request was
    # cancelled). NULL while pending.
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Both parties exist as relationships for eager loading in list
    # responses (display names). No User-side backref is declared: the
    # two user FKs would make the reverse side ambiguous, and every
    # query in this phase selects the request rows directly. `plan` is
    # the optional trip context (the recipient's plan seen in discovery)
    # and is eagerly loaded for the same reason.
    requester: Mapped[User] = relationship(foreign_keys=[requester_id])
    recipient: Mapped[User] = relationship(foreign_keys=[recipient_id])
    plan: Mapped[TravelPlan | None] = relationship()
