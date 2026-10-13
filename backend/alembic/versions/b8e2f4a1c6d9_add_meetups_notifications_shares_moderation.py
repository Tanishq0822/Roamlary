"""Add meetups, invitations, notifications, trip shares + report/SOS review columns (Phases 9-12).

Revision ID: b8e2f4a1c6d9
Revises: 7f3a9c1e5b42
Create Date: 2026-10-14

New tables (all additive, nothing existing is touched):
- `meetups` (shared meetup + house-party foundation),
- `meetup_memberships` (UNIQUE per meetup/user),
- `event_invitations` (UNIQUE per meetup/invitee),
- `meetup_announcements` (host-only posts),
- `notifications` (UNIQUE idempotency_key),
- `trip_shares` (owner + optional plan + expiry/revocation).

Column additions:
- `community_reports.reviewed_by` / `reviewed_at` (moderation audit),
- `community_reports.status` CHECK widened with `resolved` (additive:
  no existing row can violate a WIDER set, so the upgrade needs no data
  guard - same direction as the Phase 4/5 relaxations, applied with the
  established batch_alter_table pattern for SQLite support),
- `sos_events.acknowledged_at` (nullable acknowledgement stamp).

The DDL mirrors the SQLAlchemy models EXACTLY.

The downgrade is DATA-GUARDED: it refuses while any row exists in the
six new tables or any report carries status `resolved` (the older CHECK
would reject it) - that data-handling decision belongs to an operator,
deliberately (same guard policy as the Phase 4, 6b, 7 and 8
migrations).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b8e2f4a1c6d9"
down_revision: str | None = "7f3a9c1e5b42"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_MEETUP_CATEGORIES = (
    "'hiking', 'food', 'culture', 'adventure', 'leisure', 'nightlife', 'other'"
)


def upgrade() -> None:
    """Create the Phase 9-12 tables and review columns (additive)."""
    op.create_table(
        "meetups",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("host_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=20), server_default="meetup", nullable=False),
        sa.Column("title", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(length=40), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("timezone", sa.String(length=60), nullable=True),
        sa.Column("capacity", sa.SmallInteger(), server_default="20", nullable=False),
        sa.Column("visibility", sa.String(length=20), server_default="public", nullable=False),
        sa.Column("participation", sa.String(length=20), server_default="approval", nullable=False),
        sa.Column("status", sa.String(length=20), server_default="active", nullable=False),
        sa.Column("location_text", sa.String(length=200), nullable=True),
        sa.Column("venue_details", sa.Text(), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("kind IN ('meetup', 'house_party')", name=op.f("ck_meetups_kind_valid")),
        sa.CheckConstraint(
            "status IN ('active', 'cancelled', 'completed')",
            name=op.f("ck_meetups_status_valid"),
        ),
        sa.CheckConstraint(
            "visibility IN ('public', 'private')", name=op.f("ck_meetups_visibility_valid")
        ),
        sa.CheckConstraint(
            "participation IN ('open', 'approval')",
            name=op.f("ck_meetups_participation_valid"),
        ),
        sa.CheckConstraint("end_at > start_at", name=op.f("ck_meetups_end_after_start")),
        sa.CheckConstraint(
            f"category IN ({_MEETUP_CATEGORIES})", name=op.f("ck_meetups_category_valid")
        ),
        sa.CheckConstraint(
            "capacity IS NULL OR (capacity >= 2 AND capacity <= 500)",
            name=op.f("ck_meetups_capacity_range"),
        ),
        sa.ForeignKeyConstraint(["host_id"], ["users.id"], name=op.f("fk_meetups_host_id_users"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_meetups")),
    )
    op.create_index(op.f("ix_meetups_discovery"), "meetups", ["kind", "status", "visibility", "start_at"], unique=False)
    op.create_index(op.f("ix_meetups_host_id"), "meetups", ["host_id"], unique=False)

    op.create_table(
        "meetup_memberships",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("meetup_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="requested", nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "status IN ('requested', 'approved', 'declined', 'removed', 'left')",
            name=op.f("ck_meetup_memberships_status_valid"),
        ),
        sa.ForeignKeyConstraint(["decided_by"], ["users.id"], name=op.f("fk_meetup_memberships_decided_by_users"), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["meetup_id"], ["meetups.id"], name=op.f("fk_meetup_memberships_meetup_id_meetups"), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_meetup_memberships_user_id_users"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_meetup_memberships")),
        sa.UniqueConstraint("meetup_id", "user_id", name=op.f("uq_meetup_memberships_pair")),
    )
    op.create_index(op.f("ix_meetup_memberships_meetup_id"), "meetup_memberships", ["meetup_id"], unique=False)
    op.create_index(op.f("ix_meetup_memberships_user_id"), "meetup_memberships", ["user_id"], unique=False)

    op.create_table(
        "event_invitations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("meetup_id", sa.Uuid(), nullable=False),
        sa.Column("inviter_id", sa.Uuid(), nullable=False),
        sa.Column("invitee_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending', 'accepted', 'declined', 'revoked', 'expired')",
            name=op.f("ck_event_invitations_status_valid"),
        ),
        sa.ForeignKeyConstraint(["invitee_id"], ["users.id"], name=op.f("fk_event_invitations_invitee_id_users"), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["inviter_id"], ["users.id"], name=op.f("fk_event_invitations_inviter_id_users"), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["meetup_id"], ["meetups.id"], name=op.f("fk_event_invitations_meetup_id_meetups"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_event_invitations")),
        sa.UniqueConstraint("meetup_id", "invitee_id", name=op.f("uq_event_invitations_pair")),
    )
    op.create_index(op.f("ix_event_invitations_invitee_id"), "event_invitations", ["invitee_id"], unique=False)
    op.create_index(op.f("ix_event_invitations_meetup_id"), "event_invitations", ["meetup_id"], unique=False)

    op.create_table(
        "meetup_announcements",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("meetup_id", sa.Uuid(), nullable=False),
        sa.Column("author_id", sa.Uuid(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"], name=op.f("fk_meetup_announcements_author_id_users"), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["meetup_id"], ["meetups.id"], name=op.f("fk_meetup_announcements_meetup_id_meetups"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_meetup_announcements")),
    )
    op.create_index(op.f("ix_meetup_announcements_meetup_id"), "meetup_announcements", ["meetup_id"], unique=False)

    op.create_table(
        "notifications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("channel", sa.String(length=20), server_default="in_app", nullable=False),
        sa.Column("status", sa.String(length=20), server_default="queued", nullable=False),
        sa.Column("external_id", sa.String(length=120), nullable=True),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=100), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "status IN ('queued', 'attempted', 'delivered', 'failed', 'unavailable', 'unknown')",
            name=op.f("ck_notifications_status_valid"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_notifications_user_id_users"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notifications")),
        sa.UniqueConstraint("idempotency_key", name=op.f("uq_notifications_idempotency_key")),
    )
    op.create_index(op.f("ix_notifications_kind"), "notifications", ["kind"], unique=False)
    op.create_index(op.f("ix_notifications_user_id"), "notifications", ["user_id"], unique=False)

    op.create_table(
        "trip_shares",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("plan_id", sa.Uuid(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], name=op.f("fk_trip_shares_owner_id_users"), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["plan_id"], ["travel_plans.id"], name=op.f("fk_trip_shares_plan_id_travel_plans"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_trip_shares")),
    )
    op.create_index(op.f("ix_trip_shares_owner_id"), "trip_shares", ["owner_id"], unique=False)

    # Moderation audit columns on reports + widened status CHECK. ALL
    # inside batch mode: SQLite supports neither bare ADD CONSTRAINT nor
    # ALTER of constraints outside a copy-and-move batch (the
    # established Phase 4 pattern); PostgreSQL issues real ALTERs.
    with op.batch_alter_table("community_reports", recreate="always") as batch_op:
        batch_op.add_column(sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("reviewed_by", sa.Uuid(), nullable=True))
        batch_op.create_foreign_key(
            op.f("fk_community_reports_reviewed_by_users"),
            "users",
            ["reviewed_by"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch_op.drop_constraint("status_valid", type_="check")
        batch_op.create_check_constraint(
            "status_valid",
            "status IN ('pending', 'approved', 'rejected', 'resolved')",
        )

    # Acknowledgement stamp on SOS incidents.
    op.add_column("sos_events", sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    """Drop the Phases 9-12 structures - DATA-GUARDED.

    Refuses while any row exists in the six new tables or any report
    carries status `resolved` (the older CHECK would reject it): the
    operator must export or delete those rows first - a deliberate
    data-handling decision.
    """
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    counts: dict[str, int] = {}
    for table in (
        "meetups",
        "meetup_memberships",
        "event_invitations",
        "meetup_announcements",
        "notifications",
        "trip_shares",
    ):
        if inspector.has_table(table):
            counts[table] = bind.execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar() or 0
    if inspector.has_table("community_reports"):
        counts["community_reports:resolved"] = (
            bind.execute(sa.text("SELECT COUNT(*) FROM community_reports WHERE status = 'resolved'")).scalar() or 0
        )
    total = sum(counts.values())
    if total:
        parts = ", ".join(f"{name}={count}" for name, count in counts.items() if count)
        raise RuntimeError(
            f"Refusing to downgrade: {total} Phases 9-12 row(s) exist ({parts}). "
            "Export or delete this data first - dropping these tables "
            "destroys events, invitations, notifications and trip shares, "
            "a deliberate data-handling decision."
        )
    op.drop_column("sos_events", "acknowledged_at")
    # Narrowed CHECK + column/FK removal inside batch mode (same SQLite
    # constraint limitation as the upgrade path).
    with op.batch_alter_table("community_reports", recreate="always") as batch_op:
        batch_op.drop_constraint("status_valid", type_="check")
        batch_op.create_check_constraint(
            "status_valid",
            "status IN ('pending', 'approved', 'rejected')",
        )
        batch_op.drop_constraint(
            op.f("fk_community_reports_reviewed_by_users"), type_="foreignkey"
        )
        batch_op.drop_column("reviewed_by")
        batch_op.drop_column("reviewed_at")
    op.drop_index(op.f("ix_trip_shares_owner_id"), table_name="trip_shares")
    op.drop_table("trip_shares")
    op.drop_index(op.f("ix_notifications_user_id"), table_name="notifications")
    op.drop_index(op.f("ix_notifications_kind"), table_name="notifications")
    op.drop_table("notifications")
    op.drop_index(op.f("ix_meetup_announcements_meetup_id"), table_name="meetup_announcements")
    op.drop_table("meetup_announcements")
    op.drop_index(op.f("ix_event_invitations_meetup_id"), table_name="event_invitations")
    op.drop_index(op.f("ix_event_invitations_invitee_id"), table_name="event_invitations")
    op.drop_table("event_invitations")
    op.drop_index(op.f("ix_meetup_memberships_user_id"), table_name="meetup_memberships")
    op.drop_index(op.f("ix_meetup_memberships_meetup_id"), table_name="meetup_memberships")
    op.drop_table("meetup_memberships")
    op.drop_index(op.f("ix_meetups_host_id"), table_name="meetups")
    op.drop_index(op.f("ix_meetups_discovery"), table_name="meetups")
    op.drop_table("meetups")
