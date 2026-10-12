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

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.db.base_class import Base
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
