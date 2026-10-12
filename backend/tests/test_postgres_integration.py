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
from app.models import TravelPlan, TravelProfile, TrustedContact, User
from app.models.enums import CheckInStatus
from tests.conftest import (
    insert_raw_user_and_checkin,
    insert_raw_user_and_report,
    insert_raw_user_and_sos,
    insert_raw_user_and_travel,
    insert_raw_user_and_verification,
)

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


# -------------------------------- Phase 6 category constraint checks (PG)


def test_phase6_category_constraint_enforced_on_pg(pg_engine) -> None:
    """The Phase 6 CHECK (created by migration ab32047c8481) accepts
    in-set categories and rejects anything else on REAL PostgreSQL."""
    _reset_for_alembic(pg_engine)
    upgrade = _run_alembic_on_pg(["upgrade", "ab32047c8481"])
    assert upgrade.returncode == 0, f"stdout={upgrade.stdout}\nstderr={upgrade.stderr}"

    insert_raw_user_and_report(pg_engine, "poor_lighting")  # in-set: accepted
    with pg_engine.connect() as connection:
        category = connection.execute(
            sa.text("SELECT category FROM community_reports")
        ).scalar_one()
    assert category == "poor_lighting"

    with pytest.raises(IntegrityError):
        insert_raw_user_and_report(pg_engine, "theft")  # out-of-set: rejected


def test_pg_phase6_upgrade_refuses_when_unknown_categories_exist(pg_engine) -> None:
    """Data-dependent upgrade on REAL PostgreSQL: a pre-Phase-6 category
    must make the upgrade REFUSE, leaving schema and record untouched."""
    _reset_for_alembic(pg_engine)
    upgrade = _run_alembic_on_pg(["upgrade", "0dd8995649b4"])
    assert upgrade.returncode == 0, f"stdout={upgrade.stdout}\nstderr={upgrade.stderr}"

    insert_raw_user_and_report(pg_engine, "theft")  # pre-Phase-6: any string allowed

    upgrade_again = _run_alembic_on_pg(["upgrade", "ab32047c8481"])
    assert upgrade_again.returncode != 0, (
        "upgrade must be REFUSED while unknown categories exist, "
        f"but it succeeded:\n{upgrade_again.stdout}\n{upgrade_again.stderr}"
    )
    output = upgrade_again.stdout + upgrade_again.stderr
    assert "Refusing to upgrade" in output
    assert "data-handling decision" in output

    inspector = sa.inspect(pg_engine)
    names = {c["name"] for c in inspector.get_check_constraints("community_reports")}
    assert "ck_community_reports_category_valid" not in names
    with pg_engine.connect() as conn:
        version = conn.execute(sa.text("SELECT version_num FROM alembic_version")).scalar_one()
        category = conn.execute(sa.text("SELECT category FROM community_reports")).scalar_one()
    assert version == "0dd8995649b4"  # unchanged
    assert category == "theft"  # the record itself is untouched


def test_pg_phase6_downgrade_upgrade_roundtrip(pg_engine) -> None:
    """Normal path on REAL PostgreSQL: downgrade drops the constraint
    without touching stored data; upgrading again restores it."""
    _reset_for_alembic(pg_engine)
    upgrade = _run_alembic_on_pg(["upgrade", "ab32047c8481"])
    assert upgrade.returncode == 0, f"stdout={upgrade.stdout}\nstderr={upgrade.stderr}"

    insert_raw_user_and_report(pg_engine, "unsafe_area")

    downgrade = _run_alembic_on_pg(["downgrade", "0dd8995649b4"])
    assert downgrade.returncode == 0, f"stdout={downgrade.stdout}\nstderr={downgrade.stderr}"
    with pg_engine.connect() as conn:
        constraint_count = conn.execute(
            sa.text(
                "SELECT count(*) FROM pg_constraint "
                "WHERE conname = 'ck_community_reports_category_valid'"
            )
        ).scalar_one()
        version = conn.execute(sa.text("SELECT version_num FROM alembic_version")).scalar_one()
        category = conn.execute(sa.text("SELECT category FROM community_reports")).scalar_one()
    assert constraint_count == 0  # constraint dropped
    assert version == "0dd8995649b4"
    assert category == "unsafe_area"  # stored value survives

    upgrade_again = _run_alembic_on_pg(["upgrade", "ab32047c8481"])
    assert upgrade_again.returncode == 0, (
        f"stdout={upgrade_again.stdout}\nstderr={upgrade_again.stderr}"
    )
    with pg_engine.connect() as conn:
        constraint_count = conn.execute(
            sa.text(
                "SELECT count(*) FROM pg_constraint "
                "WHERE conname = 'ck_community_reports_category_valid'"
            )
        ).scalar_one()
        version = conn.execute(sa.text("SELECT version_num FROM alembic_version")).scalar_one()
        category = conn.execute(sa.text("SELECT category FROM community_reports")).scalar_one()
    assert constraint_count == 1  # constraint restored
    assert version == "ab32047c8481"
    assert category == "unsafe_area"


