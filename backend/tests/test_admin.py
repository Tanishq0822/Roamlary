"""Owner-only admin endpoint tests: review queue, policy, audit (Phase 6b).

Covers the phase brief's owner-authorization cases: every admin route
denies anonymous (401) and ordinary users (403), and probing them never
changes anyone's role; the review queue pages/filters correctly and
exposes review outcomes; approve/reject enforce valid transitions (404 /
409, self-review blocked even for the owner); and the policy endpoint is
owner-only, defaults to "verification required", audits every real
change (who/when/old/new), fails closed on corrupt configuration, is
rate limited, and never auto-verifies or rewrites anyone's history.

NOTE: an autouse fixture resets the in-process rate limiter before every
test, so the limit test stays deterministic and never leaks into others.
"""

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.cli import promote_to_owner
from app.core.policy import SOCIAL_REQUIRES_VERIFICATION_KEY
from app.core.rate_limit import reset_rate_limits
from app.models.app_setting import AppSetting
from app.models.identity_verification import IdentityVerification
from app.models.setting_change import SettingChange
from app.models.user import User
from tests.conftest import register_user

ADMIN_LIST = "/api/v1/admin/verification-requests"
POLICY = "/api/v1/admin/policy/social-verification"
DISCOVERY_PATH = "/api/v1/social/discovery"
REQUESTS_PATH = "/api/v1/verification/requests"

REVIEW_FIELDS = {
    "id",
    "user_id",
    "display_name",
    "status",
    "created_at",
    "reviewed_at",
    "reviewed_by",
    "review_note",
    "applicant_note",
}
POLICY_FIELDS = {"key", "requires_verification", "updated_at", "updated_by"}


@pytest.fixture(autouse=True)
def _fresh_rate_limit():
    """Every test starts with an empty rate-limit window."""
    reset_rate_limits()
    yield
    reset_rate_limits()


def _session(engine):
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    return factory()


def _make_owner(engine, email: str) -> None:
    """Grant owner via the REAL provisioning path (server-side CLI)."""
    db = _session(engine)
    try:
        promote_to_owner(db, email)
    finally:
        db.close()


def _owner_pair(api_client, sqlite_engine, email="owner@example.com"):
    """Register an account and grant it owner; returns bearer headers.

    Order matters: the CLI refuses to promote a nonexistent account, so
    registration must happen FIRST - exactly like real operations.
    """
    _, headers = register_user(api_client, email)
    _make_owner(sqlite_engine, email)
    return headers


def _me_id(api_client, headers) -> str:
    """The caller's own user id (from their own profile endpoint)."""
    return api_client.get("/api/v1/users/me", headers=headers).json()["id"]


def _submit(api_client, headers, note: str | None = None):
    payload = {} if note is None else {"note": note}
    return api_client.post(REQUESTS_PATH, json=payload, headers=headers)


def _policy_setting(db) -> AppSetting | None:
    return db.scalar(select(AppSetting).where(AppSetting.key == SOCIAL_REQUIRES_VERIFICATION_KEY))


def _audit_rows(db) -> list[SettingChange]:
    return list(
        db.execute(select(SettingChange).order_by(SettingChange.created_at.asc())).scalars().all()
    )


# ------------------------------------------------- authorization matrix


def test_admin_routes_require_authentication(api_client):
    """Anonymous callers get 401 on every admin route (before any logic)."""
    fake_id = str(uuid.uuid4())
    assert api_client.get(ADMIN_LIST).status_code == 401
    assert api_client.post(f"{ADMIN_LIST}/{fake_id}/approve", json={}).status_code == 401
    assert api_client.post(f"{ADMIN_LIST}/{fake_id}/reject", json={}).status_code == 401
    assert api_client.get(POLICY).status_code == 401
    assert api_client.patch(POLICY, json={"requires_verification": False}).status_code == 401


