"""User-profile endpoint tests: GET/PATCH /users/me (Phase 3)."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.db.session import get_db
from app.main import app


@pytest.fixture()
def profile_client(sqlite_engine):
    """TestClient wired to the SQLite test database."""
    TestSession = sessionmaker(bind=sqlite_engine, autoflush=False, expire_on_commit=False)

    def override_get_db():
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


def _register_and_get_token(client, email="prof@example.com"):
    resp = client.post(
        "/api/v1/auth/register",
        json={"display_name": "Asha", "email": email, "password": "s3cure-Pass!"},
    )
    return resp.json()["access_token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_get_me_returns_own_profile(profile_client):
    token = _register_and_get_token(profile_client)
    resp = profile_client.get("/api/v1/users/me", headers=_auth(token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["display_name"] == "Asha"
    assert body["email"] == "prof@example.com"
    assert "id" in body
    assert "created_at" in body


def test_get_me_requires_token(profile_client):
    resp = profile_client.get("/api/v1/users/me")
    assert resp.status_code == 401


def test_get_me_never_exposes_password_hash(profile_client):
    token = _register_and_get_token(profile_client)
    resp = profile_client.get("/api/v1/users/me", headers=_auth(token))
    assert "password_hash" not in resp.json()


def test_patch_me_updates_display_name(profile_client):
    token = _register_and_get_token(profile_client)
    resp = profile_client.patch(
        "/api/v1/users/me",
        headers=_auth(token),
        json={"display_name": "Asha Updated"},
    )
    assert resp.status_code == 200
    assert resp.json()["display_name"] == "Asha Updated"


def test_patch_me_persists_change(profile_client):
    token = _register_and_get_token(profile_client)
    profile_client.patch(
        "/api/v1/users/me", headers=_auth(token), json={"display_name": "Persisted"}
    )
    resp = profile_client.get("/api/v1/users/me", headers=_auth(token))
    assert resp.json()["display_name"] == "Persisted"


def test_patch_me_rejects_protected_fields(profile_client):
    """Attempting to set id/email/password_hash -> 422 (extra=forbid)."""
    token = _register_and_get_token(profile_client)
    resp = profile_client.patch(
        "/api/v1/users/me",
        headers=_auth(token),
        json={"display_name": "X", "id": "hacked", "password_hash": "evil"},
    )
    assert resp.status_code == 422


def test_patch_me_rejects_blank_display_name(profile_client):
    token = _register_and_get_token(profile_client)
    resp = profile_client.patch(
        "/api/v1/users/me", headers=_auth(token), json={"display_name": "   "}
    )
    assert resp.status_code == 422


def test_patch_me_requires_token(profile_client):
    resp = profile_client.patch("/api/v1/users/me", json={"display_name": "X"})
    assert resp.status_code == 401


def test_two_users_cannot_read_each_other(profile_client):
    """Each token resolves to its own user; no cross-account access."""
    t1 = _register_and_get_token(profile_client, email="one@example.com")
    t2 = _register_and_get_token(profile_client, email="two@example.com")
    r1 = profile_client.get("/api/v1/users/me", headers=_auth(t1))
    r2 = profile_client.get("/api/v1/users/me", headers=_auth(t2))
    assert r1.json()["email"] == "one@example.com"
    assert r2.json()["email"] == "two@example.com"
    assert r1.json()["id"] != r2.json()["id"]


def test_email_is_normalized_on_register(profile_client):
    """Whitespace + mixed case are normalized before saving."""
    token = _register_and_get_token(profile_client, email="  MixedCase@Example.COM ")
    resp = profile_client.get("/api/v1/users/me", headers=_auth(token))
    assert resp.json()["email"] == "mixedcase@example.com"