# ---------------------- Phase 6b verification foundation checks (PG)


def _insert_plain_user(
    connection, verification_status: str = "unverified", role: str = "user"
) -> uuid.UUID:
    """Insert one user row and return its id (raw SQL, caller-committed).

    The Phase 6b columns are always provided explicitly so this works on
    BOTH schemas the tests build: the ORM-created one (Python-side
    defaults only) and the Alembic-created one (database defaults).
    """
    user_id = uuid.uuid4()
    connection.execute(
        sa.text(
            "INSERT INTO users (id, display_name, verification_status, role, "
            "created_at, updated_at) "
            "VALUES (:id, 'X', :vstatus, :role, now(), now())"
        ),
        {"id": user_id, "vstatus": verification_status, "role": role},
    )
    return user_id


def test_phase6b_check_constraints_enforced_on_pg(pg_engine) -> None:
    """The Phase 6b CHECK constraints reject bad values written by RAW SQL
    on REAL PostgreSQL - the second validation layer behind the enums."""
    # Bad account verification status -> rejected.
    with pg_engine.begin() as connection:
        _insert_plain_user(connection)
        with pytest.raises(IntegrityError):
            connection.execute(
                sa.text(
                    "UPDATE users SET verification_status = 'super-verified' "
                    "WHERE display_name = 'X'"
                )
            )
    # Bad role -> rejected (no privilege escalation via raw SQL).
    with pg_engine.begin() as connection:
        _insert_plain_user(connection)
        with pytest.raises(IntegrityError):
            connection.execute(sa.text("UPDATE users SET role = 'admin' WHERE display_name = 'X'"))
    # Bad request status -> rejected.
    with pg_engine.begin() as connection:
        user_id = _insert_plain_user(connection)
        with pytest.raises(IntegrityError):
            connection.execute(
                sa.text(
                    "INSERT INTO identity_verifications "
                    "(id, user_id, status, created_at, updated_at) "
                    "VALUES (:rid, :uid, 'maybe', now(), now())"
                ),
                {"rid": uuid.uuid4(), "uid": user_id},
            )
    # All documented values -> accepted.
    with pg_engine.begin() as connection:
        user_id = _insert_plain_user(connection, verification_status="verified", role="owner")
        connection.execute(
            sa.text(
                "INSERT INTO identity_verifications "
                "(id, user_id, status, created_at, updated_at) "
                "VALUES (:rid, :uid, 'approved', now(), now())"
            ),
            {"rid": uuid.uuid4(), "uid": user_id},
        )
        row = connection.execute(sa.text("SELECT verification_status, role FROM users")).one()
    assert row.verification_status == "verified"
    assert row.role == "owner"


def test_phase6b_defaults_on_new_accounts(pg_session: Session) -> None:
    """An account created through the ORM (the path registration uses)
    starts unverified + user - never verified, never privileged."""
    from app.models.enums import UserRole, VerificationStatus

    user = User(display_name="PG Default", email="pg-default@example.com")
    pg_session.add(user)
    pg_session.commit()
    assert user.verification_status == VerificationStatus.UNVERIFIED
    assert user.role == UserRole.USER


def test_pg_phase6b_upgrade_backfills_existing_users(pg_engine) -> None:
    """A user created BEFORE the Phase 6b revision comes out of the
    upgrade as unverified + user on REAL PostgreSQL (server default fills
    every existing row; nobody is silently promoted)."""
    _reset_for_alembic(pg_engine)
    upgrade = _run_alembic_on_pg(["upgrade", "ab32047c8481"])
    assert upgrade.returncode == 0, f"stdout={upgrade.stdout}\nstderr={upgrade.stderr}"

    insert_raw_user_and_checkin(pg_engine, "pending")  # plain pre-Phase-6b user

    upgrade_again = _run_alembic_on_pg(["upgrade", "3e285edb0896"])
    assert upgrade_again.returncode == 0, (
        f"stdout={upgrade_again.stdout}\nstderr={upgrade_again.stderr}"
    )
    with pg_engine.connect() as conn:
        row = conn.execute(sa.text("SELECT verification_status, role FROM users")).one()
    assert row.verification_status == "unverified"
    assert row.role == "user"


