"""Add travel profiles, travel plans and travel-partner requests (Phase 7).

Revision ID: 426dcef31e27
Revises: 3e285edb0896
Create Date: 2026-10-13

Three brand-new tables; nothing existing is touched and there is nothing
to backfill, so the upgrade is unguarded (same policy as every prior
fresh-table migration). The DDL mirrors the SQLAlchemy models
EXACTLY (column types, server defaults, named CHECK constraints, named
indexes - including the two partial UNIQUE indexes that allow at most
one PENDING travel-partner request per user pair in either direction).

The downgrade is DATA-GUARDED: it refuses while any travel row exists,
so a stray downgrade can never destroy travel profiles, plans, or
partner-request history - that data-handling decision belongs to an
operator, deliberately (same guard policy as the Phase 4 and 6b
migrations).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "426dcef31e27"
down_revision: str | None = "3e285edb0896"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Single window in which a pair may hold an open request.
_PENDING_PREDICATE = sa.text("status = 'pending'")


def upgrade() -> None:
    """Create the Phase 7 tables (fresh structures, no data to migrate)."""
    op.create_table(
        "travel_profiles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("travel_nickname", sa.String(length=40), nullable=True),
        sa.Column("bio", sa.String(length=200), nullable=True),
        sa.Column("home_region", sa.String(length=80), nullable=True),
        sa.Column("languages", sa.JSON(), nullable=True),
        sa.Column("interests", sa.JSON(), nullable=True),
        sa.Column("travel_styles", sa.JSON(), nullable=True),
        sa.Column("group_size_pref", sa.SmallInteger(), nullable=True),
        sa.Column("discoverable", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "group_size_pref IS NULL OR group_size_pref BETWEEN 2 AND 12",
            name=op.f("ck_travel_profiles_group_size_pref_range"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_travel_profiles_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_travel_profiles")),
    )
    # unique=True: exactly one profile per account (the model declares
    # unique=True + index=True, which SQLAlchemy renders as a UNIQUE
    # INDEX - mirrored here so ORM- and Alembic-built schemas match).
    op.create_index(
        op.f("ix_travel_profiles_user_id"),
        "travel_profiles",
        ["user_id"],
        unique=True,
    )

    op.create_table(
        "travel_plans",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("destination", sa.String(length=80), nullable=False),
        sa.Column("destination_normalized", sa.String(length=80), nullable=False),
        sa.Column("region", sa.String(length=80), nullable=True),
        sa.Column("region_normalized", sa.String(length=80), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("flexible_dates", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="active", nullable=False),
        sa.Column("visibility", sa.String(length=20), server_default="private", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("end_date >= start_date", name=op.f("ck_travel_plans_end_date_after_start")),
        sa.CheckConstraint(
            "status IN ('active', 'paused', 'completed')",
            name=op.f("ck_travel_plans_status_valid"),
        ),
        sa.CheckConstraint(
            "visibility IN ('private', 'discoverable')",
            name=op.f("ck_travel_plans_visibility_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_travel_plans_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_travel_plans")),
    )
    op.create_index(op.f("ix_travel_plans_user_id"), "travel_plans", ["user_id"], unique=False)
    op.create_index(
        "ix_travel_plans_discovery",
        "travel_plans",
        ["destination_normalized", "status", "visibility"],
        unique=False,
    )
    op.create_index(
        "ix_travel_plans_dates",
        "travel_plans",
        ["start_date", "end_date"],
        unique=False,
    )

    op.create_table(
        "travel_partner_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("requester_id", sa.Uuid(), nullable=False),
        sa.Column("recipient_id", sa.Uuid(), nullable=False),
        sa.Column("plan_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "requester_id <> recipient_id",
            name=op.f("ck_travel_partner_requests_no_self_request"),
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'accepted', 'rejected', 'cancelled')",
            name=op.f("ck_travel_partner_requests_status_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["plan_id"],
            ["travel_plans.id"],
            name=op.f("fk_travel_partner_requests_plan_id_travel_plans"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["recipient_id"],
            ["users.id"],
            name=op.f("fk_travel_partner_requests_recipient_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["requester_id"],
            ["users.id"],
            name=op.f("fk_travel_partner_requests_requester_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_travel_partner_requests")),
    )
    op.create_index(
        op.f("ix_travel_partner_requests_requester_id"),
        "travel_partner_requests",
        ["requester_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_travel_partner_requests_recipient_id"),
        "travel_partner_requests",
        ["recipient_id"],
        unique=False,
    )
    # At most one PENDING request per DIRECTION of a pair: each index
    # locks its own ordered pair, so racing identical sends lose at the
    # database. The cross-direction duplicate (A->B and B->A both
    # pending) has different keys in both indexes and is blocked by the
    # endpoint's either-direction pre-check (documented in report.md).
    op.create_index(
        "uq_travel_partner_requests_pending_pair_ab",
        "travel_partner_requests",
        ["requester_id", "recipient_id"],
        unique=True,
        postgresql_where=_PENDING_PREDICATE,
        sqlite_where=_PENDING_PREDICATE,
    )
    op.create_index(
        "uq_travel_partner_requests_pending_pair_ba",
        "travel_partner_requests",
        ["recipient_id", "requester_id"],
        unique=True,
        postgresql_where=_PENDING_PREDICATE,
        sqlite_where=_PENDING_PREDICATE,
    )
    op.create_index(
        "ix_travel_partner_requests_recipient_status",
        "travel_partner_requests",
        ["recipient_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_travel_partner_requests_requester_status",
        "travel_partner_requests",
        ["requester_id", "status"],
        unique=False,
    )


def downgrade() -> None:
    """Drop the Phase 7 tables - DATA-GUARDED.

    Refuses while any travel data exists so Phase 7 history can never be
    destroyed by a stray downgrade: the operator must export or delete
    the rows first - a deliberate data-handling decision.
    """
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    counts: dict[str, int] = {}
    for table in ("travel_partner_requests", "travel_plans", "travel_profiles"):
        if inspector.has_table(table):
            counts[table] = (
                bind.execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar() or 0
            )
    total = sum(counts.values())
    if total:
        parts = ", ".join(f"{name}={count}" for name, count in counts.items() if count)
        raise RuntimeError(
            f"Refusing to downgrade: {total} travel row(s) exist ({parts}). "
            "Export or delete this data first - dropping these tables "
            "destroys travel profiles, plans and partner-request history, "
            "and that data-handling decision must be made deliberately."
        )

    op.drop_table("travel_partner_requests")
    op.drop_table("travel_plans")
    op.drop_table("travel_profiles")
