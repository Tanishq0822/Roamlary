"""Authentication tests: register, login, JWT validation (Phase 3).

These run against an in-memory SQLite database (offline). They verify the
full auth flow end-to-end through the real FastAPI app using dependency
overrides, so no PostgreSQL is required.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.security import ALGORITHM, create_access_token, hash_password, verify_password
from app.db.session import get_db
from app.main import app
from app.models.user import User


@pytest.fixture()
def auth_client(sqlite_engine):
    """TestClient wired to the real app but using the SQLite test database.

    Overrides the get_db dependency so every request uses the in-memory
    database instead of PostgreSQL.
    """
    from sqlalchemy.orm import sessionmaker

    TestSession = sessionmaker(bind=sqlite_engine, autoflush=False, expire_on_commit=False)

    def override_get_db():
        session = TestSession()
        try:
            yield session
        finally:
            session.close()

    # Clear any prior overrides, then set ours.
    app.dependency_overrides.clear()
    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


def _register(client: TestClient, email="asha@example.com", password="s3cure-Pass!", name="Asha"):
    return client.post(
        "/api/v1/auth/register",
        json={"display_name": name, "email": email, "password": password},
    )


# ---------------------------------------------------------------- register


def test_register_creates_user_and_returns_token(auth_client):
    resp = _register(auth_client)
    assert resp.status_code == 201
    body = resp.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"
    # The raw token is a three-part JWT.
    assert body["access_token"].count(".") == 2


def test_register_stores_hashed_password_not_plaintext(auth_client, sqlite_engine):
    from sqlalchemy import select
    from sqlalchemy.orm import sessionmaker

    _register(auth_client, password="s3cure-Pass!")
    factory = sessionmaker(bind=sqlite_engine)
    db = factory()
    user = db.scalar(select(User))
    assert user.password_hash is not None
    assert "s3cure-Pass!" not in user.password_hash
    # Argon2id hashes start with the algorithm identifier.
    assert user.password_hash.startswith("$argon2id$")
    db.close()


def test_register_response_excludes_password_hash(auth_client):
    resp = _register(auth_client)
    assert "password_hash" not in resp.json()


def test_register_duplicate_email_conflict(auth_client):
    _register(auth_client, email="dup@example.com")
    resp = _register(auth_client, email="dup@example.com")
    assert resp.status_code == 409


def test_register_duplicate_email_case_insensitive(auth_client):
    _register(auth_client, email="Mixed@Example.com")
    resp = _register(auth_client, email="mixed@example.com")
    assert resp.status_code == 409


def test_register_invalid_email_rejected(auth_client):
    resp = auth_client.post(
        "/api/v1/auth/register",
        json={"display_name": "X", "email": "not-an-email", "password": "s3cure-Pass!"},
    )
    assert resp.status_code == 422


def test_register_short_password_rejected(auth_client):
    resp = auth_client.post(
        "/api/v1/auth/register",
        json={"display_name": "X", "email": "x@example.com", "password": "short"},
    )
    assert resp.status_code == 422


# ------------------------------------------------------------------- login


def test_login_success_returns_token(auth_client):
    _register(auth_client, email="login@example.com", password="s3cure-Pass!")
    resp = auth_client.post(
        "/api/v1/auth/login",
        json={"email": "login@example.com", "password": "s3cure-Pass!"},
    )
    assert resp.status_code == 200
    assert "access_token" in resp.json()


def test_login_wrong_password_rejected(auth_client):
    _register(auth_client, email="wp@example.com", password="s3cure-Pass!")
    resp = auth_client.post(
        "/api/v1/auth/login",
        json={"email": "wp@example.com", "password": "wrong-password"},
    )
    assert resp.status_code == 401


def test_login_unknown_email_same_error_as_wrong_password(auth_client):
    """Unknown email and wrong password must return the SAME error."""
    _register(auth_client, email="known@example.com", password="s3cure-Pass!")
    unknown = auth_client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@example.com", "password": "whatever"},
    )
    wrongpw = auth_client.post(
        "/api/v1/auth/login",
        json={"email": "known@example.com", "password": "wrong"},
    )
    assert unknown.status_code == 401
    assert wrongpw.status_code == 401
    assert unknown.json()["detail"] == wrongpw.json()["detail"]


def test_login_token_claims_safe(auth_client):
    """Token contains sub + exp, and never a password or hash."""
    resp = _register(auth_client, email="claims@example.com")
    token = resp.json()["access_token"]
    claims = jwt.decode(token, options={"verify_signature": False})
    assert "sub" in claims
    assert "exp" in claims
    # No sensitive fields inside the token.
    joined = str(claims).lower()
    assert "password" not in joined
    assert "s3cure-pass" not in joined


# --------------------------------------------------------- JWT validation


def test_protected_route_missing_token_rejected(auth_client):
    resp = auth_client.get("/api/v1/users/me")
    assert resp.status_code == 401


def test_protected_route_malformed_token_rejected(auth_client):
    resp = auth_client.get("/api/v1/users/me", headers={"Authorization": "Bearer not.a.jwt"})
    assert resp.status_code == 401


def test_protected_route_expired_token_rejected(auth_client):
    _register(auth_client, email="exp@example.com")
    # Build an already-expired token directly.
    expired = jwt.encode(
        {
            "sub": str(uuid4()),
            "iat": datetime.now(UTC) - timedelta(hours=2),
            "exp": datetime.now(UTC) - timedelta(hours=1),
        },
        settings.jwt_secret_key,
        algorithm=ALGORITHM,
    )
    resp = auth_client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {expired}"})
    assert resp.status_code == 401


def test_protected_route_bad_signature_rejected(auth_client):
    """A token signed with a DIFFERENT secret must be rejected."""
    # A well-formed but WRONG secret (>=32 bytes, so the test exercises
    # signature mismatch, not a weak-key warning).
    wrong_secret = "a" * 32
    forged = jwt.encode(
        {
            "sub": str(uuid4()),
            "iat": datetime.now(UTC),
            "exp": datetime.now(UTC) + timedelta(hours=1),
        },
        wrong_secret,
        algorithm=ALGORITHM,
    )
    resp = auth_client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {forged}"})
    assert resp.status_code == 401


def test_protected_route_deleted_user_rejected(auth_client, sqlite_engine):
    """A validly signed token whose user no longer exists -> 401."""
    from sqlalchemy.orm import sessionmaker

    _register(auth_client, email="ghost@example.com")
    from sqlalchemy import select

    factory = sessionmaker(bind=sqlite_engine)
    db = factory()
    user = db.scalar(select(User).where(User.email == "ghost@example.com"))
    token = create_access_token(user.id)
    # Delete the user out from under the token.
    db.delete(user)
    db.commit()
    db.close()

    resp = auth_client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401


def test_algorithm_confusion_none_rejected(auth_client):
    """A token claiming alg=none must be rejected."""
    header = jwt.algorithms.base64url_encode(b'{"alg":"none","typ":"JWT"}').decode()
    payload = jwt.algorithms.base64url_encode(b'{"sub":"x","exp":9999999999}').decode()
    resp = auth_client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {header}.{payload}."},
    )
    assert resp.status_code == 401


# -------------------------------------------------------------- unit tests


def test_verify_password_handles_missing_hash():
    assert verify_password("anything", None) is False


def test_hash_and_verify_round_trip():
    h = hash_password("another-pass")
    assert verify_password("another-pass", h) is True
    assert verify_password("wrong", h) is False


def test_two_identical_passwords_produce_different_hashes():
    """A fresh random salt per hash means identical inputs differ."""
    assert hash_password("same-password") != hash_password("same-password")


def test_health_still_works_with_auth_configured(auth_client):
    """Regression: the public health endpoint is unaffected by auth."""
    resp = auth_client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json() == {
        "status": "ok",
        "service": "roamlary-backend",
        "version": "1.0.0",
    }