def test_pg_phase6b_downgrade_refuses_when_verification_data_exists(pg_engine) -> None:
    """Data-dependent downgrade on REAL PostgreSQL: existing verification
    requests must make the Phase 6b downgrade REFUSE, and the refusal must
    change nothing (schema and the record stay exactly as they were)."""
    _reset_for_alembic(pg_engine)
    upgrade = _run_alembic_on_pg(["upgrade", "3e285edb0896"])
    assert upgrade.returncode == 0, f"stdout={upgrade.stdout}\nstderr={upgrade.stderr}"

    insert_raw_user_and_verification(pg_engine, request_status="pending")

    downgrade = _run_alembic_on_pg(["downgrade", "ab32047c8481"])
    assert downgrade.returncode != 0, (
        "downgrade must be REFUSED while verification requests exist, "
        f"but it succeeded:\n{downgrade.stdout}\n{downgrade.stderr}"
    )
    output = downgrade.stdout + downgrade.stderr
    assert "Refusing to downgrade" in output
    assert "data-handling decision" in output

    inspector = sa.inspect(pg_engine)
    assert "identity_verifications" in set(inspector.get_table_names())
    assert "verification_status" in {c["name"] for c in inspector.get_columns("users")}
    with pg_engine.connect() as conn:
        version = conn.execute(sa.text("SELECT version_num FROM alembic_version")).scalar_one()
        status_value = conn.execute(
            sa.text("SELECT status FROM identity_verifications")
        ).scalar_one()
        constraint = conn.execute(
            sa.text(
                "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
                "WHERE conname = 'ck_users_role_valid'"
            )
        ).scalar_one()
    assert version == "3e285edb0896"  # still at the Phase 6b revision
    assert status_value == "pending"  # the record itself is untouched
    assert "'owner'" in constraint  # role CHECK still active


def test_pg_phase6b_downgrade_upgrade_roundtrip(pg_engine) -> None:
    """Normal path on REAL PostgreSQL: clean state downgrades successfully
    (tables + columns removed, user row survives); upgrading again restores
    the exact Phase 6b schema with secure backfill."""
    _reset_for_alembic(pg_engine)
    upgrade = _run_alembic_on_pg(["upgrade", "3e285edb0896"])
    assert upgrade.returncode == 0, f"stdout={upgrade.stdout}\nstderr={upgrade.stderr}"

    insert_raw_user_and_verification(pg_engine, request_status=None)  # defaults only

    downgrade = _run_alembic_on_pg(["downgrade", "ab32047c8481"])
    assert downgrade.returncode == 0, f"stdout={downgrade.stdout}\nstderr={downgrade.stderr}"
    inspector = sa.inspect(pg_engine)
    assert "identity_verifications" not in set(inspector.get_table_names())
    user_cols = {c["name"] for c in inspector.get_columns("users")}
    assert "verification_status" not in user_cols
    assert "role" not in user_cols
    with pg_engine.connect() as conn:
        version = conn.execute(sa.text("SELECT version_num FROM alembic_version")).scalar_one()
        count = conn.execute(sa.text("SELECT count(*) FROM users")).scalar_one()
    assert version == "ab32047c8481"
    assert count == 1  # the user row itself survives

    upgrade_again = _run_alembic_on_pg(["upgrade", "3e285edb0896"])
    assert upgrade_again.returncode == 0, (
        f"stdout={upgrade_again.stdout}\nstderr={upgrade_again.stderr}"
    )
    inspector = sa.inspect(pg_engine)
    assert {"identity_verifications", "app_settings", "setting_changes"} <= set(
        inspector.get_table_names()
    )
    with pg_engine.connect() as conn:
        version = conn.execute(sa.text("SELECT version_num FROM alembic_version")).scalar_one()
        row = conn.execute(sa.text("SELECT verification_status, role FROM users")).one()
    assert version == "3e285edb0896"
    assert row.verification_status == "unverified"  # re-backfilled
    assert row.role == "user"


# ----------------------- Phase 7 travel surface on PostgreSQL


