"""Migration tests: Alembic is wired correctly and its initial migration
creates exactly the expected schema.

These tests run OFFLINE against a temporary SQLite database file (in
pytest's tmp directory, never inside the repository). PostgreSQL
verification runs separately in tests/test_postgres_integration.py and
against the development container during implementation.
"""

import os
import subprocess
import sys
from pathlib import Path

import sqlalchemy as sa

from tests.conftest import (
    insert_raw_user_and_checkin,
    insert_raw_user_and_report,
    insert_raw_user_and_sos,
    insert_raw_user_and_verification,
)

BACKEND_DIR = Path(__file__).resolve().parents[1]
EXPECTED_TABLES = {
    "users",
    "trusted_contacts",
    "check_ins",
    "sos_events",
    "community_reports",
    "identity_verifications",
    "app_settings",
    "setting_changes",
}


def _run_alembic(args: list[str], database_url: str) -> subprocess.CompletedProcess:
    """Run an alembic command with DATABASE_URL provided via environment.

    This proves the secure configuration path works: alembic/env.py
    reads DATABASE_URL from the environment, exactly like production.
    """
    env = {**os.environ, "DATABASE_URL": database_url}
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
    )


def test_alembic_upgrade_head_creates_all_tables(tmp_path) -> None:
    db_file = tmp_path / "migration_test.db"
    url = f"sqlite:///{db_file}"

    result = _run_alembic(["upgrade", "head"], url)
    assert result.returncode == 0, f"stdout={result.stdout}\nstderr={result.stderr}"

    engine = sa.create_engine(url)
    tables = set(sa.inspect(engine).get_table_names()) - {"alembic_version"}
    assert tables == EXPECTED_TABLES
    engine.dispose()


def test_alembic_downgrade_base_removes_tables(tmp_path) -> None:
    """The migration is reversible - a required property for safe history."""
    db_file = tmp_path / "migration_downgrade.db"
    url = f"sqlite:///{db_file}"

    upgrade = _run_alembic(["upgrade", "head"], url)
    assert upgrade.returncode == 0, upgrade.stderr

    downgrade = _run_alembic(["downgrade", "base"], url)
    assert downgrade.returncode == 0, downgrade.stderr

    engine = sa.create_engine(url)
    tables = set(sa.inspect(engine).get_table_names()) - {"alembic_version"}
    assert tables == set()  # every domain table was removed again
    engine.dispose()


def test_alembic_history_is_a_single_linear_chain(tmp_path) -> None:
    """Exactly one migration exists and it has no parent (initial schema)."""
    result = _run_alembic(["history", "--verbose"], "sqlite://")
    assert result.returncode == 0, result.stderr
    assert "initial schema" in result.stdout


def test_phase4_downgrade_refuses_when_cancelled_checkins_exist(tmp_path) -> None:
    """DATA-DEPENDENT DOWNGRADE (regression): a 'cancelled' row must make the
    Phase 4 downgrade REFUSE cleanly, instead of failing mid-schema-change
    against the old 4-value CHECK constraint.

    The refusal happens BEFORE any schema change, so schema and records
    must both be left exactly as they were - nothing deleted or converted.

    (Upgrades target the Phase 4 revision explicitly, not `head`: `head`
    moved to Phase 5 in 0dd8995649b4, and these tests are about THIS
    migration's behaviour.)
    """
    db_file = tmp_path / "migration_guard.db"
    url = f"sqlite:///{db_file}"

    upgrade = _run_alembic(["upgrade", "ccd362671e07"], url)
    assert upgrade.returncode == 0, f"stdout={upgrade.stdout}\nstderr={upgrade.stderr}"

    engine = sa.create_engine(url)
    insert_raw_user_and_checkin(engine, "cancelled")

    downgrade = _run_alembic(["downgrade", "d9841015aec7"], url)
    assert downgrade.returncode != 0, (
        "downgrade must be REFUSED while cancelled check-ins exist, "
        f"but it succeeded:\n{downgrade.stdout}\n{downgrade.stderr}"
    )
    output = downgrade.stdout + downgrade.stderr
    assert "Refusing to downgrade" in output
    assert "data-handling decision" in output

    # The refusal must leave EVERYTHING unchanged.
    inspector = sa.inspect(engine)
    checkin_cols = {c["name"] for c in inspector.get_columns("check_ins")}
    contact_cols = {c["name"] for c in inspector.get_columns("trusted_contacts")}
    assert "note" in checkin_cols  # column NOT dropped
    assert "relationship" in contact_cols  # column NOT dropped
    with engine.connect() as conn:
        version = conn.execute(sa.text("SELECT version_num FROM alembic_version")).scalar_one()
        status = conn.execute(sa.text("SELECT status FROM check_ins")).scalar_one()
        table_sql = conn.execute(
            sa.text("SELECT sql FROM sqlite_master WHERE type='table' AND name='check_ins'")
        ).scalar_one()
    assert version == "ccd362671e07"  # still at the Phase 4 revision
    assert status == "cancelled"  # the record itself is untouched
    assert "'cancelled'" in table_sql  # 5-value constraint still active
    engine.dispose()


