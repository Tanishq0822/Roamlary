"""Endpoint tests for login-session revocation (Phase 8).

These prove the revocation guarantee the brief demands: every login
mints a trackable session; logout kills the calling token on next use
while others survive; revoking one session kills only it; revoke-others
preserves exactly the caller; revoke-all kills everything including the
caller AND legacy pre-Phase-8 tokens (via the version bump); nobody can
touch another account's sessions (identical 404s); direct database
tampering (deleted row, bumped version) is enforced on next use; and
revocation kills TOKENS, not passwords (logging in again after
revoke-all works - there is no refresh-token reuse to reject because no
refresh tokens exist).
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.models import AuthSession, User

SESSIONS_PATH = "/api/v1/auth/sessions"


def _session(engine):
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    return factory()


def _user_with_token(api_client, engine, tag="sess", label=None):
    """Register (one login session) and return (email, headers, token)."""
    email = f"{tag}-{uuid.uuid4().hex[:8]}@example.com"
    body = {"display_name": tag, "email": email, "password": "s3cure-Pass!"}
    if label is not None:
        body["device_label"] = label
    resp = api_client.post("/api/v1/auth/register", json=body)
    assert resp.status_code == 201, resp.text
    token = resp.json()["access_token"]
    return email, {"Authorization": f"Bearer {token}"}, token


def _login(api_client, email, label=None):
    body = {"email": email, "password": "s3cure-Pass!"}
    if label is not None:
        body["device_label"] = label
    resp = api_client.post("/api/v1/auth/login", json=body)
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}, token


def test_login_mints_a_listed_current_session(api_client, sqlite_engine) -> None:
    email, headers, _ = _user_with_token(api_client, sqlite_engine, label="my phone")
    listed = api_client.get(SESSIONS_PATH, headers=headers).json()
    assert listed["total"] == 1
    row = listed["sessions"][0]
    assert row["label"] == "my phone"
    assert row["current"] is True
    assert row["revoked_at"] is None
    assert set(row) == {"id", "label", "created_at", "revoked_at", "current"}


def test_blank_device_label_stores_null(api_client, sqlite_engine) -> None:
    _, headers, _ = _user_with_token(api_client, sqlite_engine, label="   ")
    assert api_client.get(SESSIONS_PATH, headers=headers).json()["sessions"][0]["label"] is None


def test_sessions_require_authentication(api_client) -> None:
    assert api_client.get(SESSIONS_PATH).status_code == 401
    assert api_client.post("/api/v1/auth/logout").status_code == 401
    assert api_client.post("/api/v1/auth/revoke-all").status_code == 401
    assert api_client.post("/api/v1/auth/sessions/revoke-others").status_code == 401


def test_logout_kills_current_token_only(api_client, sqlite_engine) -> None:
    email, headers_a, _ = _user_with_token(api_client, sqlite_engine)
    headers_b, _ = _login(api_client, email)
    assert api_client.get(SESSIONS_PATH, headers=headers_b).json()["total"] == 2

    done = api_client.post("/api/v1/auth/logout", headers=headers_a)
    assert done.status_code == 200
    assert done.json()["revoked_at"] is not None
    # The logged-out token stops working immediately...
    assert api_client.get(SESSIONS_PATH, headers=headers_a).status_code == 401
    # ...while the other session survives untouched.
    listed = api_client.get(SESSIONS_PATH, headers=headers_b).json()
    assert listed["total"] == 2
    current = [s for s in listed["sessions"] if s["current"]]
    assert len(current) == 1 and current[0]["revoked_at"] is None


def test_revoke_one_session_by_id(api_client, sqlite_engine) -> None:
    email, headers_a, _ = _user_with_token(api_client, sqlite_engine)
    headers_b, _ = _login(api_client, email)
    target = [
        s
        for s in api_client.get(SESSIONS_PATH, headers=headers_a).json()["sessions"]
        if not s["current"]
    ][0]["id"]
    revoked = api_client.post(f"{SESSIONS_PATH}/{target}/revoke", headers=headers_a)
    assert revoked.status_code == 200
    assert revoked.json()["revoked_at"] is not None
    assert api_client.get(SESSIONS_PATH, headers=headers_b).status_code == 401
    assert api_client.get(SESSIONS_PATH, headers=headers_a).status_code == 200
    # Re-revoking is idempotent.
    assert api_client.post(f"{SESSIONS_PATH}/{target}/revoke", headers=headers_a).status_code == 200


def test_revoke_others_preserves_exactly_current(api_client, sqlite_engine) -> None:
    email, headers_a, _ = _user_with_token(api_client, sqlite_engine)
    headers_b, _ = _login(api_client, email)
    headers_c, _ = _login(api_client, email)
    result = api_client.post("/api/v1/auth/sessions/revoke-others", headers=headers_a).json()
    assert result["total"] == 3
    current_rows = [s for s in result["sessions"] if s["current"]]
    other_rows = [s for s in result["sessions"] if not s["current"]]
    assert len(current_rows) == 1 and current_rows[0]["revoked_at"] is None
    assert len(other_rows) == 2 and all(s["revoked_at"] is not None for s in other_rows)
    assert api_client.get(SESSIONS_PATH, headers=headers_a).status_code == 200
    assert api_client.get(SESSIONS_PATH, headers=headers_b).status_code == 401
    assert api_client.get(SESSIONS_PATH, headers=headers_c).status_code == 401


def test_revoke_all_kills_everything_including_caller(api_client, sqlite_engine) -> None:
    email, headers_a, _ = _user_with_token(api_client, sqlite_engine)
    headers_b, _ = _login(api_client, email)
    result = api_client.post("/api/v1/auth/revoke-all", headers=headers_a)
    assert result.status_code == 200
    assert all(s["revoked_at"] is not None for s in result.json()["sessions"])
    assert api_client.get(SESSIONS_PATH, headers=headers_a).status_code == 401
    assert api_client.get(SESSIONS_PATH, headers=headers_b).status_code == 401
    # Revocation kills TOKENS, not the password: logging in again works
    # (there are no refresh tokens to reject - none ever existed).
    fresh, _ = _login(api_client, email)
    assert api_client.get(SESSIONS_PATH, headers=fresh).status_code == 200


def test_revoke_all_kills_legacy_token_via_version(api_client, sqlite_engine) -> None:
    """A pre-Phase-8 token (no session id, governed by the version check
    alone) survives row-level revokes but dies on revoke-all's bump."""
    from app.core.security import create_access_token

    email, headers_a, _ = _user_with_token(api_client, sqlite_engine)
    db = _session(sqlite_engine)
    try:
        user = db.scalar(select(User).where(User.email == email))
        legacy = create_access_token(user.id)
    finally:
        db.close()
    legacy_h = {"Authorization": f"Bearer {legacy}"}
    assert api_client.get(SESSIONS_PATH, headers=legacy_h).status_code == 200
    assert api_client.post("/api/v1/auth/revoke-all", headers=headers_a).status_code == 200
    assert api_client.get(SESSIONS_PATH, headers=legacy_h).status_code == 401


