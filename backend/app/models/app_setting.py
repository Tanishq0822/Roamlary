"""Runtime application settings stored in the database (Phase 6b).

Plain language: some switches must be changeable WHILE the server runs
(for example: does social access require identity verification?), which
rules out environment variables - those need an edit + restart. One row =
one setting key/value pair.

Fail-closed rule (enforced in `app/core/policy.py`, not here): if a key
is missing or holds an unrecognized value, the EFFECTIVE value is the
secure default (`required` / True). Absence of configuration must never
open access.

Values are short plain strings ('true'/'false' for the policy). Every
write goes through the owner-only policy endpoint, which also records an
audit row in `setting_changes`.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AppSetting(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One stored setting (natural key: `key`, unique + indexed)."""

    __tablename__ = "app_settings"

    # Machine-readable key, e.g. "social_requires_verification".
    key: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)

    # Short plain-text value, e.g. "true". Validated in the application
    # layer (the policy reader fails closed on anything unexpected).
    value: Mapped[str] = mapped_column(String(100), nullable=False)

    # The account that last wrote this row (owner via the policy
    # endpoint). NULL only if a future system path seeds a default.
    updated_by: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT")
    )