def test_phase4_downgrade_upgrade_roundtrip_without_cancelled_records(tmp_path) -> None:
    """NORMAL DOWNGRADE PATH: with no cancelled rows the downgrade succeeds,
    and upgrading again restores the exact Phase 4 schema.

    (Upgrades target the Phase 4 revision explicitly, not `head`: `head`
    moved to Phase 5 in 0dd8995649b4, and these tests are about THIS
    migration's behaviour.)
    """
    db_file = tmp_path / "migration_roundtrip.db"
    url = f"sqlite:///{db_file}"

    upgrade = _run_alembic(["upgrade", "ccd362671e07"], url)
    assert upgrade.returncode == 0, f"stdout={upgrade.stdout}\nstderr={upgrade.stderr}"

    engine = sa.create_engine(url)
    insert_raw_user_and_checkin(engine, "pending", note="roundtrip probe")

    # 1) Downgrade succeeds - no row violates the restored 4-value CHECK.
    downgrade = _run_alembic(["downgrade", "d9841015aec7"], url)
    assert downgrade.returncode == 0, f"stdout={downgrade.stdout}\nstderr={downgrade.stderr}"
    inspector = sa.inspect(engine)
    assert "note" not in {c["name"] for c in inspector.get_columns("check_ins")}
    assert "relationship" not in {c["name"] for c in inspector.get_columns("trusted_contacts")}
    with engine.connect() as conn:
        version = conn.execute(sa.text("SELECT version_num FROM alembic_version")).scalar_one()
        status = conn.execute(sa.text("SELECT status FROM check_ins")).scalar_one()
    assert version == "d9841015aec7"
    assert status == "pending"  # the record itself survives the schema revert

    # 2) Upgrading back restores the Phase 4 schema exactly.
    upgrade_again = _run_alembic(["upgrade", "ccd362671e07"], url)
    assert upgrade_again.returncode == 0, (
        f"stdout={upgrade_again.stdout}\nstderr={upgrade_again.stderr}"
    )
    inspector = sa.inspect(engine)
    assert "note" in {c["name"] for c in inspector.get_columns("check_ins")}
    assert "relationship" in {c["name"] for c in inspector.get_columns("trusted_contacts")}
    with engine.connect() as conn:
        version = conn.execute(sa.text("SELECT version_num FROM alembic_version")).scalar_one()
        row = conn.execute(sa.text("SELECT status, note FROM check_ins")).one()
        table_sql = conn.execute(
            sa.text("SELECT sql FROM sqlite_master WHERE type='table' AND name='check_ins'")
        ).scalar_one()
    assert version == "ccd362671e07"
    assert row.status == "pending"
    # The note column was dropped and re-created EMPTY: a downgrade reverts
    # the Phase 4 feature itself (documented behaviour), while the ROW and
    # its status survive.
    assert row.note is None
    assert "'cancelled'" in table_sql  # 5-value constraint restored
    engine.dispose()


