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


def test_register_rejects_injected_internal_fields(auth_client):
    """Privileged/internal fields in the body -> 422, never stored.

    The register schema is strict (extra="forbid"): smuggling `id`,
    `password_hash`, or `firebase_uid` is a validation error, not a
    silently-ignored extra.
    """
    resp = auth_client.post(
        "/api/v1/auth/register",
        json={
            "display_name": "X",
            "email": "inject@example.com",
            "password": "s3cure-Pass!",
            "password_hash": "evil-hash",
            "id": "00000000-0000-0000-0000-000000000000",
            "firebase_uid": "evil-uid",
        },
    )
    assert resp.status_code == 422


def test_register_race_duplicate_maps_to_409(sqlite_engine):
    """Simulated concurrent duplicate: pre-check misses the row, the DB
    unique constraint fires on commit -> 409, never an unhandled 500."""
    import pytest
    from fastapi import HTTPException
    from sqlalchemy.orm import sessionmaker

    from app.api.v1.endpoints.auth import register
    from app.api.v1.schemas.auth import RegisterRequest

    factory = sessionmaker(bind=sqlite_engine, autoflush=False, expire_on_commit=False)

    # A concurrent request already committed this email.
    other = factory()
    other.add(
        User(
            display_name="Concurrent",
            email="race@example.com",
            password_hash=hash_password("s3cure-Pass!"),
        )
    )
    other.commit()
    other.close()

    # Our request's session: the duplicate SELECT is "stale" (returns None),
    # exactly what happens in the race window between check and insert.
    db = factory()
    real_scalar = db.scalar
    calls = {"count": 0}

    def stale_scalar(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            return None  # pretend the concurrent row is not visible yet
        return real_scalar(*args, **kwargs)

    db.scalar = stale_scalar

    body = RegisterRequest(display_name="Mine", email="race@example.com", password="s3cure-Pass!")
    with pytest.raises(HTTPException) as exc_info:
        register(body, db)
    assert exc_info.value.status_code == 409
    db.close()


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


def test_login_rejects_extra_fields(auth_client):
    """Strict login schema: unknown fields are a 422, not ignored."""
    resp = auth_client.post(
        "/api/v1/auth/login",
        json={"email": "x@example.com", "password": "whatever1", "role": "admin"},
    )
    assert resp.status_code == 422


def test_login_unknown_email_still_runs_password_verification(auth_client, monkeypatch):
    """Timing equalization: an unknown email must still cost one Argon2
    verification (against the dummy hash), so response time does not reveal
    whether the account exists."""
    import app.api.v1.endpoints.auth as auth_module

    calls = []
    original = auth_module.verify_password

    def spy(password, password_hash):
        calls.append(password_hash)
        return original(password, password_hash)

    monkeypatch.setattr(auth_module, "verify_password", spy)
    resp = auth_client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@example.com", "password": "whatever1"},
    )
    assert resp.status_code == 401
    assert len(calls) == 1
    assert calls[0] == auth_module._DUMMY_PASSWORD_HASH


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


def test_token_missing_required_exp_claim_rejected(auth_client):
    """A correctly signed token WITHOUT the required exp claim -> 401."""
    _register(auth_client, email="noexp@example.com")
    no_exp = jwt.encode(
        {"sub": str(uuid4()), "iat": datetime.now(UTC)},
        settings.jwt_secret_key,
        algorithm=ALGORITHM,
    )
    resp = auth_client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {no_exp}"})
    assert resp.status_code == 401


def test_token_missing_required_sub_claim_rejected(auth_client):
    """A correctly signed token WITHOUT the required sub claim -> 401."""
    no_sub = jwt.encode(
        {"iat": datetime.now(UTC), "exp": datetime.now(UTC) + timedelta(hours=1)},
        settings.jwt_secret_key,
        algorithm=ALGORITHM,
    )
    resp = auth_client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {no_sub}"})
    assert resp.status_code == 401


