"""Shared pytest fixtures.

Two independent test layers live here:
1. `client` - FastAPI TestClient (no database, no network).
2. `sqlite_engine` / `db_session` - in-memory SQLite used for fast,
   offline model & CRUD-style tests.

Honesty note (documented in report.md): SQLite tests prove MODEL
BEHAVIOUR, not PostgreSQL compatibility. PostgreSQL-specific checks run
in tests/test_postgres_integration.py against a real disposable
database and are skipped when none is provided.
"""

import uuid

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.db.base_class import Base
from app.db.session import get_db
from app.main import app

# Fixed TEST-ONLY JWT secret. Every test signs and verifies with this value
# instead of whatever is in the developer's real .env, so the suite is
# hermetic (same results on any machine) and no real secret is ever needed
# or exercised by tests. The fail-closed tests override it to "" on purpose.
TEST_JWT_SECRET = "unit-test-only-secret-0123456789abcdefghijklmnop"


@pytest.fixture(autouse=True)
def _hermetic_jwt_secret(monkeypatch):
    """Confine test secrets to test configuration (never the real .env)."""
    monkeypatch.setattr(settings, "jwt_secret_key", TEST_JWT_SECRET)


@pytest.fixture()
def client() -> TestClient:
    """FastAPI TestClient bound to the application under test."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def sqlite_engine():
    """In-memory SQLite engine with all Phase 2 tables created."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # SQLite disables foreign keys by default; turn them ON so the
    # ON DELETE RESTRICT behaviour can actually be tested.
    @event.listens_for(engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture()
def db_session(sqlite_engine):
    """One short-lived, always-closed database session per test."""
    testing_session_factory = sessionmaker(
        bind=sqlite_engine, autoflush=False, expire_on_commit=False
    )
    session = testing_session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def api_client(sqlite_engine):
    """Authenticated-API test client wired to the SQLite test database.

    Overrides get_db so every request uses the in-memory database, and
    clears any stale dependency overrides on entry and exit. Used by the
    Phase 4 trusted-contact and check-in tests, which drive the real
    FastAPI app end-to-end (register -> token -> authenticated call).
    """

    def override_get_db():
        TestSession = sessionmaker(bind=sqlite_engine, autoflush=False, expire_on_commit=False)
        session = TestSession()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides.clear()
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def register_user(client, email, password="s3cure-Pass!", display_name="Tester"):
    """Register a user and return (user_id, bearer_headers).

    Convenience helper for tests that need one or more distinct accounts
    to prove ownership isolation.
    """
    resp = client.post(
        "/api/v1/auth/register",
        json={"display_name": display_name, "email": email, "password": password},
    )
    assert resp.status_code == 201, resp.text
    token = resp.json()["access_token"]
    me = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"}).json()
    return me["id"], {"Authorization": f"Bearer {token}"}


def insert_raw_user_and_checkin(engine, status: str, note: str | None = None) -> None:
    """Insert one user + one check-in with RAW SQL, bypassing the ORM.

    Migration tests need rows that already sit in the database no matter
    who wrote them (app, script, or manual SQL) - exactly the situation a
    migration downgrade faces. CURRENT_TIMESTAMP is valid on both SQLite
    and PostgreSQL. PostgreSQL binds native uuid.UUID objects (its driver
    resolves them to the uuid column); SQLite's driver cannot adapt UUID
    objects, so it gets the canonical string form. Both rows use the
    'Migration Probe' display name so operators can spot them.
    """
    if engine.dialect.name == "postgresql":
        user_id, checkin_id = uuid.uuid4(), uuid.uuid4()
    else:
        user_id, checkin_id = str(uuid.uuid4()), str(uuid.uuid4())
    with engine.begin() as conn:
        conn.execute(
            sa.text(
                "INSERT INTO users (id, display_name, created_at, updated_at) "
                "VALUES (:id, 'Migration Probe', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ),
            {"id": user_id},
        )
        conn.execute(
            sa.text(
                "INSERT INTO check_ins "
                "(id, user_id, status, note, created_at, updated_at) "
                "VALUES (:id, :user_id, :status, :note, "
                "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ),
            {"id": checkin_id, "user_id": user_id, "status": status, "note": note},
        )


def insert_raw_user_and_sos(engine, status: str, description: str | None = None) -> None:
    """Insert one user + one SOS incident with RAW SQL, bypassing the ORM.

    Same purpose as insert_raw_user_and_checkin: migration tests need
    rows that already sit in the database no matter who wrote them -
    exactly the situation a migration downgrade faces.
    """
    if engine.dialect.name == "postgresql":
        user_id, sos_id = uuid.uuid4(), uuid.uuid4()
    else:
        user_id, sos_id = str(uuid.uuid4()), str(uuid.uuid4())
    with engine.begin() as conn:
        conn.execute(
            sa.text(
                "INSERT INTO users (id, display_name, created_at, updated_at) "
                "VALUES (:id, 'Migration Probe', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ),
            {"id": user_id},
        )
        conn.execute(
            sa.text(
                "INSERT INTO sos_events "
                "(id, user_id, status, description, created_at, updated_at) "
                "VALUES (:id, :user_id, :status, :description, "
                "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ),
            {"id": sos_id, "user_id": user_id, "status": status, "description": description},
        )


def insert_raw_user_and_report(
    engine, category: str, status: str = "pending", description: str = "Migration probe"
) -> None:
    """Insert one user + one community report with RAW SQL, bypassing the ORM.

    Same purpose as the other raw helpers: migration tests need rows
    that already sit in the database no matter who wrote them - exactly
    the situation an Alembic upgrade/downgrade guard faces. The
    `category` is a plain string on purpose, so tests can insert values
    the Phase 6 CHECK constraint would reject.
    """
    if engine.dialect.name == "postgresql":
        user_id, report_id = uuid.uuid4(), uuid.uuid4()
    else:
        user_id, report_id = str(uuid.uuid4()), str(uuid.uuid4())
    with engine.begin() as conn:
        conn.execute(
            sa.text(
                "INSERT INTO users (id, display_name, created_at, updated_at) "
                "VALUES (:id, 'Migration Probe', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ),
            {"id": user_id},
        )
        conn.execute(
            sa.text(
                "INSERT INTO community_reports "
                "(id, user_id, category, description, status, created_at, updated_at) "
                "VALUES (:id, :user_id, :category, :description, :status, "
                "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ),
            {
                "id": report_id,
                "user_id": user_id,
                "category": category,
                "description": description,
                "status": status,
            },
        )
