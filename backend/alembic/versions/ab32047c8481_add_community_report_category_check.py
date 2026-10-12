"""add community report category check

Revision ID: ab32047c8481
Revises: 0dd8995649b4
Create Date: 2026-10-12 13:05:11.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'ab32047c8481'
down_revision: Union[str, None] = '0dd8995649b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# The project's MetaData naming convention, copied verbatim into this
# migration so the file is SELF-CONTAINED. Migrations are frozen history:
# they must never import live application code, because that code can
# change later and silently break old migrations. (Same pattern as
# migrations ccd362671e07 and 0dd8995649b4.)
_NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

# The Phase 6 category set (must match ReportCategory in the application
# and the CHECK below; kept literal here so the migration is frozen
# history). The Phase 2 schema allowed ANY string up to 40 chars.
_ALLOWED_CATEGORIES = (
    "'unsafe_area', 'harassment', 'suspicious_activity',"
    " 'road_hazard', 'poor_lighting', 'other'"
)


def upgrade() -> None:
    # DATA-SAFETY GUARD - checked BEFORE any schema change (same proven
    # pattern as migrations ccd362671e07 and 0dd8995649b4, mirrored to
    # the upgrade direction). The Phase 2 schema allowed arbitrary
    # category strings, so rows written by hand or by an old client may
    # carry values outside the new closed set. Creating the CHECK would
    # fail against them (and converting or deleting them to force the
    # migration through would silently destroy user data), so this
    # migration REFUSES instead. The check runs before any DDL, so a
    # refusal leaves both the schema and every record exactly as they
    # are.
    connection = op.get_bind()
    invalid_count = connection.execute(
        sa.text(
            "SELECT count(*) FROM community_reports "
            f"WHERE category NOT IN ({_ALLOWED_CATEGORIES})"
        )
    ).scalar_one()
    if invalid_count:
        raise RuntimeError(
            "Refusing to upgrade migration ab32047c8481: "
            f"{invalid_count} community report(s) carry a category outside "
            f"the Phase 6 closed set ({_ALLOWED_CATEGORIES}). No schema "
            "changes were made and no records were deleted, converted, or "
            "otherwise modified - the database is unchanged and still at "
            "revision 0dd8995649b4. Make an explicit data-handling "
            "decision for these record(s) first (map each one to an "
            "allowed category such as 'other', or delete them), then run "
            "the upgrade again."
        )

    # Phase 6: turn the previously loose category string into a closed
    # set. batch_alter_table is REQUIRED for cross-dialect support
    # (SQLite rebuilds the table, PostgreSQL issues a real ALTER TABLE)
    # and the constraint name is the SHORT logical name 'category_valid' -
    # the naming convention expands it to 'ck_community_reports_category_valid'.
    with op.batch_alter_table(
        "community_reports", naming_convention=_NAMING_CONVENTION
    ) as batch_op:
        batch_op.create_check_constraint(
            "category_valid",
            f"category IN ({_ALLOWED_CATEGORIES})",
        )


def downgrade() -> None:
    # Dropping a CHECK constraint cannot lose or alter data: every stored
    # category value survives exactly as it is, and the constraint simply
    # stops guarding future writes (restoring the loose Phase 2 rules).
    # This direction is therefore ALWAYS safe - there is no data-dependent
    # refusal to add here.
    with op.batch_alter_table(
        "community_reports", naming_convention=_NAMING_CONVENTION
    ) as batch_op:
        batch_op.drop_constraint("category_valid", type_="check")