def test_admin_routes_forbidden_for_ordinary_user(api_client, sqlite_engine):
    """Brief items 6+7: a token is not enough - the `owner` role is, and
    ordinary users get 403 everywhere. Probing must change nothing."""
    _, h = register_user(api_client, "ordinary@example.com")
    fake_id = str(uuid.uuid4())

    assert api_client.get(ADMIN_LIST, headers=h).status_code == 403
    assert api_client.post(f"{ADMIN_LIST}/{fake_id}/approve", json={}, headers=h).status_code == 403
    assert api_client.post(f"{ADMIN_LIST}/{fake_id}/reject", json={}, headers=h).status_code == 403
    assert api_client.get(POLICY, headers=h).status_code == 403
    assert (
        api_client.patch(POLICY, json={"requires_verification": False}, headers=h).status_code
        == 403
    )

    # None of that probing granted anything: role untouched in the
    # database, policy row never created, gate still on.
    db = _session(sqlite_engine)
    try:
        user = db.scalar(select(User).where(User.email == "ordinary@example.com"))
        assert user.role == "user"
        assert _policy_setting(db) is None
    finally:
        db.close()
    assert api_client.get(DISCOVERY_PATH, headers=h).status_code == 403  # still gated


# ----------------------------------------------------------- review queue


def test_queue_lists_requests_oldest_first_with_exact_shape(api_client, sqlite_engine):
    owner_h = _owner_pair(api_client, sqlite_engine)
    _, h1 = register_user(api_client, "q1@example.com")
    _, h2 = register_user(api_client, "q2@example.com")
    r1 = _submit(api_client, h1, note="first applicant")
    r2 = _submit(api_client, h2, note="second applicant")
    assert r1.status_code == 201 and r2.status_code == 201

    resp = api_client.get(ADMIN_LIST, headers=owner_h)
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 2
    # Oldest submitted first (FIFO review fairness).
    assert rows[0]["id"] == r1.json()["id"]
    assert rows[1]["id"] == r2.json()["id"]
    assert set(rows[0]) == REVIEW_FIELDS  # no email, no password hash
    assert rows[0]["applicant_note"] == "first applicant"
    assert rows[0]["display_name"] == "Tester"
    assert rows[0]["status"] == "pending"
    assert rows[0]["reviewed_at"] is None and rows[0]["reviewed_by"] is None


def test_queue_status_filter_and_invalid_filter(api_client, sqlite_engine):
    owner_h = _owner_pair(api_client, sqlite_engine)
    _, h1 = register_user(api_client, "f1@example.com")
    _, h2 = register_user(api_client, "f2@example.com")
    _submit(api_client, h1)
    _submit(api_client, h2)
    # Approve one, reject the other.
    rows = api_client.get(ADMIN_LIST, headers=owner_h).json()
    assert (
        api_client.post(
            f"{ADMIN_LIST}/{rows[0]['id']}/approve", json={}, headers=owner_h
        ).status_code
        == 200
    )
    assert (
        api_client.post(
            f"{ADMIN_LIST}/{rows[1]['id']}/reject",
            json={"review_note": "unclear"},
            headers=owner_h,
        ).status_code
        == 200
    )

    assert len(api_client.get(f"{ADMIN_LIST}?status=pending", headers=owner_h).json()) == 0
    approved = api_client.get(f"{ADMIN_LIST}?status=approved", headers=owner_h).json()
    rejected = api_client.get(f"{ADMIN_LIST}?status=rejected", headers=owner_h).json()
    assert [r["status"] for r in approved] == ["approved"]
    assert [r["status"] for r in rejected] == ["rejected"]
    # Unknown filter value -> 422 (closed set, like every enum in this API).
    assert api_client.get(f"{ADMIN_LIST}?status=whatever", headers=owner_h).status_code == 422


def test_queue_pagination_bounds(api_client, sqlite_engine):
    owner_h = _owner_pair(api_client, sqlite_engine)
    for i in range(3):
        _, h = register_user(api_client, f"p{i}@example.com")
        assert _submit(api_client, h).status_code == 201

    assert api_client.get(f"{ADMIN_LIST}?limit=0", headers=owner_h).status_code == 422
    assert api_client.get(f"{ADMIN_LIST}?limit=101", headers=owner_h).status_code == 422
    assert api_client.get(f"{ADMIN_LIST}?offset=-1", headers=owner_h).status_code == 422

    page = api_client.get(f"{ADMIN_LIST}?limit=2", headers=owner_h).json()
    assert len(page) == 2
    page2 = api_client.get(f"{ADMIN_LIST}?limit=2&offset=2", headers=owner_h).json()
    assert len(page2) == 1  # the third request