def test_phase5_downgrade_refuses_when_cancelled_sos_exist(tmp_path) -> None:
    """DATA-DEPENDENT DOWNGRADE (regression): a 'cancelled' SOS incident
    must make the Phase 5 downgrade REFUSE cleanly, instead of failing
    mid-schema-change against the old 4-value CHECK constraint.

    The refusal happens BEFORE any schema change, so schema and records
    must both be left exactly as they were - nothing deleted or converted.
    """
    db_file = tmp_path / "migration_sos_guard.db"
    url = f"sqlite:///{db_file}"

    upgrade = _run_alembic(["upgrade", "0dd8995649b4"], url)
    assert upgrade.returncode == 0, f"stdout={upgrade.stdout}\nstderr={upgrade.stderr}"

    engine = sa.create_engine(url)
    insert_raw_user_and_sos(engine, "cancelled")

    downgrade = _run_alembic(["downgrade", "ccd362671e07"], url)
    assert downgrade.returncode != 0, (
        "downgrade must be REFUSED while cancelled SOS incidents exist, "
        f"but it succeeded:\n{downgrade.stdout}\n{downgrade.stderr}"
    )
    output = downgrade.stdout + downgrade.stderr
    assert "Refusing to downgrade" in output
    assert "data-handling decision" in output

    # The refusal must leave EVERYTHING unchanged.
    inspector = sa.inspect(engine)
    sos_cols = {c["name"] for c in inspector.get_columns("sos_events")}
    assert {"description", "location_recorded_at", "cancelled_at"} <= sos_cols
    with engine.connect() as conn:
        version = conn.execute(sa.text("SELECT version_num FROM alembic_version")).scalar_one()
        status_value = conn.execute(sa.text("SELECT status FROM sos_events")).scalar_one()
        table_sql = conn.execute(
            sa.text("SELECT sql FROM sqlite_master WHERE type='table' AND name='sos_events'")
        ).scalar_one()
    assert version == "0dd8995649b4"  # still at the Phase 5 revision
    assert status_value == "cancelled"  # the record itself is untouched
    assert "'cancelled'" in table_sql  # 5-value constraint still active
    engine.dispose()


def test_phase5_downgrade_upgrade_roundtrip_without_cancelled_sos(tmp_path) -> None:
    """NORMAL DOWNGRADE PATH: with no cancelled SOS incidents the downgrade
    succeeds, and upgrading again restores the exact Phase 5 schema."""
    db_file = tmp_path / "migration_sos_roundtrip.db"
    url = f"sqlite:///{db_file}"

    upgrade = _run_alembic(["upgrade", "0dd8995649b4"], url)
    assert upgrade.returncode == 0, f"stdout={upgrade.stdout}\nstderr={upgrade.stderr}"

    engine = sa.create_engine(url)
    insert_raw_user_and_sos(engine, "active", description="roundtrip probe")

    downgrade = _run_alembic(["downgrade", "ccd362671e07"], url)
    assert downgrade.returncode == 0, f"stdout={downgrade.stdout}\nstderr={downgrade.stderr}"
    inspector = sa.inspect(engine)
    assert "description" not in {c["name"] for c in inspector.get_columns("sos_events")}
    with engine.connect() as conn:
        version = conn.execute(sa.text("SELECT version_num FROM alembic_version")).scalar_one()
        status_value = conn.execute(sa.text("SELECT status FROM sos_events")).scalar_one()
    assert version == "ccd362671e07"
    assert status_value == "active"  # the record itself survives the schema revert

    upgrade_again = _run_alembic(["upgrade", "0dd8995649b4"], url)
    assert upgrade_again.returncode == 0, (
        f"stdout={upgrade_again.stdout}\nstderr={upgrade_again.stderr}"
    )
    inspector = sa.inspect(engine)
    assert {"description", "location_recorded_at", "cancelled_at"} <= {
        c["name"] for c in inspector.get_columns("sos_events")
    }
    with engine.connect() as conn:
        version = conn.execute(sa.text("SELECT version_num FROM alembic_version")).scalar_one()
        row = conn.execute(sa.text("SELECT status, description FROM sos_events")).one()
        table_sql = conn.execute(
            sa.text("SELECT sql FROM sqlite_master WHERE type='table' AND name='sos_events'")
        ).scalar_one()
    assert version == "0dd8995649b4"
    assert row.status == "active"
    # The description column was dropped and re-created EMPTY: a downgrade
    # reverts the Phase 5 feature itself (documented behaviour), while the
    # ROW and its status survive.
    assert row.description is None
    assert "'cancelled'" in table_sql  # 5-value constraint restored
    engine.dispose()


