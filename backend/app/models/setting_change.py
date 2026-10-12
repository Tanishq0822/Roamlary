"""Audit trail for setting changes (Phase 6b).

Plain language: every time the platform owner changes a policy, one row
is appended here recording WHAT changed, the OLD value, the NEW value,
WHO changed it, and WHEN. The row is append-only by design - nothing in
the API updates or deletes `setting_changes`, so the history of who
flipped which switch always stays intact.

`old_value` is NULL only for the very first write of a key (there was no
previous value to record).
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base, TimestampMixin, UUIDPrimaryKeyMixin


class SettingChange(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One audited setting change (append-only)."""

    __tablename__ = "setting_changes"

    # Which setting changed, e.g. "social_requires_verification".
    setting_key: Mapped[str] = mapped_column(String(64), index=True, nullable=False)

    # Values before/after this change; NULL old_value = first write ever.
    old_value: Mapped[str | None] = mapped_column(String(100))
    new_value: Mapped[str] = mapped_column(String(100), nullable=False)

    # The owner account that made the change (RESTRICT: audit rows are
    # never orphaned or silently dropped).
    changed_by: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
