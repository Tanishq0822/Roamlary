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
import uuid
from datetime import datetime

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

import app.models  # noqa: F401  (registers all tables)
from app.db.base_class import Base
from app.models import TrustedContact, User
from app.models.enums import CheckInStatus

PG_TEST_URL = os.environ.get("ROAMLARY_TEST_DATABASE_URL")

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