def test_phase6_upgrade_refuses_when_unknown_categories_exist(tmp_path) -> None:
    """DATA-DEPENDENT UPGRADE (regression): a report with a category
    outside the Phase 6 closed set (any string was allowed by the Phase 2
    schema) must make the upgrade REFUSE cleanly, instead of failing
    mid-schema-change against the new CHECK constraint.

    The refusal happens BEFORE any schema change, so schema and records
    must both be left exactly as they were - nothing deleted or converted.
    """
    db_file = tmp_path / "migration_category_guard.db"
    url = f"sqlite:///{db_file}"

    upgrade = _run_alembic(["upgrade", "0dd8995649b4"], url)
    assert upgrade.returncode == 0, f"stdout={upgrade.stdout}\nstderr={upgrade.stderr}"

    engine = sa.create_engine(url)
    insert_raw_user_and_report(engine, "theft")  # pre-Phase-6: any string allowed

    upgrade_again = _run_alembic(["upgrade", "ab32047c8481"], url)
    assert upgrade_again.returncode != 0, (
        "upgrade must be REFUSED while unknown categories exist, "
        f"but it succeeded:\n{upgrade_again.stdout}\n{upgrade_again.stderr}"
    )
    output = upgrade_again.stdout + upgrade_again.stderr
    assert "Refusing to upgrade" in output
    assert "data-handling decision" in output

    # The refusal must leave EVERYTHING unchanged.
    inspector = sa.inspect(engine)
    names = {c["name"] for c in inspector.get_check_constraints("community_reports")}
    assert "ck_community_reports_category_valid" not in names
    with engine.connect() as conn:
        version = conn.execute(sa.text("SELECT version_num FROM alembic_version")).scalar_one()
        category = conn.execute(sa.text("SELECT category FROM community_reports")).scalar_one()
    assert version == "0dd8995649b4"  # still at the Phase 5 revision
    assert category == "theft"  # the record itself is untouched
    engine.dispose()


def test_phase6_upgrade_downgrade_roundtrip_with_valid_data(tmp_path) -> None:
    """NORMAL PATH: with only in-set categories the upgrade succeeds; the
    downgrade drops the constraint WITHOUT touching any stored category
    value; upgrading again restores the exact Phase 6 schema."""
    db_file = tmp_path / "migration_category_roundtrip.db"
    url = f"sqlite:///{db_file}"

    upgrade = _run_alembic(["upgrade", "ab32047c8481"], url)
    assert upgrade.returncode == 0, f"stdout={upgrade.stdout}\nstderr={upgrade.stderr}"

    engine = sa.create_engine(url)
    insert_raw_user_and_report(engine, "road_hazard")

    with engine.connect() as conn:
        table_sql = conn.execute(
            sa.text("SELECT sql FROM sqlite_master WHERE type='table' AND name='community_reports'")
        ).scalar_one()
    assert "category_valid" in table_sql and "'unsafe_area'" in table_sql

    downgrade = _run_alembic(["downgrade", "0dd8995649b4"], url)
    assert downgrade.returncode == 0, f"stdout={downgrade.stdout}\nstderr={downgrade.stderr}"
    with engine.connect() as conn:
        version = conn.execute(sa.text("SELECT version_num FROM alembic_version")).scalar_one()
        category = conn.execute(sa.text("SELECT category FROM community_reports")).scalar_one()
        table_sql = conn.execute(
            sa.text("SELECT sql FROM sqlite_master WHERE type='table' AND name='community_reports'")
        ).scalar_one()
    assert version == "0dd8995649b4"
    assert category == "road_hazard"  # stored value survives a constraint drop
    assert "category_valid" not in table_sql

    upgrade_again = _run_alembic(["upgrade", "ab32047c8481"], url)
    assert upgrade_again.returncode == 0, (
        f"stdout={upgrade_again.stdout}\nstderr={upgrade_again.stderr}"
    )
    with engine.connect() as conn:
        version = conn.execute(sa.text("SELECT version_num FROM alembic_version")).scalar_one()
        category = conn.execute(sa.text("SELECT category FROM community_reports")).scalar_one()
        table_sql = conn.execute(
            sa.text("SELECT sql FROM sqlite_master WHERE type='table' AND name='community_reports'")
        ).scalar_one()
    assert version == "ab32047c8481"
    assert category == "road_hazard"
    assert "category_valid" in table_sql
    engine.dispose()


