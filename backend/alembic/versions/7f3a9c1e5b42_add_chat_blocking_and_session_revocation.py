"""Add chat, blocking and session-revocation surface (Phase 8).

Revision ID: 7f3a9c1e5b42
Revises: 426dcef31e27
Create Date: 2026-10-14

Four brand-new tables plus two additive changes to existing tables:

- `user_blocks` (directed block rows, UNIQUE per blocker/blocked pair,
  no-self CHECK),
- `conversations` (ONE row per canonical unordered user pair, UNIQUE;
  pending/accepted/rejected/cancelled lifecycle),
- `messages` (text-only, soft-delete flags, history index),
- `auth_sessions` (one row per login; revocation kills the token),
- `users.token_version` (NOT NULL, server default 0: "revoke all"
  bumps it and kills every token, including pre-Phase-8 legacy ones),
- `travel_partner_requests.pair_low_id/pair_high_id` + a pending-only
  UNIQUE index on the canonical pair: the Phase 7 cross-direction race
  fix (two simultaneous opposite-direction sends can no longer both
  land). Backfilled from the existing directed columns with a
  dialect-aware UPDATE (PostgreSQL LEAST/GREATEST on uuid, SQLite
  min/max on the stored hex - both order identically to
  app/core/pairing.canonical_pair).

The DDL mirrors the SQLAlchemy models EXACTLY. The upgrade needs no
data guard for the new tables (nothing existing can violate them); the
pair-column backfill is a pure derivation of stored IDs.

The downgrade is DATA-GUARDED: it refuses while any block,
conversation, message, or session row exists, so a stray downgrade can
never destroy contact-safety or chat history - that data-handling
decision belongs to an operator, deliberately (same guard policy as the
Phase 4, 6b and 7 migrations).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7f3a9c1e5b42"
down_revision: str | None = "426dcef31e27"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# The single window in which a pair may hold an open travel request.
_PENDING_PREDICATE = sa.text("status = 'pending'")


def upgrade() -> None:
    """Create the Phase 8 tables and additive columns (no data to move)."""
    op.add_column("users", sa.Column("token_version", sa.Integer(), server_default="0", nullable=False))

    op.create_table(
        "user_blocks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("blocker_id", sa.Uuid(), nullable=False),
        sa.Column("blocked_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("blocker_id <> blocked_id", name=op.f("ck_user_blocks_no_self_block")),
        sa.ForeignKeyConstraint(["blocker_id"], ["users.id"], name=op.f("fk_user_blocks_blocker_id_users"), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["blocked_id"], ["users.id"], name=op.f("fk_user_blocks_blocked_id_users"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_blocks")),
        sa.UniqueConstraint("blocker_id", "blocked_id", name=op.f("uq_user_blocks_pair")),
    )
    op.create_index(op.f("ix_user_blocks_blocker_id"), "user_blocks", ["blocker_id"], unique=False)
    op.create_index(op.f("ix_user_blocks_blocked_id"), "user_blocks", ["blocked_id"], unique=False)

    op.create_table(
        "conversations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_low_id", sa.Uuid(), nullable=False),
        sa.Column("user_high_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("requested_by", sa.Uuid(), nullable=False),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("user_low_id <> user_high_id", name=op.f("ck_conversations_no_self_conversation")),
        sa.CheckConstraint(
            "status IN ('pending', 'accepted', 'rejected', 'cancelled')",
            name=op.f("ck_conversations_status_valid"),
        ),
        sa.ForeignKeyConstraint(["requested_by"], ["users.id"], name=op.f("fk_conversations_requested_by_users"), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_high_id"], ["users.id"], name=op.f("fk_conversations_user_high_id_users"), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_low_id"], ["users.id"], name=op.f("fk_conversations_user_low_id_users"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_conversations")),
        sa.UniqueConstraint("user_low_id", "user_high_id", name=op.f("uq_conversations_pair")),
    )
    op.create_index(op.f("ix_conversations_high_status"), "conversations", ["user_high_id", "status"], unique=False)
    op.create_index(op.f("ix_conversations_low_status"), "conversations", ["user_low_id", "status"], unique=False)
    op.create_index(op.f("ix_conversations_user_high_id"), "conversations", ["user_high_id"], unique=False)
    op.create_index(op.f("ix_conversations_user_low_id"), "conversations", ["user_low_id"], unique=False)

    op.create_table(
        "messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("sender_id", sa.Uuid(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], name=op.f("fk_messages_conversation_id_conversations"), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["sender_id"], ["users.id"], name=op.f("fk_messages_sender_id_users"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_messages")),
    )
    op.create_index(op.f("ix_messages_conversation_id"), "messages", ["conversation_id"], unique=False)
    op.create_index(op.f("ix_messages_conversation_time"), "messages", ["conversation_id", "created_at", "id"], unique=False)
    op.create_index(op.f("ix_messages_sender_id"), "messages", ["sender_id"], unique=False)

    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("label", sa.String(length=80), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_auth_sessions_user_id_users"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_auth_sessions")),
    )
    op.create_index(op.f("ix_auth_sessions_user_id"), "auth_sessions", ["user_id"], unique=False)
    op.create_index(op.f("ix_auth_sessions_user_revoked"), "auth_sessions", ["user_id", "revoked_at"], unique=False)

    # Phase 7 race fix: canonical pair columns on the existing request
    # table. Added nullable, backfilled from the directed columns with a
    # dialect-aware UPDATE (LEAST/GREATEST exist on PostgreSQL;
    # min/max are the SQLite scalar equivalents - both order exactly
    # like app/core/pairing.canonical_pair), then locked by the
    # pending-only UNIQUE index below. Columns stay nullable in the DDL
    # (SQLite cannot add NOT NULL to a populated table without a full
    # rebuild); the application always writes both, and the model
    # declares them optional for the same reason.
    op.add_column("travel_partner_requests", sa.Column("pair_high_id", sa.Uuid(), nullable=True))
    op.add_column("travel_partner_requests", sa.Column("pair_low_id", sa.Uuid(), nullable=True))
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        bind.execute(
            sa.text(
                "UPDATE travel_partner_requests "
                "SET pair_low_id = LEAST(requester_id, recipient_id), "
                "pair_high_id = GREATEST(requester_id, recipient_id)"
            )
        )
    else:
        bind.execute(
            sa.text(
                "UPDATE travel_partner_requests "
                "SET pair_low_id = min(requester_id, recipient_id), "
                "pair_high_id = max(requester_id, recipient_id)"
            )
        )
    op.create_index(
        "uq_travel_partner_requests_pending_canonical_pair",
        "travel_partner_requests",
        ["pair_low_id", "pair_high_id"],
        unique=True,
        postgresql_where=_PENDING_PREDICATE,
        sqlite_where=_PENDING_PREDICATE,
    )
    op.create_index(op.f("ix_travel_partner_requests_pair_high_id"), "travel_partner_requests", ["pair_high_id"], unique=False)
    op.create_index(op.f("ix_travel_partner_requests_pair_low_id"), "travel_partner_requests", ["pair_low_id"], unique=False)


def downgrade() -> None:
    """Drop the Phase 8 tables and columns - DATA-GUARDED.

    Refuses while any block, conversation, message, or session row
    exists so Phase 8 history can never be destroyed by a stray
    downgrade: the operator must export or delete the rows first - a
    deliberate data-handling decision.
    """
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    counts: dict[str, int] = {}
    for table in ("user_blocks", "conversations", "messages", "auth_sessions"):
        if inspector.has_table(table):
            counts[table] = bind.execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar() or 0
    total = sum(counts.values())
    if total:
        parts = ", ".join(f"{name}={count}" for name, count in counts.items() if count)
        raise RuntimeError(
            f"Refusing to downgrade: {total} Phase 8 row(s) exist ({parts}). "
            "Export or delete this data first - dropping these tables "
            "destroys blocks, conversations, messages and session records, "
            "a deliberate data-handling decision."
        )
    op.drop_index(op.f("ix_travel_partner_requests_pair_low_id"), table_name="travel_partner_requests")
    op.drop_index(op.f("ix_travel_partner_requests_pair_high_id"), table_name="travel_partner_requests")
    op.drop_index("uq_travel_partner_requests_pending_canonical_pair", table_name="travel_partner_requests")
    op.drop_column("travel_partner_requests", "pair_low_id")
    op.drop_column("travel_partner_requests", "pair_high_id")
    op.drop_index(op.f("ix_auth_sessions_user_revoked"), table_name="auth_sessions")
    op.drop_index(op.f("ix_auth_sessions_user_id"), table_name="auth_sessions")
    op.drop_table("auth_sessions")
    op.drop_index(op.f("ix_messages_sender_id"), table_name="messages")
    op.drop_index(op.f("ix_messages_conversation_time"), table_name="messages")
    op.drop_index(op.f("ix_messages_conversation_id"), table_name="messages")
    op.drop_table("messages")
    op.drop_index(op.f("ix_conversations_user_low_id"), table_name="conversations")
    op.drop_index(op.f("ix_conversations_user_high_id"), table_name="conversations")
    op.drop_index(op.f("ix_conversations_low_status"), table_name="conversations")
    op.drop_index(op.f("ix_conversations_high_status"), table_name="conversations")
    op.drop_table("conversations")
    op.drop_index(op.f("ix_user_blocks_blocked_id"), table_name="user_blocks")
    op.drop_index(op.f("ix_user_blocks_blocker_id"), table_name="user_blocks")
    op.drop_table("user_blocks")
    op.drop_column("users", "token_version")
