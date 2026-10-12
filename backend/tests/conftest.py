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


def insert_raw_user_and_verification(
    engine,
    request_status: str | None = "pending",
    verification_status: str = "unverified",
    role: str = "user",
) -> None:
    """Insert one user (+ optional verification request) with RAW SQL.

    Same purpose as the other raw helpers: the Phase 6b downgrade guard
    must be tested against rows no matter who wrote them. Only works on a
    schema that already has the Phase 6b columns (revision 3e285edb0896).

    - `request_status=None` inserts a user only (use `verification_status`
      or `role` to simulate non-default state for the guard).
    - `request_status="pending"` also inserts a verification request row.
    """
    if engine.dialect.name == "postgresql":
        user_id, request_id = uuid.uuid4(), uuid.uuid4()
    else:
        user_id, request_id = str(uuid.uuid4()), str(uuid.uuid4())
    with engine.begin() as conn:
        conn.execute(
            sa.text(
                "INSERT INTO users "
                "(id, display_name, verification_status, role, created_at, updated_at) "
                "VALUES (:id, 'Migration Probe', :vstatus, :role, "
                "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ),
            {"id": user_id, "vstatus": verification_status, "role": role},
        )
        if request_status is not None:
            conn.execute(
                sa.text(
                    "INSERT INTO identity_verifications "
                    "(id, user_id, status, created_at, updated_at) "
                    "VALUES (:rid, :uid, :status, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                ),
                {"rid": request_id, "uid": user_id, "status": request_status},
            )


def insert_raw_user_and_travel(engine) -> None:
    """Insert two users + a travel profile, plan, and partner request with
    RAW SQL.

    Same purpose as the other raw helpers: the Phase 7 downgrade guard
    must be tested against rows no matter who wrote them. Works on a
    schema that already has the travel tables (revision 426dcef31e27).
    Two users exist because a partner request needs a real counterpart.
    Only NOT NULL columns and the 'Migration Probe' names are written;
    everything else takes its column defaults.
    """
    if engine.dialect.name == "postgresql":
        uid_a, uid_b, profile_id, plan_id, request_id = (uuid.uuid4() for _ in range(5))
        discoverable_literal = "TRUE"  # PG rejects the integer form
    else:
        uid_a, uid_b, profile_id, plan_id, request_id = (str(uuid.uuid4()) for _ in range(5))
        discoverable_literal = "1"  # SQLite stores booleans as integers
    with engine.begin() as conn:
        for uid in (uid_a, uid_b):
            conn.execute(
                sa.text(
                    "INSERT INTO users "
                    "(id, display_name, created_at, updated_at) "
                    "VALUES (:id, 'Migration Probe', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                ),
                {"id": uid},
            )
        conn.execute(
            sa.text(
                "INSERT INTO travel_profiles "
                "(id, user_id, travel_nickname, discoverable, created_at, updated_at) "
                "VALUES (:pid, :uid, 'Migration Probe', " + discoverable_literal + ", "
                "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ),
            {"pid": profile_id, "uid": uid_a},
        )
        conn.execute(
            sa.text(
                "INSERT INTO travel_plans "
                "(id, user_id, destination, destination_normalized, start_date, end_date, "
                "created_at, updated_at) "
                "VALUES (:planid, :uid, 'Goa', 'goa', '2026-12-01', '2026-12-10', "
                "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ),
            {"planid": plan_id, "uid": uid_a},
        )
        conn.execute(
            sa.text(
                "INSERT INTO travel_partner_requests "
                "(id, requester_id, recipient_id, status, created_at, updated_at) "
                "VALUES (:rid, :uida, :uidb, 'pending', "
                "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ),
            {"rid": request_id, "uida": uid_a, "uidb": uid_b},
        )