def test_token_with_non_uuid_sub_rejected(auth_client):
    """A signed token whose sub is not a valid user UUID -> 401."""
    bad_sub = jwt.encode(
        {
            "sub": "not-a-uuid",
            "iat": datetime.now(UTC),
            "exp": datetime.now(UTC) + timedelta(hours=1),
        },
        settings.jwt_secret_key,
        algorithm=ALGORITHM,
    )
    resp = auth_client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {bad_sub}"})
    assert resp.status_code == 401


def test_sub_claim_cannot_be_swapped_to_impersonate(auth_client, sqlite_engine):
    """Changing sub to another user's id invalidates the signature -> 401."""
    from sqlalchemy import select
    from sqlalchemy.orm import sessionmaker

    t1 = _register(auth_client, email="victim@example.com").json()["access_token"]
    _register(auth_client, email="attacker@example.com")

    factory = sessionmaker(bind=sqlite_engine)
    db = factory()
    victim = db.scalar(select(User).where(User.email == "victim@example.com"))
    db.close()

    # Attacker re-signs a token with the victim's sub using the WRONG key
    # (they never know the real secret, so any swap breaks the signature).
    swapped = jwt.encode(
        {
            "sub": str(victim.id),
            "iat": datetime.now(UTC),
            "exp": datetime.now(UTC) + timedelta(hours=1),
        },
        "attacker-key-attacker-key-attacker!",
        algorithm=ALGORITHM,
    )
    resp = auth_client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {swapped}"})
    assert resp.status_code == 401
    # And the legitimate token still works.
    assert (
        auth_client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {t1}"}).status_code
        == 200
    )


# ------------------------------------------------------------- fail-closed


def test_missing_jwt_secret_blocks_token_issuance(auth_client, monkeypatch):
    """No JWT_SECRET_KEY -> register and login both return 503 (fail closed).

    The account is created FIRST (with a secret configured), then the
    secret is removed, so the login 503 proves token issuance itself is
    blocked - not merely that the account is missing (which would be 401).
    """
    # Create the account while auth is still configured.
    _register(auth_client, email="nosecret@example.com")
    monkeypatch.setattr(settings, "jwt_secret_key", "")

    reg = auth_client.post(
        "/api/v1/auth/register",
        json={"display_name": "X", "email": "other@example.com", "password": "s3cure-Pass!"},
    )
    assert reg.status_code == 503

    login = auth_client.post(
        "/api/v1/auth/login",
        json={"email": "nosecret@example.com", "password": "s3cure-Pass!"},
    )
    assert login.status_code == 503


def test_missing_jwt_secret_blocks_token_verification(auth_client, monkeypatch):
    """No JWT_SECRET_KEY -> even a once-valid token is refused (503)."""
    token = _register(auth_client, email="keep@example.com").json()["access_token"]
    monkeypatch.setattr(settings, "jwt_secret_key", "")
    resp = auth_client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 503


def test_missing_jwt_secret_does_not_create_account(auth_client, monkeypatch, sqlite_engine):
    """Fail closed BEFORE the database write: no half-created account."""
    from sqlalchemy import select
    from sqlalchemy.orm import sessionmaker

    monkeypatch.setattr(settings, "jwt_secret_key", "")
    auth_client.post(
        "/api/v1/auth/register",
        json={"display_name": "X", "email": "half@example.com", "password": "s3cure-Pass!"},
    )
    factory = sessionmaker(bind=sqlite_engine)
    db = factory()
    assert db.scalar(select(User).where(User.email == "half@example.com")) is None
    db.close()


def test_health_works_without_jwt_secret(auth_client, monkeypatch):
    """Regression: health stays 200 with auth unconfigured."""
    monkeypatch.setattr(settings, "jwt_secret_key", "")
    resp = auth_client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json() == {
        "status": "ok",
        "service": "roamlary-backend",
        "version": "1.0.0",
    }


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
