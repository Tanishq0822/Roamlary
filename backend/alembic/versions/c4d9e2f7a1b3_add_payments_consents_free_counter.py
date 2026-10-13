"""Add pay-per-post payments, safety consents + free-post counter (Phases 14-15).

Revision ID: c4d9e2f7a1b3
Revises: b8e2f4a1c6d9
Create Date: 2026-10-15

New tables (all additive, nothing existing is touched):
- `post_payments` (UNIQUE idempotency_key + UNIQUE provider_reference,
  non-negative amount CHECK, status CHECK),
- `safety_consents` (decision CHECK, subject index; append-only by
  design - no update/delete paths exist).

Column addition:
- `users.free_posts_used` (NOT NULL, server default 0: every account
  starts with its free entitlement intact).

The DDL mirrors the SQLAlchemy models EXACTLY. The upgrade needs no
data guard (new tables; the counter backfills to 0 - the secure
starting point: nobody loses a free post they never had).

The downgrade is DATA-GUARDED: it refuses while any payment or consent
row exists, so a stray downgrade can never destroy charge records or
consent history - that data-handling decision belongs to an operator,
deliberately (same guard policy as all prior guarded migrations).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c4d9e2f7a1b3"
down_revision: str | None = "b8e2f4a1c6d9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the Phases 14-15 tables and the free-post counter."""
    op.add_column(
        "users", sa.Column("free_posts_used", sa.Integer(), server_default="0", nullable=False)
    )

    op.create_table(
        "post_payments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("category", sa.String(length=40), nullable=False),
        sa.Column("subject_type", sa.String(length=40), nullable=True),
        sa.Column("subject_id", sa.Uuid(), nullable=True),
        sa.Column("amount_paise", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=10), server_default="INR", nullable=False),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("provider", sa.String(length=20), server_default="none", nullable=False),
        sa.Column("provider_reference", sa.String(length=120), nullable=True),
        sa.Column("idempotency_key", sa.String(length=100), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending', 'succeeded', 'failed', 'cancelled', 'refunded')",
            name=op.f("ck_post_payments_status_valid"),
        ),
        sa.CheckConstraint("amount_paise >= 0", name=op.f("ck_post_payments_amount_non_negative")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_post_payments_user_id_users"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_post_payments")),
        sa.UniqueConstraint("idempotency_key", name=op.f("uq_post_payments_idempotency_key")),
        sa.UniqueConstraint("provider_reference", name=op.f("uq_post_payments_provider_reference")),
    )
    op.create_index(op.f("ix_post_payments_category"), "post_payments", ["category"], unique=False)
    op.create_index(op.f("ix_post_payments_user_id"), "post_payments", ["user_id"], unique=False)

    op.create_table(
        "safety_consents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("subject_type", sa.String(length=20), nullable=False),
        sa.Column("subject_id", sa.Uuid(), nullable=False),
        sa.Column("share_trip_details", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("checkin_reminders", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("sos_notify", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("decision", sa.String(length=20), server_default="declined", nullable=False),
        sa.Column("disclosure_version", sa.String(length=20), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "decision IN ('accepted', 'declined')",
            name=op.f("ck_safety_consents_decision_valid"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_safety_consents_user_id_users"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_safety_consents")),
    )
    op.create_index(op.f("ix_safety_consents_subject"), "safety_consents", ["user_id", "subject_type", "subject_id", "created_at"], unique=False)
    op.create_index(op.f("ix_safety_consents_user_id"), "safety_consents", ["user_id"], unique=False)


def downgrade() -> None:
    """Drop the Phases 14-15 structures - DATA-GUARDED.

    Refuses while any payment or consent row exists so charge records
    and consent history can never be destroyed by a stray downgrade:
    the operator must export or delete the rows first - a deliberate
    data-handling decision.
    """
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    counts: dict[str, int] = {}
    for table in ("post_payments", "safety_consents"):
        if inspector.has_table(table):
            counts[table] = bind.execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar() or 0
    total = sum(counts.values())
    if total:
        parts = ", ".join(f"{name}={count}" for name, count in counts.items() if count)
        raise RuntimeError(
            f"Refusing to downgrade: {total} Phases 14-15 row(s) exist ({parts}). "
            "Export or delete this data first - dropping these tables "
            "destroys payment and consent records, "
            "a deliberate data-handling decision."
        )
    op.drop_index(op.f("ix_safety_consents_user_id"), table_name="safety_consents")
    op.drop_index(op.f("ix_safety_consents_subject"), table_name="safety_consents")
    op.drop_table("safety_consents")
    op.drop_index(op.f("ix_post_payments_user_id"), table_name="post_payments")
    op.drop_index(op.f("ix_post_payments_category"), table_name="post_payments")
    op.drop_table("post_payments")
    op.drop_column("users", "free_posts_used")
