"""Pay-per-post payment table (Phase 14: free first post, then ₹10/post).

Plain language: one row = one charge decision for one publishing
attempt. The FIRST qualifying post per account is free (consumed
atomically from `users.free_posts_used`); every later one costs
₹10 = 1000 paise (server-set from the live billing policy - amounts
never arrive from clients). A post is published ONLY against a FREE
grant or a SUCCEEDED payment, and each succeeded payment is consumed
EXACTLY once (compare-and-set on `consumed_at`), so refreshes,
double-clicks, retries, and duplicate webhooks cannot duplicate posts
or charges.

No real provider is configured (the default): paid publishing stays
explicitly pending/unavailable - never faked. A mock provider exists
for tests (deterministic, no network). Currency is always INR;
amounts are integer paise internally.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import PaymentStatus

if TYPE_CHECKING:
    from app.models.user import User

# Eligible post categories (closed set - validated in the service, so a
# typo'd category fails loudly instead of entering the database).
# Ordinary chat messages, edits, accepts/rejects, and retries are NOT
# categories: they never create charges.
POST_CATEGORIES = frozenset(
    {
        "travel_partner",  # POST /travel-buddies/requests
        "chat_request",  # POST /chat/requests
        "meetup",  # POST /meetups
        "house_party",  # POST /parties
    }
)


class PostPayment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One pay-per-post charge record."""

    __tablename__ = "post_payments"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'succeeded', 'failed', 'cancelled', 'refunded')",
            name="status_valid",
        ),
        CheckConstraint("amount_paise >= 0", name="amount_non_negative"),
    )

    user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )

    # Which eligible category this payment belongs to.
    category: Mapped[str] = mapped_column(String(40), nullable=False, index=True)

    # The published subject, filled when consumed (post id + table
    # name). NULL until a post is actually published against this row.
    subject_type: Mapped[str | None] = mapped_column(String(40))
    subject_id: Mapped[UUID | None] = mapped_column(Uuid)

    # Integer paise, server-set from the billing policy at creation.
    amount_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(
        String(10), nullable=False, default="INR", server_default="INR"
    )

    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=PaymentStatus.PENDING, server_default="pending"
    )

    # 'none' for free-grant rows, otherwise the verifying provider name.
    provider: Mapped[str] = mapped_column(
        String(20), nullable=False, default="none", server_default="none"
    )
    # Provider-side reference (UNIQUE; NULLs exempt on both backends).
    # Webhook duplicates land on the SAME row via this key.
    provider_reference: Mapped[str | None] = mapped_column(String(120), unique=True)
    # Client-supplied idempotency key (UNIQUE): refresh/double-click/
    # retry with the same key returns the SAME row, never a new charge.
    idempotency_key: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)

    # Server clock of the single consumption (post published). NULL =
    # unconsumed. Set exactly once via compare-and-set.
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    last_error: Mapped[str | None] = mapped_column(Text)

    user: Mapped[User] = relationship(foreign_keys=[user_id])
