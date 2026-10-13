"""Notification record table (Phase 12, honest delivery tracking).

Plain language: one row = one thing the system tried (or will try) to
tell one user about. The vocabulary is deliberately honest:

- `delivered` + channel `in_app` = the row is visible via
  GET /notifications (the ONLY channel that exists). Nothing else may
  ever be called delivered.
- `unavailable` = an external channel (SMS/email/push) was requested
  but no provider is configured - the failure is recorded, never
  hidden, never claimed as sent.
- `unknown` = handed to a provider with no delivery receipt.
- `queued`/`attempted`/`failed` = retry lifecycle states.

Idempotency: `idempotency_key` is UNIQUE per event (e.g.
"sos:{sos_id}:contact:{contact_id}"), so retries and repeated checks
can NEVER create duplicate alerts - a retry re-attempts the SAME row
(attempts + 1, never a second row). Bodies carry event facts only, never
credentials or sensitive message content.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import NotificationStatus

if TYPE_CHECKING:
    from app.models.user import User


class Notification(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One notification attempt for one user."""

    __tablename__ = "notifications"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'attempted', 'delivered', 'failed', 'unavailable', 'unknown')",
            name="status_valid",
        ),
    )

    user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    # Machine-friendly event kind (sos_created, meetup_invite,
    # join_decision, event_cancelled, trip_shared, checkin_due,
    # sos_update). Validated at the service layer.
    kind: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    # Delivery channel attempted: 'in_app' is the only real one;
    # 'sms'/'email'/'push' record honest `unavailable`.
    channel: Mapped[str] = mapped_column(
        String(20), nullable=False, default="in_app", server_default="in_app"
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=NotificationStatus.QUEUED, server_default="queued"
    )
    # Provider-side receipt id, when a provider gives one. NULL otherwise.
    external_id: Mapped[str | None] = mapped_column(String(120))
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    last_error: Mapped[str | None] = mapped_column(Text)
    # One row per event: retries update, never duplicate.
    idempotency_key: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(foreign_keys=[user_id])