def test_direct_version_bump_kills_token(api_client, sqlite_engine) -> None:
    """Tampering-equivalent: a version newer than the token's claim is
    rejected on next use (the revoke-all enforcement path)."""
    email, headers, _ = _user_with_token(api_client, sqlite_engine)
    db = _session(sqlite_engine)
    try:
        user = db.scalar(select(User).where(User.email == email))
        user.token_version = (user.token_version or 0) + 1
        db.commit()
    finally:
        db.close()
    assert api_client.get(SESSIONS_PATH, headers=headers).status_code == 401


def test_deleted_session_row_kills_token(api_client, sqlite_engine) -> None:
    """A session row that vanishes (operator cleanup) invalidates the
    token pointing at it - fail closed, never open."""
    email, headers, _ = _user_with_token(api_client, sqlite_engine)
    db = _session(sqlite_engine)
    try:
        user = db.scalar(select(User).where(User.email == email))
        row = db.scalar(select(AuthSession).where(AuthSession.user_id == user.id))
        db.delete(row)
        db.commit()
    finally:
        db.close()
    assert api_client.get(SESSIONS_PATH, headers=headers).status_code == 401


def test_cannot_revoke_another_users_session(api_client, sqlite_engine) -> None:
    """Session ids are user-scoped: another account's id (or a made-up
    one) returns the identical 404, so ids cannot probe other users."""
    _, headers_a, _ = _user_with_token(api_client, sqlite_engine, tag="victim")
    _, headers_b, _ = _user_with_token(api_client, sqlite_engine, tag="attacker")
    foreign_id = api_client.get(SESSIONS_PATH, headers=headers_a).json()["sessions"][0]["id"]
    assert (
        api_client.post(f"{SESSIONS_PATH}/{foreign_id}/revoke", headers=headers_b).status_code
        == 404
    )
    assert (
        api_client.post(f"{SESSIONS_PATH}/{uuid.uuid4()}/revoke", headers=headers_b).status_code
        == 404
    )
    # The victim's session is untouched.
    assert api_client.get(SESSIONS_PATH, headers=headers_a).status_code == 200


def test_unrelated_accounts_survive_revoke_all(api_client, sqlite_engine) -> None:
    """Account-wide revocation is scoped by user id: no other account's
    rows are stamped and no other token dies (no global-invalidation
    bug)."""
    _, headers_a, _ = _user_with_token(api_client, sqlite_engine, tag="leaver")
    _, headers_b, _ = _user_with_token(api_client, sqlite_engine, tag="stayer")
    assert api_client.post("/api/v1/auth/revoke-all", headers=headers_a).status_code == 200
    assert api_client.get(SESSIONS_PATH, headers=headers_b).status_code == 200
    assert api_client.get(SESSIONS_PATH, headers=headers_b).json()["total"] == 1
