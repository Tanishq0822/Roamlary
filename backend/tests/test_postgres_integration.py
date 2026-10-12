"""PostgreSQL integration tests - run ONLY against a real, DISPOSABLE
development database.

How this works (plain language): these tests are SKIPPED unless the
environment variable ROAMLARY_TEST_DATABASE_URL points to a dedicated
test database (for example roamlary_test in the local Docker
container). They then verify what SQLite cannot: native UUID columns,
real CHECK-constraint enforcement, timezone-aware timestamps, and
relationships - all on PostgreSQL itself.

They intentionally CREATE and DROP tables, so NEVER point them at a
database containing data you care about.
"""

import os
import subprocess
import sys
import uuid
from datetime import datetime
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

import app.models  # noqa: F401  (registers all tables)
from app.db.base_class import Base
from app.models import TrustedContact, User
from app.models.enums import CheckInStatus
from tests.conftest import insert_raw_user_and_checkin, insert_raw_user_and_sos

PG_TEST_URL = os.environ.get("ROAMLARY_TEST_DATABASE_URL")
BACKEND_DIR = Path(__file__).resolve().parents[1]

pytestmark = pytest.mark.skipif(
    not PG_TEST_URL,
    reason="PostgreSQL test database not provided (ROAMLARY_TEST_DATABASE_URL unset)",
)


@pytest.fixture()
def pg_engine():
    """Disposable PostgreSQL engine: schema created and dropped per test."""
    engine = sa.create_engine(PG_TEST_URL)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture()
def pg_session(pg_engine):
    factory = sessionmaker(bind=pg_engine, autoflush=False, expire_on_commit=False)
    session = factory()
    try:
        yield session
    finally:
        session.close()


def test_id_column_is_native_uuid_type(pg_engine) -> None:
    """users.id is a real PostgreSQL `uuid` column (not text)."""
    with pg_engine.connect() as connection:
        data_type = connection.execute(
            sa.text(
                "SELECT data_type FROM information_schema.columns "
                "WHERE table_name = 'users' AND column_name = 'id'"
            )
        ).scalar()
    assert data_type == "uuid"


def test_user_and_contact_round_trip(pg_session: Session) -> None:
    """Insert + read with relationships on PostgreSQL."""
    user = User(display_name="PG Asha", email="pg-asha@example.com")
    pg_session.add(TrustedContact(name="Mom", phone="+911234567890", owner=user))
    pg_session.commit()

    saved = pg_session.query(User).one()
    assert saved.id is not None and isinstance(saved.id, uuid.UUID)
    assert saved.trusted_contacts[0].name == "Mom"
    assert isinstance(saved.created_at, datetime)
    # Timezone-aware timestamps survive the PostgreSQL round trip.
    assert saved.created_at.tzinfo is not None


def test_check_constraint_rejects_invalid_status(pg_engine) -> None:
    """A raw SQL insert with a bad status fails at the database level."""
    with pg_engine.begin() as connection:
        new_id = uuid.uuid4()
        connection.execute(
            sa.text(
                "INSERT INTO users (id, display_name, created_at, updated_at) "
                "VALUES (:id, 'X', now(), now())"
            ),
            {"id": new_id},
        )
        with pytest.raises(IntegrityError):
            connection.execute(
                sa.text(
                    "INSERT INTO check_ins (id, user_id, status, created_at, updated_at) "
                    "VALUES (:cid, :uid, 'bogus-status', now(), now())"
                ),
                {"cid": uuid.uuid4(), "uid": new_id},
            )


def test_check_constraint_allows_valid_status(pg_engine) -> None:
    """The documented status values are accepted by PostgreSQL."""
    with pg_engine.begin() as connection:
        user_id = uuid.uuid4()
        connection.execute(
            sa.text(
                "INSERT INTO users (id, display_name, created_at, updated_at) "
                "VALUES (:id, 'X', now(), now())"
            ),
            {"id": user_id},
        )
        connection.execute(
            sa.text(
                "INSERT INTO check_ins (id, user_id, status, created_at, updated_at) "
                "VALUES (:cid, :uid, :status, now(), now())"
            ),
            {"cid": uuid.uuid4(), "uid": user_id, "status": CheckInStatus.SAFE},
        )