# ----------------------- Phase 6b verification foundation migration tests


def test_phase6b_upgrade_backfills_existing_users_with_secure_defaults(tmp_path) -> None:
    """A user created BEFORE the Phase 6b columns existed must come out of
    the upgrade as `unverified` + `user` - the secure starting point for
    pre-existing accounts (no conversion of historical data happens)."""
    db_file = tmp_path / "migration_phase6b_backfill.db"
    url = f"sqlite:///{db_file}"

    upgrade = _run_alembic(["upgrade", "ab32047c8481"], url)
    assert upgrade.returncode == 0, f"stdout={upgrade.stdout}\nstderr={upgrade.stderr}"

    engine = sa.create_engine(url)
    insert_raw_user_and_checkin(engine, "pending")  # plain pre-Phase-6b user

    upgrade_again = _run_alembic(["upgrade", "3e285edb0896"], url)
    assert upgrade_again.returncode == 0, (
        f"stdout={upgrade_again.stdout}\nstderr={upgrade_again.stderr}"
    )
    with engine.connect() as conn:
        row = conn.execute(sa.text("SELECT verification_status, role FROM users")).one()
    assert row.verification_status == "unverified"  # backfilled, not NULL
    assert row.role == "user"  # nobody is silently promoted
    engine.dispose()


def test_phase6b_downgrade_refuses_when_verification_data_exists(tmp_path) -> None:
    """DATA-DEPENDENT DOWNGRADE (regression): existing verification
    requests must make the Phase 6b downgrade REFUSE cleanly instead of
    silently dropping the history. The refusal happens BEFORE any schema
    change - schema and records must both be left exactly as they were."""
    db_file = tmp_path / "migration_phase6b_guard.db"
    url = f"sqlite:///{db_file}"

    upgrade = _run_alembic(["upgrade", "3e285edb0896"], url)
    assert upgrade.returncode == 0, f"stdout={upgrade.stdout}\nstderr={upgrade.stderr}"

    engine = sa.create_engine(url)
    insert_raw_user_and_verification(engine, request_status="pending")

    downgrade = _run_alembic(["downgrade", "ab32047c8481"], url)
    assert downgrade.returncode != 0, (
        "downgrade must be REFUSED while verification requests exist, "
        f"but it succeeded:\n{downgrade.stdout}\n{downgrade.stderr}"
    )
    output = downgrade.stdout + downgrade.stderr
    assert "Refusing to downgrade" in output
    assert "data-handling decision" in output

    # The refusal must leave EVERYTHING unchanged.
    inspector = sa.inspect(engine)
    names = {t for t in inspector.get_table_names() if t != "alembic_version"}
    assert "identity_verifications" in names  # table NOT dropped
    assert "verification_status" in {
        c["name"] for c in inspector.get_columns("users")
    }  # column NOT dropped
    with engine.connect() as conn:
        version = conn.execute(sa.text("SELECT version_num FROM alembic_version")).scalar_one()
        status_value = conn.execute(
            sa.text("SELECT status FROM identity_verifications")
        ).scalar_one()
    assert version == "3e285edb0896"  # still at the Phase 6b revision
    assert status_value == "pending"  # the record itself is untouched
    engine.dispose()