def test_queue_review_outcomes_recorded_with_owner_identity(api_client, sqlite_engine):
    owner_h = _owner_pair(api_client, sqlite_engine)
    owner_id = _me_id(api_client, owner_h)
    _, h = register_user(api_client, "rev@example.com")
    _submit(api_client, h, note="context for reviewer")
    rows = api_client.get(ADMIN_LIST, headers=owner_h).json()

    approve = api_client.post(
        f"{ADMIN_LIST}/{rows[0]['id']}/approve",
        json={"review_note": "welcome aboard"},
        headers=owner_h,
    )
    assert approve.status_code == 200
    body = approve.json()
    assert set(body) == REVIEW_FIELDS
    assert body["status"] == "approved"
    assert body["reviewed_by"] == owner_id  # WHO decided
    assert body["reviewed_at"] is not None  # WHEN (UTC)
    assert body["review_note"] == "welcome aboard"
    assert body["applicant_note"] == "context for reviewer"  # history intact


# --------------------------------------------------- review transitions


def test_review_nonexistent_request_is_404(api_client, sqlite_engine):
    owner_h = _owner_pair(api_client, sqlite_engine)
    missing = str(uuid.uuid4())
    assert (
        api_client.post(f"{ADMIN_LIST}/{missing}/approve", json={}, headers=owner_h).status_code
        == 404
    )
    assert (
        api_client.post(f"{ADMIN_LIST}/{missing}/reject", json={}, headers=owner_h).status_code
        == 404
    )


def test_review_invalid_transitions_conflict(api_client, sqlite_engine):
    """Brief item 5: only pending requests can be reviewed - reviewing an
    already-decided request is 409 (approve-after-approve and
    reject-after-approve both)."""
    owner_h = _owner_pair(api_client, sqlite_engine)
    _, h = register_user(api_client, "trans@example.com")
    _submit(api_client, h)
    req_id = api_client.get(ADMIN_LIST, headers=owner_h).json()[0]["id"]

    first = api_client.post(f"{ADMIN_LIST}/{req_id}/approve", json={}, headers=owner_h)
    assert first.status_code == 200
    again = api_client.post(f"{ADMIN_LIST}/{req_id}/approve", json={}, headers=owner_h)
    assert again.status_code == 409
    assert "Only pending" in again.json()["detail"]
    opposite = api_client.post(f"{ADMIN_LIST}/{req_id}/reject", json={}, headers=owner_h)
    assert opposite.status_code == 409


def test_owner_cannot_review_own_request(api_client, sqlite_engine):
    """Self-review is blocked for EVERYONE, owner included: the only
    account that could otherwise mark itself verified is the owner."""
    owner_h = _owner_pair(api_client, sqlite_engine)
    assert _submit(api_client, owner_h).status_code == 201
    req_id = api_client.get(ADMIN_LIST, headers=owner_h).json()[0]["id"]

    approve = api_client.post(f"{ADMIN_LIST}/{req_id}/approve", json={}, headers=owner_h)
    assert approve.status_code == 409
    assert "your own" in approve.json()["detail"]
    reject = api_client.post(f"{ADMIN_LIST}/{req_id}/reject", json={}, headers=owner_h)
    assert reject.status_code == 409
    # And the account did not change: still pending, never verified.
    status = api_client.get("/api/v1/verification/status", headers=owner_h).json()
    assert status["verification_status"] == "pending"


def test_review_works_without_a_body(api_client, sqlite_engine):
    """The review body is optional: a bare POST approves just the same."""
    owner_h = _owner_pair(api_client, sqlite_engine)
    _, h = register_user(api_client, "nobody@example.com")
    _submit(api_client, h)
    req_id = api_client.get(ADMIN_LIST, headers=owner_h).json()[0]["id"]

    resp = api_client.post(f"{ADMIN_LIST}/{req_id}/approve", headers=owner_h)
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "approved"