def test_password_hash_column_exists_and_is_nullable(pg_engine) -> None:
    """users.password_hash exists on real PostgreSQL and accepts NULL.

    NULL must be allowed so a future Firebase-only account (no local
    password) can still be stored as a row.
    """
    with pg_engine.connect() as connection:
        row = connection.execute(
            sa.text(
                "SELECT is_nullable FROM information_schema.columns "
                "WHERE table_name = 'users' AND column_name = 'password_hash'"
            )
        ).fetchone()
    assert row is not None, "password_hash column missing from users table"
    assert row[0] == "YES"


def test_password_hash_stores_argon2id_hash(pg_engine) -> None:
    """A real Argon2id hash round-trips through PostgreSQL."""
    from app.core.security import hash_password, verify_password

    stored = hash_password("s3cure-Pass!")
    user = User(
        display_name="PG Auth",
        email="pg-auth@example.com",
        password_hash=stored,
    )
    with pg_engine.begin() as connection:
        connection.execute(
            sa.text(
                "INSERT INTO users (id, display_name, email, password_hash, "
                "created_at, updated_at) VALUES (:id, :name, :email, :ph, now(), now())"
            ),
            {"id": uuid.uuid4(), "name": user.display_name, "email": user.email, "ph": stored},
        )
        saved_hash = connection.execute(
            sa.text("SELECT password_hash FROM users WHERE email = :email"),
            {"email": user.email},
        ).scalar()
    assert saved_hash.startswith("$argon2id$")
    assert verify_password("s3cure-Pass!", saved_hash) is True
    assert verify_password("wrong", saved_hash) is False


def test_firebase_only_account_allows_null_password(pg_engine) -> None:
    """A row with firebase_uid and NO local password is storable."""
    with pg_engine.begin() as connection:
        connection.execute(
            sa.text(
                "INSERT INTO users (id, display_name, firebase_uid, password_hash, "
                "created_at, updated_at) "
                "VALUES (:id, 'FB User', :uid, NULL, now(), now())"
            ),
            {"id": uuid.uuid4(), "uid": f"fb-{uuid.uuid4()}"},
        )
        count = connection.execute(
            sa.text("SELECT count(*) FROM users WHERE password_hash IS NULL")
        ).scalar()
    assert count == 1


# --------------------------------------------------- Phase 4 schema checks


def test_phase4_columns_exist_and_are_nullable(pg_engine) -> None:
    """trusted_contacts.relationship and check_ins.note exist on real
    PostgreSQL and accept NULL (both are optional fields)."""
    with pg_engine.connect() as connection:
        rows = connection.execute(
            sa.text(
                "SELECT table_name, column_name, is_nullable "
                "FROM information_schema.columns "
                "WHERE (table_name = 'trusted_contacts' AND column_name = 'relationship') "
                "   OR (table_name = 'check_ins' AND column_name = 'note')"
            )
        ).fetchall()
    found = {(r[0], r[1]): r[2] for r in rows}
    assert found.get(("trusted_contacts", "relationship")) == "YES"
    assert found.get(("check_ins", "note")) == "YES"


def test_phase4_relationship_and_note_round_trip(pg_engine) -> None:
    """The new columns store and return values (and empty stays NULL)."""
    with pg_engine.begin() as connection:
        user_id = uuid.uuid4()
        connection.execute(
            sa.text(
                "INSERT INTO users (id, display_name, created_at, updated_at) "
                "VALUES (:id, 'X', now(), now())"
            ),
            {"id": user_id},
        )
        connection.execute(
            sa.text(
                "INSERT INTO trusted_contacts "
                "(id, user_id, name, phone, relationship, created_at, updated_at) "
                "VALUES (:cid, :uid, 'Mom', '+911234567890', 'mother', now(), now())"
            ),
            {"cid": uuid.uuid4(), "uid": user_id},
        )
        relationship = connection.execute(
            sa.text("SELECT relationship FROM trusted_contacts WHERE user_id = :uid"),
            {"uid": user_id},
        ).scalar()
        connection.execute(
            sa.text(
                "INSERT INTO check_ins "
                "(id, user_id, status, note, created_at, updated_at) "
                "VALUES (:cid, :uid, 'pending', 'north trail', now(), now())"
            ),
            {"cid": uuid.uuid4(), "uid": user_id},
        )
        note = connection.execute(
            sa.text("SELECT note FROM check_ins WHERE user_id = :uid"),
            {"uid": user_id},
        ).scalar()
    assert relationship == "mother"
    assert note == "north trail"


