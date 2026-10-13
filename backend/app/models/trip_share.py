"""Trip-sharing session table (Phase 12).

Plain language: one row = "these people may see this trip until this
time". Sharing reuses what exists: the shared object is a travel plan
(optional - a plan-less "I'm travelling" share is allowed), and the
viewers are the owner's ACCEPTED travel-partner counterparts (the only
pre-verified social relationship - no new identity system, no live
location infrastructure).

What is shared: the plan's destination/dates/visibility plus the owner's
check-in states (reused read shapes, viewer-scoped). What is NOT
shared: live GPS (no such infrastructure exists - honestly no location
beyond what the plan and check-ins already state), private messages, SOS
records, or anything of anyone else.

Expiry and revocation are enforced on the SERVER at read time
(expires_at passed, or revoked_at set → the share reads as gone) - the
UI cannot override them. Expiry is capped at 90 days.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.travel_plan import TravelPlan
    from app.models.user import User


class TripShare(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One trip-sharing grant from an owner to their accepted partners."""

    __tablename__ = "trip_shares"

    owner_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    # The shared trip context (optional). RESTRICT: a share keeps
    # pointing at a real plan; delete the share first.
    plan_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("travel_plans.id", ondelete="RESTRICT")
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # Server clock of owner revocation. NULL = still shared (until expiry).
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    owner: Mapped[User] = relationship(foreign_keys=[owner_id])
    plan: Mapped[TravelPlan | None] = relationship()