def test_reject_response_and_applicant_see_the_outcome(api_client, sqlite_engine):
    owner_h = _owner_pair(api_client, sqlite_engine)
    _, h = register_user(api_client, "seen@example.com")
    _submit(api_client, h)
    req_id = api_client.get(ADMIN_LIST, headers=owner_h).json()[0]["id"]

    reject = api_client.post(
        f"{ADMIN_LIST}/{req_id}/reject",
        json={"review_note": "document was blurry"},
        headers=owner_h,
    )
    assert reject.status_code == 200
    assert reject.json()["reviewed_at"] is not None

    # The applicant sees the outcome on THEIR OWN status endpoint.
    status = api_client.get("/api/v1/verification/status", headers=h).json()
    assert status["verification_status"] == "rejected"
    assert status["latest_request"]["review_note"] == "document was blurry"
    assert status["latest_request"]["status"] == "rejected"


# --------------------------------------------------------------- policy


def test_policy_default_requires_verification(api_client, sqlite_engine):
    """Brief item 8: no configuration row at all -> effective policy is
    'verification required' (fail-closed default)."""
    owner_h = _owner_pair(api_client, sqlite_engine)
    resp = api_client.get(POLICY, headers=owner_h)
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == POLICY_FIELDS
    assert body["key"] == "social_requires_verification"
    assert body["requires_verification"] is True
    assert body["updated_at"] is None and body["updated_by"] is None


def test_policy_change_records_who_when_old_new(api_client, sqlite_engine, db_session):
    """Brief item D: every real change appends an audit row with who,
    when, old value, and new value (first-ever write audits old=NULL)."""
    owner_h = _owner_pair(api_client, sqlite_engine)
    owner_id = _me_id(api_client, owner_h)

    first = api_client.patch(POLICY, json={"requires_verification": False}, headers=owner_h)
    assert first.status_code == 200
    assert first.json()["requires_verification"] is False
    assert first.json()["updated_by"] == owner_id
    assert first.json()["updated_at"] is not None

    second = api_client.patch(POLICY, json={"requires_verification": True}, headers=owner_h)
    assert second.status_code == 200

    rows = _audit_rows(db_session)
    assert len(rows) == 2
    assert rows[0].old_value is None  # there was no setting before
    assert rows[0].new_value == "false"
    assert rows[0].setting_key == SOCIAL_REQUIRES_VERIFICATION_KEY
    assert rows[1].old_value == "false" and rows[1].new_value == "true"
    for row in rows:
        assert str(row.changed_by) == owner_id  # WHO
        assert row.created_at is not None  # WHEN (UTC)
    setting = _policy_setting(db_session)
    assert setting.value == "true"
    assert str(setting.updated_by) == owner_id


def test_noop_policy_change_writes_no_audit_row(api_client, sqlite_engine, db_session):
    """Setting the same value twice is not a change: no audit noise."""
    owner_h = _owner_pair(api_client, sqlite_engine)
    first = api_client.patch(POLICY, json={"requires_verification": False}, headers=owner_h)
    assert first.status_code == 200
    second = api_client.patch(POLICY, json={"requires_verification": False}, headers=owner_h)
    assert second.status_code == 200
    assert len(_audit_rows(db_session)) == 1  # only the real change


def test_policy_change_rejects_invalid_body(api_client, sqlite_engine):
    owner_h = _owner_pair(api_client, sqlite_engine)
    resp = api_client.patch(POLICY, json={"requires_verification": "banana"}, headers=owner_h)
    assert resp.status_code == 422
    resp = api_client.patch(
        POLICY,
        json={"requires_verification": True, "extra": "field"},
        headers=owner_h,
    )
    assert resp.status_code == 422  # strict body


def test_policy_change_rate_limited(api_client, sqlite_engine):
    """Sensitive-action protection: 5 changes/hour/owner, then 429.
    (In-process window - documented limitation: multi-worker deployments
    need a shared store.)"""
    owner_h = _owner_pair(api_client, sqlite_engine)
    for i in range(5):
        resp = api_client.patch(POLICY, json={"requires_verification": i % 2 == 0}, headers=owner_h)
        assert resp.status_code == 200, f"attempt {i + 1} should still be allowed"
    resp = api_client.patch(POLICY, json={"requires_verification": True}, headers=owner_h)
    assert resp.status_code == 429
    assert "Try again" in resp.json()["detail"]