def test_phase4_cancelled_status_allowed_by_check_constraint(pg_engine) -> None:
    """The relaxed CHECK constraint accepts 'cancelled' on PostgreSQL."""
    with pg_engine.begin() as connection:
        user_id = uuid.uuid4()
        connection.execute(
            sa.text(
                "INSERT INTO users (id, display_name, created_at, updated_at) "
                "VALUES (:id, 'X', now(), now())"
            ),
            {"id": user_id},
        )
        connection.execute(
            sa.text(
                "INSERT INTO check_ins (id, user_id, status, created_at, updated_at) "
                "VALUES (:cid, :uid, 'cancelled', now(), now())"
            ),
            {"cid": uuid.uuid4(), "uid": user_id},
        )
        status_value = connection.execute(
            sa.text("SELECT status FROM check_ins WHERE user_id = :uid"),
            {"uid": user_id},
        ).scalar()
    assert status_value == "cancelled"


# --------------------------------- Phase 4 migration downgrade safety (PG)
# These run alembic itself against the DISPOSABLE roamlary_test database,
# proving the data-dependent downgrade guard on a real PostgreSQL server.
#
# The Phase 4 tests below upgrade to the Phase 4 revision explicitly
# (not `head`): `head` moved to Phase 5 in 0dd8995649b4, and those tests
# are about the PHASE 4 migration's behaviour.


def _run_alembic_on_pg(args: list[str]) -> subprocess.CompletedProcess:
    """Run an alembic command against the disposable PG test database.

    DATABASE_URL is provided via the environment (its value is never
    printed), exercising the same configuration path alembic/env.py uses
    in production.
    """
    env = {**os.environ, "DATABASE_URL": PG_TEST_URL}
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
    )


def _reset_for_alembic(engine) -> None:
    """Give alembic an empty database it owns completely.

    Every other test in this file builds the schema from the ORM models
    (Base.metadata.create_all), which alembic cannot use: alembic must
    create every table itself, from the migration files. alembic_version
    is not part of the models' metadata, so it is dropped explicitly too.
    """
    Base.metadata.drop_all(engine)
    with engine.begin() as conn:
        conn.execute(sa.text("DROP TABLE IF EXISTS alembic_version"))


def test_pg_phase4_downgrade_refuses_when_cancelled_checkins_exist(pg_engine) -> None:
    """Data-dependent downgrade on REAL PostgreSQL: a 'cancelled' row must
    make the Phase 4 downgrade REFUSE, and the refusal must change nothing
    (schema, constraint, and the record itself stay exactly as they were).
    """
    _reset_for_alembic(pg_engine)
    upgrade = _run_alembic_on_pg(["upgrade", "ccd362671e07"])
    assert upgrade.returncode == 0, f"stdout={upgrade.stdout}\nstderr={upgrade.stderr}"

    insert_raw_user_and_checkin(pg_engine, "cancelled")

    downgrade = _run_alembic_on_pg(["downgrade", "d9841015aec7"])
    assert downgrade.returncode != 0, (
        "downgrade must be REFUSED while cancelled check-ins exist, "
        f"but it succeeded:\n{downgrade.stdout}\n{downgrade.stderr}"
    )
    output = downgrade.stdout + downgrade.stderr
    assert "Refusing to downgrade" in output
    assert "data-handling decision" in output

    inspector = sa.inspect(pg_engine)
    assert "note" in {c["name"] for c in inspector.get_columns("check_ins")}
    assert "relationship" in {c["name"] for c in inspector.get_columns("trusted_contacts")}
    with pg_engine.connect() as conn:
        version = conn.execute(sa.text("SELECT version_num FROM alembic_version")).scalar_one()
        status = conn.execute(sa.text("SELECT status FROM check_ins")).scalar_one()
        constraint = conn.execute(
            sa.text(
                "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
                "WHERE conname = 'ck_check_ins_status_valid'"
            )
        ).scalar_one()
    assert version == "ccd362671e07"  # still at the Phase 4 revision
    assert status == "cancelled"  # the record itself is untouched
    assert "'cancelled'" in constraint  # 5-value constraint still active