def test_phase7_travel_tables_have_native_uuid_and_restrict_fks(pg_engine) -> None:
    """The three travel tables use native uuid columns, and every FK
    (including the optional plan context) is RESTRICT."""
    with pg_engine.connect() as conn:
        uuid_cols = (
            conn.execute(
                sa.text(
                    "SELECT table_name, column_name FROM information_schema.columns "
                    "WHERE table_name IN "
                    "('travel_profiles', 'travel_plans', 'travel_partner_requests') "
                    "AND column_name = 'id' AND data_type = 'uuid'"
                )
            )
            .scalars()
            .all()
        )
        assert len(uuid_cols) == 3  # one native uuid PK per travel table
        fkr = conn.execute(
            sa.text(
                "SELECT conrelid::regclass::text, confrelid::regclass::text, "
                "confdeltype FROM pg_constraint WHERE contype = 'f' AND "
                "conrelid::regclass::text IN "
                "('travel_profiles', 'travel_plans', 'travel_partner_requests')"
            )
        ).all()
    assert fkr, "foreign keys must exist on the travel tables"
    for table, referred, on_delete in fkr:
        # pg_constraint.confdeltype is 'r'/'R' for ON DELETE RESTRICT.
        assert on_delete.upper() == "R", f"{table}->{referred} must be ON DELETE RESTRICT"


def test_phase7_partial_pending_pair_index_enforced_on_pg(pg_engine) -> None:
    """On real PostgreSQL, racing identical pending sends lose at the
    database (per direction); the cross-direction pair is guarded by the
    endpoint layer (documented boundary)."""
    with pg_engine.begin() as conn:
        a_id, b_id = uuid.uuid4(), uuid.uuid4()
        for uid in (a_id, b_id):
            conn.execute(
                sa.text(
                    "INSERT INTO users (id, display_name, created_at, updated_at) "
                    "VALUES (:id, 'PG Traveller', now(), now())"
                ),
                {"id": uid},
            )
        base = (
            "INSERT INTO travel_partner_requests "
            "(id, requester_id, recipient_id, status, created_at, updated_at) "
            "VALUES (:rid, :req, :rec, 'pending', now(), now())"
        )
        conn.execute(sa.text(base), {"rid": uuid.uuid4(), "req": a_id, "rec": b_id})
        with pytest.raises(IntegrityError):
            conn.execute(sa.text(base), {"rid": uuid.uuid4(), "req": a_id, "rec": b_id})
        conn.rollback()
    # After rollback both rows are gone; seed the mirrored direction and
    # prove ITS duplicate is rejected too.
    with pg_engine.begin() as conn:
        a_id, b_id = uuid.uuid4(), uuid.uuid4()
        for uid in (a_id, b_id):
            conn.execute(
                sa.text(
                    "INSERT INTO users (id, display_name, created_at, updated_at) "
                    "VALUES (:id, 'PG Traveller', now(), now())"
                ),
                {"id": uid},
            )
        base = (
            "INSERT INTO travel_partner_requests "
            "(id, requester_id, recipient_id, status, created_at, updated_at) "
            "VALUES (:rid, :req, :rec, 'pending', now(), now())"
        )
        conn.execute(sa.text(base), {"rid": uuid.uuid4(), "req": b_id, "rec": a_id})
        with pytest.raises(IntegrityError):
            conn.execute(sa.text(base), {"rid": uuid.uuid4(), "req": b_id, "rec": a_id})
        conn.rollback()


def test_phase7_check_constraints_enforced_on_pg(pg_engine: Session) -> None:
    """Self-requests and inverted date ranges fail at the database."""
    with pg_engine.begin() as conn:
        uid = uuid.uuid4()
        conn.execute(
            sa.text(
                "INSERT INTO users (id, display_name, created_at, updated_at) "
                "VALUES (:id, 'PG Check', now(), now())"
            ),
            {"id": uid},
        )
        with pytest.raises(IntegrityError):  # no self-request
            conn.execute(
                sa.text(
                    "INSERT INTO travel_partner_requests "
                    "(id, requester_id, recipient_id, status, created_at, updated_at) "
                    "VALUES (:rid, :uid, :uid, 'pending', now(), now())"
                ),
                {"rid": uuid.uuid4(), "uid": uid},
            )
        conn.rollback()
    with pg_engine.begin() as conn:
        uid = uuid.uuid4()
        conn.execute(
            sa.text(
                "INSERT INTO users (id, display_name, created_at, updated_at) "
                "VALUES (:id, 'PG Check', now(), now())"
            ),
            {"id": uid},
        )
        with pytest.raises(IntegrityError):  # end before start
            conn.execute(
                sa.text(
                    "INSERT INTO travel_plans "
                    "(id, user_id, destination, destination_normalized, start_date, "
                    "end_date, created_at, updated_at) "
                    "VALUES (:pid, :uid, 'Goa', 'goa', '2026-12-10', '2026-12-01', "
                    "now(), now())"
                ),
                {"pid": uuid.uuid4(), "uid": uid},
            )
        conn.rollback()