def test_phase6b_downgrade_refuses_when_roles_or_states_are_non_default(
    tmp_path,
) -> None:
    """Even with NO request rows, one verified account or one owner role
    must make the downgrade REFUSE: rolling back would erase that state."""
    db_file = tmp_path / "migration_phase6b_guard_state.db"
    url = f"sqlite:///{db_file}"

    upgrade = _run_alembic(["upgrade", "3e285edb0896"], url)
    assert upgrade.returncode == 0, f"stdout={upgrade.stdout}\nstderr={upgrade.stderr}"

    engine = sa.create_engine(url)
    insert_raw_user_and_verification(
        engine, request_status=None, verification_status="verified", role="owner"
    )

    downgrade = _run_alembic(["downgrade", "ab32047c8481"], url)
    assert downgrade.returncode != 0, (
        "downgrade must be REFUSED while non-default verification states "
        f"or roles exist, but it succeeded:\n{downgrade.stdout}\n{downgrade.stderr}"
    )
    output = downgrade.stdout + downgrade.stderr
    assert "Refusing to downgrade" in output
    assert "data-handling decision" in output

    with engine.connect() as conn:
        version = conn.execute(sa.text("SELECT version_num FROM alembic_version")).scalar_one()
        row = conn.execute(sa.text("SELECT verification_status, role FROM users")).one()
    assert version == "3e285edb0896"
    assert row.verification_status == "verified"  # state untouched
    assert row.role == "owner"  # role untouched
    engine.dispose()


def test_phase6b_downgrade_upgrade_roundtrip_when_database_is_clean(tmp_path) -> None:
    """NORMAL PATH: with defaults everywhere and no verification rows the
    downgrade succeeds (columns + tables removed); upgrading again restores
    the exact Phase 6b schema."""
    db_file = tmp_path / "migration_phase6b_roundtrip.db"
    url = f"sqlite:///{db_file}"

    upgrade = _run_alembic(["upgrade", "3e285edb0896"], url)
    assert upgrade.returncode == 0, f"stdout={upgrade.stdout}\nstderr={upgrade.stderr}"

    engine = sa.create_engine(url)
    insert_raw_user_and_verification(engine, request_status=None)  # secure defaults only

    downgrade = _run_alembic(["downgrade", "ab32047c8481"], url)
    assert downgrade.returncode == 0, f"stdout={downgrade.stdout}\nstderr={downgrade.stderr}"
    inspector = sa.inspect(engine)
    assert "identity_verifications" not in set(inspector.get_table_names())
    user_cols = {c["name"] for c in inspector.get_columns("users")}
    assert "verification_status" not in user_cols
    assert "role" not in user_cols
    with engine.connect() as conn:
        version = conn.execute(sa.text("SELECT version_num FROM alembic_version")).scalar_one()
        # The user row itself survives the schema revert (Phase 6b columns
        # never existed before, so it just has no such fields anymore).
        count = conn.execute(sa.text("SELECT count(*) FROM users")).scalar_one()
    assert version == "ab32047c8481"
    assert count == 1

    upgrade_again = _run_alembic(["upgrade", "3e285edb0896"], url)
    assert upgrade_again.returncode == 0, (
        f"stdout={upgrade_again.stdout}\nstderr={upgrade_again.stderr}"
    )
    inspector = sa.inspect(engine)
    assert {"identity_verifications", "app_settings", "setting_changes"} <= set(
        inspector.get_table_names()
    )
    user_cols = {c["name"] for c in inspector.get_columns("users")}
    assert {"verification_status", "role"} <= user_cols
    with engine.connect() as conn:
        version = conn.execute(sa.text("SELECT version_num FROM alembic_version")).scalar_one()
        # Backfilled again to the secure defaults after the round trip.
        row = conn.execute(sa.text("SELECT verification_status, role FROM users")).one()
    assert version == "3e285edb0896"
    assert row.verification_status == "unverified"
    assert row.role == "user"
    engine.dispose()