def test_pg_phase4_downgrade_upgrade_roundtrip_without_cancelled_records(
    pg_engine,
) -> None:
    """Normal path on REAL PostgreSQL: with no cancelled rows the downgrade
    succeeds, and upgrading again restores the exact Phase 4 schema."""
    _reset_for_alembic(pg_engine)
    upgrade = _run_alembic_on_pg(["upgrade", "ccd362671e07"])
    assert upgrade.returncode == 0, f"stdout={upgrade.stdout}\nstderr={upgrade.stderr}"

    insert_raw_user_and_checkin(pg_engine, "pending", note="roundtrip probe")

    downgrade = _run_alembic_on_pg(["downgrade", "d9841015aec7"])
    assert downgrade.returncode == 0, f"stdout={downgrade.stdout}\nstderr={downgrade.stderr}"
    inspector = sa.inspect(pg_engine)
    assert "note" not in {c["name"] for c in inspector.get_columns("check_ins")}
    assert "relationship" not in {c["name"] for c in inspector.get_columns("trusted_contacts")}
    with pg_engine.connect() as conn:
        version = conn.execute(sa.text("SELECT version_num FROM alembic_version")).scalar_one()
        status = conn.execute(sa.text("SELECT status FROM check_ins")).scalar_one()
    assert version == "d9841015aec7"
    assert status == "pending"  # the record itself survives the schema revert

    upgrade_again = _run_alembic_on_pg(["upgrade", "ccd362671e07"])
    assert upgrade_again.returncode == 0, (
        f"stdout={upgrade_again.stdout}\nstderr={upgrade_again.stderr}"
    )
    inspector = sa.inspect(pg_engine)
    assert "note" in {c["name"] for c in inspector.get_columns("check_ins")}
    assert "relationship" in {c["name"] for c in inspector.get_columns("trusted_contacts")}
    with pg_engine.connect() as conn:
        version = conn.execute(sa.text("SELECT version_num FROM alembic_version")).scalar_one()
        row = conn.execute(sa.text("SELECT status, note FROM check_ins")).one()
        constraint = conn.execute(
            sa.text(
                "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
                "WHERE conname = 'ck_check_ins_status_valid'"
            )
        ).scalar_one()
    assert version == "ccd362671e07"
    assert row.status == "pending"
    # The note column was dropped and re-created EMPTY: a downgrade reverts
    # the Phase 4 feature itself (documented behaviour), while the ROW and
    # its status survive.
    assert row.note is None
    assert "'cancelled'" in constraint  # 5-value constraint restored


# ------------------------------------------- Phase 5 SOS schema checks (PG)


def test_phase5_sos_columns_exist_and_are_nullable(pg_engine) -> None:
    """The three Phase 5 columns exist on real PostgreSQL and accept NULL
    (description, location timestamp, and cancellation timestamp are all
    optional)."""
    with pg_engine.connect() as connection:
        rows = connection.execute(
            sa.text(
                "SELECT column_name, is_nullable FROM information_schema.columns "
                "WHERE table_name = 'sos_events' AND column_name IN "
                "('description', 'location_recorded_at', 'cancelled_at')"
            )
        ).fetchall()
    found = {r[0]: r[1] for r in rows}
    assert found == {
        "description": "YES",
        "location_recorded_at": "YES",
        "cancelled_at": "YES",
    }


def test_phase5_cancelled_status_allowed_by_check_constraint(pg_engine) -> None:
    """The relaxed CHECK constraint accepts 'cancelled' on PostgreSQL."""
    with pg_engine.begin() as connection:
        user_id = uuid.uuid4()
        connection.execute(
            sa.text(
                "INSERT INTO users (id, display_name, created_at, updated_at) "
                "VALUES (:id, 'X', now(), now())"
            ),
            {"id": user_id},
        )
        connection.execute(
            sa.text(
                "INSERT INTO sos_events (id, user_id, status, created_at, updated_at) "
                "VALUES (:sid, :uid, 'cancelled', now(), now())"
            ),
            {"sid": uuid.uuid4(), "uid": user_id},
        )
        status_value = connection.execute(
            sa.text("SELECT status FROM sos_events WHERE user_id = :uid"),
            {"uid": user_id},
        ).scalar()
    assert status_value == "cancelled"


