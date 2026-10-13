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
from sqlalchemy import create_engine, event, select
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


def insert_raw_phase8_rows(engine) -> None:
    """Insert two users + a block, a conversation, a message, and a login
    session with RAW SQL.

    Same purpose as the other raw helpers: the Phase 8 downgrade guard
    must be tested against rows no matter who wrote them. Works on a
    schema that already has the Phase 8 tables (revision 7f3a9c1e5b42).
    Only NOT NULL columns and the 'Migration Probe' names are written;
    everything else takes its column defaults. The conversation pair is
    ordered the same way app/core/pairing.canonical_pair orders UUIDs
    (hex comparison matches integer comparison for UUIDs).
    """
    if engine.dialect.name == "postgresql":
        uid_a, uid_b, block_id, conv_id, msg_id, sess_id = (uuid.uuid4() for _ in range(6))
    else:
        uid_a, uid_b, block_id, conv_id, msg_id, sess_id = (str(uuid.uuid4()) for _ in range(6))
    low, high = (uid_a, uid_b) if str(uid_a) <= str(uid_b) else (uid_b, uid_a)
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
                "INSERT INTO user_blocks "
                "(id, blocker_id, blocked_id, created_at, updated_at) "
                "VALUES (:bid, :uida, :uidb, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ),
            {"bid": block_id, "uida": uid_a, "uidb": uid_b},
        )
        conn.execute(
            sa.text(
                "INSERT INTO conversations "
                "(id, user_low_id, user_high_id, status, requested_by, "
                "created_at, updated_at) "
                "VALUES (:cid, :low, :high, 'pending', :uida, "
                "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ),
            {"cid": conv_id, "low": low, "high": high, "uida": uid_a},
        )
        conn.execute(
            sa.text(
                "INSERT INTO messages "
                "(id, conversation_id, sender_id, body, created_at, updated_at) "
                "VALUES (:mid, :cid, :uida, 'hello', "
                "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ),
            {"mid": msg_id, "cid": conv_id, "uida": uid_a},
        )
        conn.execute(
            sa.text(
                "INSERT INTO auth_sessions "
                "(id, user_id, created_at, updated_at) "
                "VALUES (:sid, :uida, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ),
            {"sid": sess_id, "uida": uid_a},
        )


def insert_raw_phase912_rows(engine) -> None:
    """Insert two users + one row in each Phases 9-12 table and a
    `resolved` report, all with RAW SQL.

    Same purpose as the other raw helpers: the combined downgrade guard
    must be tested against rows no matter who wrote them. Works on a
    schema at revision b8e2f4a1c6d9. Only NOT NULL columns and the
    'Migration Probe' names are written; everything else takes column
    defaults.
    """
    if engine.dialect.name == "postgresql":
        ids = [uuid.uuid4() for _ in range(10)]
    else:
        ids = [str(uuid.uuid4()) for _ in range(10)]
    uid_a, uid_b, meet_id, memb_id, inv_id, ann_id, notif_id, share_id, rep_id = ids[:9]
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
                "INSERT INTO meetups "
                "(id, host_id, kind, title, category, start_at, end_at, capacity, "
                "visibility, participation, status, created_at, updated_at) "
                "VALUES (:mid, :uid, 'meetup', 'Probe Hike', 'hiking', "
                "'2027-01-05T10:00:00+00:00', '2027-01-05T12:00:00+00:00', 10, "
                "'public', 'approval', 'active', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ),
            {"mid": meet_id, "uid": uid_a},
        )
        conn.execute(
            sa.text(
                "INSERT INTO meetup_memberships "
                "(id, meetup_id, user_id, status, created_at, updated_at) "
                "VALUES (:mbid, :mid, :uid, 'approved', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ),
            {"mbid": memb_id, "mid": meet_id, "uid": uid_b},
        )
        conn.execute(
            sa.text(
                "INSERT INTO event_invitations "
                "(id, meetup_id, inviter_id, invitee_id, status, created_at, updated_at) "
                "VALUES (:iid, :mid, :uida, :uidb, 'pending', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ),
            {"iid": inv_id, "mid": meet_id, "uida": uid_a, "uidb": uid_b},
        )
        conn.execute(
            sa.text(
                "INSERT INTO meetup_announcements "
                "(id, meetup_id, author_id, body, created_at, updated_at) "
                "VALUES (:aid, :mid, :uid, 'hello', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ),
            {"aid": ann_id, "mid": meet_id, "uid": uid_a},
        )
        conn.execute(
            sa.text(
                "INSERT INTO notifications "
                "(id, user_id, kind, title, body, channel, status, attempts, "
                "idempotency_key, created_at, updated_at) "
                "VALUES (:nid, :uid, 'trip_shared', 'Probe', 'hello', 'in_app', "
                "'delivered', 1, 'probe-key', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ),
            {"nid": notif_id, "uid": uid_a},
        )
        conn.execute(
            sa.text(
                "INSERT INTO trip_shares "
                "(id, owner_id, expires_at, created_at, updated_at) "
                "VALUES (:sid, :uid, '2027-02-01T00:00:00+00:00', "
                "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ),
            {"sid": share_id, "uid": uid_a},
        )
        conn.execute(
            sa.text(
                "INSERT INTO community_reports "
                "(id, user_id, category, description, latitude, longitude, status, "
                "reviewed_by, reviewed_at, created_at, updated_at) "
                "VALUES (:rid, :uid, 'other', 'probe', 1.0, 2.0, 'resolved', "
                ":uid, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ),
            {"rid": rep_id, "uid": uid_a},
        )


def insert_raw_phase1415_rows(engine) -> None:
    """Insert one user + a payment row and a consent row with RAW SQL.

    Same purpose as the other raw helpers: the Phases 14-15 downgrade
    guard must be tested against rows no matter who wrote them. Works
    on a schema at revision c4d9e2f7a1b3. Only NOT NULL columns are
    written; everything else takes column defaults.
    """
    if engine.dialect.name == "postgresql":
        uid, pay_id, consent_id = (uuid.uuid4() for _ in range(3))
    else:
        uid, pay_id, consent_id = (str(uuid.uuid4()) for _ in range(3))
    with engine.begin() as conn:
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
                "INSERT INTO post_payments "
                "(id, user_id, category, amount_paise, currency, status, provider, "
                "idempotency_key, attempts, created_at, updated_at) "
                "VALUES (:pid, :uid, 'meetup', 1000, 'INR', 'succeeded', 'mock', "
                "'probe-key', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ),
            {"pid": pay_id, "uid": uid},
        )
        conn.execute(
            sa.text(
                "INSERT INTO safety_consents "
                "(id, user_id, subject_type, subject_id, decision, disclosure_version, "
                "created_at, updated_at) "
                "VALUES (:cid, :uid, 'meetup', :uid, 'declined', '2026-10-15.v1', "
                "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ),
            {"cid": consent_id, "uid": uid},
        )


def prefund_payment(engine, email: str, category: str) -> str:
    """Insert a SUCCEEDED mock payment row for a user; returns its id.

    Test-only shortcut for suites that predate pay-per-post: the
    billing handshake itself is proven in test_billing.py, so older
    multi-create tests fund their 2nd+ posts directly instead of
    re-testing the 402/pay/resubmit loop. The row is real (consumed
    atomically by the endpoint like any payment).
    """
    from sqlalchemy.orm import sessionmaker

    from app.models import PostPayment, User

    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    db = factory()
    try:
        user = db.scalar(select(User).where(User.email == email))
        row = PostPayment(
            user_id=user.id,
            category=category,
            amount_paise=1000,
            currency="INR",
            status="succeeded",
            provider="mock",
            provider_reference=f"prefund-{uuid.uuid4().hex}",
            idempotency_key=f"prefund-{uuid.uuid4().hex}",
        )
        db.add(row)
        db.commit()
        return str(row.id)
    finally:
        db.close()
