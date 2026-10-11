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

BACKEND_DIR = Path(__file__).resolve().parents[1]
EXPECTED_TABLES = {"users", "trusted_contacts", "check_ins", "sos_events", "community_reports"}


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
