"""Shared SQLAlchemy declarative base and column conventions.

Plain language: this module is the common foundation every table model
inherits from, so all tables get the same primary-key, timestamp and
constraint-naming behaviour without repeating code in each model file.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, MetaData, Uuid, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Consistent database constraint names, e.g. "ck_check_ins_status_valid".
# Without a convention, database-generated names can differ between
# PostgreSQL and SQLite and make migrations unstable.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


def utc_now() -> datetime:
    """Timezone-aware UTC timestamp used for column defaults."""
    return datetime.now(UTC)


class Base(DeclarativeBase):
    """Declarative base carrying the shared naming convention."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class UUIDPrimaryKeyMixin:
    """Adds a UUID primary key column named `id`.

    UUIDs (random 128-bit identifiers) are used instead of counting
    numbers (1, 2, 3...) so identifiers never leak how many records
    exist and can be generated before anything is saved.
    """

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)


class TimestampMixin:
    """Adds UTC `created_at` and `updated_at` columns.

    `created_at` is set when a row is inserted; `updated_at` is set on
    insert and refreshed automatically whenever the row is updated.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        server_default=func.now(),
        onupdate=utc_now,
        nullable=False,
    )
