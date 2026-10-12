"""add identity verification foundation

Revision ID: 3e285edb0896
Revises: ab32047c8481
Create Date: 2026-10-12 15:42:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '3e285edb0896'
down_revision: Union[str, None] = 'ab32047c8481'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# The project's MetaData naming convention, copied verbatim into this
# migration so the file is SELF-CONTAINED. Migrations are frozen history:
# they must never import live application code, because that code can
# change later and silently break old migrations. (Same pattern as
# migrations ccd362671e07, 0dd8995649b4 and ab32047c8481.)
_NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

# The Phase 6b state sets (must match the application enums and the CHECKs
# below; kept literal here so the migration is frozen history).
_ACCOUNT_STATUSES = "'unverified', 'pending', 'verified', 'rejected'"
_ROLES = "'user', 'owner'"
_REQUEST_STATUSES = "'pending', 'approved', 'rejected'"


def upgrade() -> None:
    # NO upgrade-side data guard is needed here, and the reason is worth
    # recording: migrations ab32047c8481 / ccd362671e07 / 0dd8995649b4
    # had to REFUSE because they added CHECK constraints over EXISTING
    # free-form data that might violate them. This migration adds two NEW
    # columns that did not exist before, each NOT NULL WITH a one-time
    # server default, so every pre-existing users row is backfilled as
    # 'unverified'/'user' - the secure starting point - and no historical
    # value can violate the new CHECKs. The three new tables start empty.
    # Nothing existing is converted, dropped, or rewritten.

    # users: account verification state + authorization role.
    # batch_alter_table is REQUIRED for cross-dialect support (SQLite
    # rebuilds the table, PostgreSQL issues a real ALTER TABLE); short
    # logical constraint names expand via the naming convention to
    # 'ck_users_verification_status_valid' / 'ck_users_role_valid'.
    with op.batch_alter_table('users', naming_convention=_NAMING_CONVENTION) as batch_op:
        batch_op.add_column(sa.Column(
            'verification_status', sa.String(length=20),
            server_default='unverified', nullable=False,
        ))
        batch_op.add_column(sa.Column(
            'role', sa.String(length=20),
            server_default='user', nullable=False,
        ))
        batch_op.create_check_constraint(
            'verification_status_valid',
            f"verification_status IN ({_ACCOUNT_STATUSES})",
        )
        batch_op.create_check_constraint(
            'role_valid',
            f"role IN ({_ROLES})",
        )

    # The verification-request history: one row per submission, reviewer
    # decision + timestamps included. ON DELETE RESTRICT on both FKs so
    # verification history can never be deleted by accident (applicant
    # AND reviewer rows stay).
    op.create_table(
        'identity_verifications',
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('reviewed_by', sa.Uuid(), nullable=True),
        sa.Column('review_note', sa.Text(), nullable=True),
        sa.Column('applicant_note', sa.Text(), nullable=True),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint(f"status IN ({_REQUEST_STATUSES})", name=op.f('ck_identity_verifications_status_valid')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_identity_verifications_user_id_users'), ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['reviewed_by'], ['users.id'], name=op.f('fk_identity_verifications_reviewed_by_users'), ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_identity_verifications'))
    )
    op.create_index(op.f('ix_identity_verifications_user_id'), 'identity_verifications', ['user_id'], unique=False)

    # Runtime settings (currently exactly one key: social_requires_verification).
    # The unique index on `key` is the natural primary lookup path.
    op.create_table(
        'app_settings',
        sa.Column('key', sa.String(length=64), nullable=False),
        sa.Column('value', sa.String(length=100), nullable=False),
        sa.Column('updated_by', sa.Uuid(), nullable=True),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['updated_by'], ['users.id'], name=op.f('fk_app_settings_updated_by_users'), ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_app_settings'))
    )
    op.create_index(op.f('ix_app_settings_key'), 'app_settings', ['key'], unique=True)

    # Append-only audit trail: who changed which setting, when, old/new.
    op.create_table(
        'setting_changes',
        sa.Column('setting_key', sa.String(length=64), nullable=False),
        sa.Column('old_value', sa.String(length=100), nullable=True),
        sa.Column('new_value', sa.String(length=100), nullable=False),
        sa.Column('changed_by', sa.Uuid(), nullable=False),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['changed_by'], ['users.id'], name=op.f('fk_setting_changes_changed_by_users'), ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_setting_changes'))
    )
    op.create_index(op.f('ix_setting_changes_setting_key'), 'setting_changes', ['setting_key'], unique=False)


def downgrade() -> None:
    # DATA-SAFETY GUARD - checked BEFORE any schema change (same proven
    # pattern as migrations ccd362671e07 and 0dd8995649b4, mirrored to
    # the downgrade direction). Rolling back would DROP the verification
    # history, the policy setting, and its audit trail, and would strip
    # the two users columns - destroying real data if any exists. This
    # migration REFUSES instead. The check runs before any DDL, so a
    # refusal leaves the schema and every record exactly as they are.
    connection = op.get_bind()
    verification_rows = connection.execute(
        sa.text("SELECT count(*) FROM identity_verifications")
    ).scalar_one()
    setting_rows = connection.execute(
        sa.text("SELECT count(*) FROM app_settings")
    ).scalar_one()
    audit_rows = connection.execute(
        sa.text("SELECT count(*) FROM setting_changes")
    ).scalar_one()
    non_default_users = connection.execute(
        sa.text(
            "SELECT count(*) FROM users "
            "WHERE verification_status <> 'unverified' OR role <> 'user'"
        )
    ).scalar_one()
    if verification_rows or setting_rows or audit_rows or non_default_users:
        raise RuntimeError(
            "Refusing to downgrade migration 3e285edb0896: "
            f"{verification_rows} verification request(s), "
            f"{setting_rows} setting row(s), {audit_rows} audit row(s) "
            f"and {non_default_users} user(s) with a non-default "
            "verification state or role exist. Rolling back would delete "
            "verification history, the policy record, and role/state data "
            "- no schema changes were made and no records were deleted, "
            "so the database is unchanged and still at revision "
            "3e285edb0896. Make an explicit data-handling decision first "
            "(export or accept the loss of these records), then run the "
            "downgrade again."
        )

    # Only ever reached when EVERY table is empty and every user is at the
    # secure defaults - dropping then loses nothing.
    op.drop_index(op.f('ix_setting_changes_setting_key'), table_name='setting_changes')
    op.drop_table('setting_changes')
    op.drop_index(op.f('ix_app_settings_key'), table_name='app_settings')
    op.drop_table('app_settings')
    op.drop_index(op.f('ix_identity_verifications_user_id'), table_name='identity_verifications')
    op.drop_table('identity_verifications')

    with op.batch_alter_table('users', naming_convention=_NAMING_CONVENTION) as batch_op:
        batch_op.drop_constraint('role_valid', type_='check')
        batch_op.drop_constraint('verification_status_valid', type_='check')
        batch_op.drop_column('role')
        batch_op.drop_column('verification_status')