def test_policy_change_does_not_auto_verify_or_rewrite_history(
    api_client, sqlite_engine, db_session
):
    """Brief item 10: flipping the policy touches ONLY the settings and
    audit tables - nobody's verification state or review history moves."""
    owner_h = _owner_pair(api_client, sqlite_engine)
    _, h = register_user(api_client, "history@example.com")
    assert _submit(api_client, h).status_code == 201
    req_id = api_client.get(ADMIN_LIST, headers=owner_h).json()[0]["id"]
    assert (
        api_client.post(f"{ADMIN_LIST}/{req_id}/approve", json={}, headers=owner_h).status_code
        == 200
    )
    _, h2 = register_user(api_client, "stillpending@example.com")
    assert _submit(api_client, h2).status_code == 201

    # Off, then on again.
    off = api_client.patch(POLICY, json={"requires_verification": False}, headers=owner_h)
    assert off.status_code == 200
    on = api_client.patch(POLICY, json={"requires_verification": True}, headers=owner_h)
    assert on.status_code == 200

    # Verified stays verified, pending stays pending, unverified stays
    # unverified - the flip moved no user at all.
    assert (
        api_client.get("/api/v1/verification/status", headers=h).json()["verification_status"]
        == "verified"
    )
    assert (
        api_client.get("/api/v1/verification/status", headers=h2).json()["verification_status"]
        == "pending"
    )
    _, h3 = register_user(api_client, "untouched@example.com")
    assert (
        api_client.get("/api/v1/verification/status", headers=h3).json()["verification_status"]
        == "unverified"
    )
    # The historical request row is unchanged too.
    request = db_session.get(IdentityVerification, uuid.UUID(req_id))
    assert request.status == "approved"
    assert request.reviewed_at is not None


def test_policy_off_opens_gate_and_on_closes_it_again(api_client, sqlite_engine):
    """The policy actually controls the gate, in both directions, with
    effect immediately (no restart, no token refresh)."""
    owner_h = _owner_pair(api_client, sqlite_engine)
    _, h = register_user(api_client, "toggle@example.com")
    assert api_client.get(DISCOVERY_PATH, headers=h).status_code == 403

    assert api_client.patch(POLICY, json={"requires_verification": False}, headers=owner_h)
    assert api_client.get(DISCOVERY_PATH, headers=h).status_code == 200

    assert api_client.patch(POLICY, json={"requires_verification": True}, headers=owner_h)
    assert api_client.get(DISCOVERY_PATH, headers=h).status_code == 403


def test_corrupt_policy_value_fails_closed(api_client, sqlite_engine, db_session):
    """Brief item 9: a garbage stored value never opens access - the
    effective policy stays 'required', the gate keeps denying, and the
    owner can overwrite the bad row with a valid PATCH."""
    owner_h = _owner_pair(api_client, sqlite_engine)
    _, h = register_user(api_client, "corrupt@example.com")

    # Simulate a hand-edited/corrupt row (bypass the API's validation).
    seeded = api_client.patch(POLICY, json={"requires_verification": False}, headers=owner_h)
    assert seeded.status_code == 200
    setting = _policy_setting(db_session)
    setting.value = "maybe"
    db_session.commit()

    # Fail closed: reported as required, and the gate still denies.
    reported = api_client.get(POLICY, headers=owner_h).json()
    assert reported["requires_verification"] is True
    assert api_client.get(DISCOVERY_PATH, headers=h).status_code == 403
    status = api_client.get("/api/v1/verification/status", headers=h).json()
    assert status["social_access_required"] is True

    # A valid write repairs the row: writing False against the corrupt
    # raw value is a real change (the corrupt row was effectively True).
    resp = api_client.patch(POLICY, json={"requires_verification": False}, headers=owner_h)
    assert resp.status_code == 200
    assert resp.json()["requires_verification"] is False
    db_session.expire_all()  # the API wrote from a different session
    assert _policy_setting(db_session).value == "false"