def test_pg_phase5_downgrade_refuses_when_cancelled_sos_exist(pg_engine) -> None:
    """Data-dependent downgrade on REAL PostgreSQL: a 'cancelled' SOS
    incident must make the Phase 5 downgrade REFUSE, and the refusal must
    change nothing (schema, constraint, and the record itself stay as they
    were)."""
    _reset_for_alembic(pg_engine)
    upgrade = _run_alembic_on_pg(["upgrade", "0dd8995649b4"])
    assert upgrade.returncode == 0, f"stdout={upgrade.stdout}\nstderr={upgrade.stderr}"

    insert_raw_user_and_sos(pg_engine, "cancelled")

    downgrade = _run_alembic_on_pg(["downgrade", "ccd362671e07"])
    assert downgrade.returncode != 0, (
        "downgrade must be REFUSED while cancelled SOS incidents exist, "
        f"but it succeeded:\n{downgrade.stdout}\n{downgrade.stderr}"
    )
    output = downgrade.stdout + downgrade.stderr
    assert "Refusing to downgrade" in output
    assert "data-handling decision" in output

    inspector = sa.inspect(pg_engine)
    assert {"description", "location_recorded_at", "cancelled_at"} <= {
        c["name"] for c in inspector.get_columns("sos_events")
    }
    with pg_engine.connect() as conn:
        version = conn.execute(sa.text("SELECT version_num FROM alembic_version")).scalar_one()
        status_value = conn.execute(sa.text("SELECT status FROM sos_events")).scalar_one()
        constraint = conn.execute(
            sa.text(
                "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
                "WHERE conname = 'ck_sos_events_status_valid'"
            )
        ).scalar_one()
    assert version == "0dd8995649b4"  # still at the Phase 5 revision
    assert status_value == "cancelled"  # the record itself is untouched
    assert "'cancelled'" in constraint  # 5-value constraint still active


def test_pg_phase5_downgrade_upgrade_roundtrip_without_cancelled_sos(pg_engine) -> None:
    """Normal path on REAL PostgreSQL: no cancelled SOS incidents ->
    downgrade succeeds; upgrading again restores the exact Phase 5 schema."""
    _reset_for_alembic(pg_engine)
    upgrade = _run_alembic_on_pg(["upgrade", "0dd8995649b4"])
    assert upgrade.returncode == 0, f"stdout={upgrade.stdout}\nstderr={upgrade.stderr}"

    insert_raw_user_and_sos(pg_engine, "active", description="roundtrip probe")

    downgrade = _run_alembic_on_pg(["downgrade", "ccd362671e07"])
    assert downgrade.returncode == 0, f"stdout={downgrade.stdout}\nstderr={downgrade.stderr}"
    inspector = sa.inspect(pg_engine)
    assert "description" not in {c["name"] for c in inspector.get_columns("sos_events")}
    with pg_engine.connect() as conn:
        version = conn.execute(sa.text("SELECT version_num FROM alembic_version")).scalar_one()
        status_value = conn.execute(sa.text("SELECT status FROM sos_events")).scalar_one()
    assert version == "ccd362671e07"
    assert status_value == "active"  # the record itself survives the schema revert

    upgrade_again = _run_alembic_on_pg(["upgrade", "0dd8995649b4"])
    assert upgrade_again.returncode == 0, (
        f"stdout={upgrade_again.stdout}\nstderr={upgrade_again.stderr}"
    )
    inspector = sa.inspect(pg_engine)
    assert {"description", "location_recorded_at", "cancelled_at"} <= {
        c["name"] for c in inspector.get_columns("sos_events")
    }
    with pg_engine.connect() as conn:
        version = conn.execute(sa.text("SELECT version_num FROM alembic_version")).scalar_one()
        row = conn.execute(sa.text("SELECT status, description FROM sos_events")).one()
        constraint = conn.execute(
            sa.text(
                "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
                "WHERE conname = 'ck_sos_events_status_valid'"
            )
        ).scalar_one()
    assert version == "0dd8995649b4"
    assert row.status == "active"
    # The description column was dropped and re-created EMPTY (documented
    # downgrade behaviour); the ROW and its status survive.
    assert row.description is None
    assert "'cancelled'" in constraint  # 5-value constraint restored