def test_phase7_json_list_columns_round_trip_on_pg(pg_session: Session) -> None:
    """The generic JSON preference lists store and return real arrays."""
    user = User(display_name="PG Nomad", email="pg-nomad@example.com")
    pg_session.add(user)
    pg_session.flush()
    pg_session.add(
        TravelProfile(
            user_id=user.id,
            travel_nickname="Nomad",
            languages=["english", "hindi"],
            travel_styles=["slow_travel"],
            interests=["hiking", "food"],
            discoverable=True,
        )
    )
    pg_session.add(
        TravelPlan(
            user_id=user.id,
            destination="Ladakh",
            destination_normalized="ladakh",
            start_date=datetime.now().date(),
            end_date=datetime.now().date(),
            flexible_dates=True,
            status="active",
            visibility="discoverable",
        )
    )
    pg_session.commit()
    profile = pg_session.query(TravelProfile).one()
    assert profile.languages == ["english", "hindi"]
    assert profile.interests == ["hiking", "food"]
    plan = pg_session.query(TravelPlan).one()
    assert plan.destination_normalized == "ladakh"


def test_pg_phase7_downgrade_refuses_when_travel_data_exists(pg_engine) -> None:
    """DATA-DEPENDENT DOWNGRADE on real PostgreSQL: travel rows make the
    rollback REFUSE cleanly, leaving schema and records untouched."""
    _reset_for_alembic(pg_engine)
    upgrade = _run_alembic_on_pg(["upgrade", "head"])
    assert upgrade.returncode == 0, f"stdout={upgrade.stdout}\nstderr={upgrade.stderr}"

    insert_raw_user_and_travel(pg_engine)

    downgrade = _run_alembic_on_pg(["downgrade", "3e285edb0896"])
    assert downgrade.returncode != 0, (
        "downgrade must be REFUSED while travel data exists, "
        f"but it succeeded:\n{downgrade.stdout}\n{downgrade.stderr}"
    )
    output = downgrade.stdout + downgrade.stderr
    assert "Refusing to downgrade" in output
    assert "data-handling decision" in output

    inspector = sa.inspect(pg_engine)
    assert {"travel_profiles", "travel_plans", "travel_partner_requests"} <= set(
        inspector.get_table_names()
    )
    with pg_engine.connect() as conn:
        version = conn.execute(sa.text("SELECT version_num FROM alembic_version")).scalar_one()
        destination = conn.execute(sa.text("SELECT destination FROM travel_plans")).scalar_one()
    assert version == "426dcef31e27"
    assert destination == "Goa"


def test_pg_phase7_downgrade_upgrade_roundtrip(pg_engine) -> None:
    """Normal path on REAL PostgreSQL: clean state downgrades (tables
    removed); upgrading again restores the exact Phase 7 schema."""
    _reset_for_alembic(pg_engine)
    upgrade = _run_alembic_on_pg(["upgrade", "head"])
    assert upgrade.returncode == 0, f"stdout={upgrade.stdout}\nstderr={upgrade.stderr}"

    insert_raw_user_and_checkin(pg_engine, "pending")  # non-travel row survives

    downgrade = _run_alembic_on_pg(["downgrade", "3e285edb0896"])
    assert downgrade.returncode == 0, f"stdout={downgrade.stdout}\nstderr={downgrade.stderr}"
    inspector = sa.inspect(pg_engine)
    assert "travel_plans" not in set(inspector.get_table_names())
    with pg_engine.connect() as conn:
        version = conn.execute(sa.text("SELECT version_num FROM alembic_version")).scalar_one()
        count = conn.execute(sa.text("SELECT count(*) FROM users")).scalar_one()
    assert version == "3e285edb0896"
    assert count == 1  # the user row itself survives

    upgrade_again = _run_alembic_on_pg(["upgrade", "head"])
    assert upgrade_again.returncode == 0, (
        f"stdout={upgrade_again.stdout}\nstderr={upgrade_again.stderr}"
    )
    inspector = sa.inspect(pg_engine)
    assert {"travel_profiles", "travel_plans", "travel_partner_requests"} <= set(
        inspector.get_table_names()
    )
    with pg_engine.connect() as conn:
        version = conn.execute(sa.text("SELECT version_num FROM alembic_version")).scalar_one()
    assert version == "426dcef31e27"
