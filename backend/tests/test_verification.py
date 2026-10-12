"""Identity-verification workflow + social-gate tests (Phase 6b).

Covers the phase brief's required cases end-to-end through the real API:
new accounts start unverified; strict bodies reject every self-elevation
attempt (`role`, `verification_status`, `status`, `user_id`); the submit
workflow moves unverified/rejected -> pending and refuses invalid
transitions with 409; the gate denies unverified/pending/rejected
accounts with actionable 403s and admits a verified account only after a
real owner approval; safety workflows (contacts, check-ins, SOS,
reports) and account routes stay open regardless of verification; and
responses never expose another user's data or sensitive fields.
"""

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.cli import promote_to_owner
from app.models.user import User
from tests.conftest import register_user

STATUS_PATH = "/api/v1/verification/status"
REQUESTS_PATH = "/api/v1/verification/requests"
DISCOVERY_PATH = "/api/v1/social/discovery"

STATUS_FIELDS = {
    "verification_status",
    "role",
    "social_access_required",
    "latest_request",
}
REQUEST_FIELDS = {"id", "status", "created_at", "reviewed_at", "review_note", "applicant_note"}


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


def _set_state(engine, email: str, state: str) -> None:
    """Set the account verification state directly (test shortcut for
    states the API can only reach through the review flow)."""
    db = _session(engine)
    try:
        user = db.scalar(select(User).where(User.email == email))
        user.verification_status = state
        db.commit()
    finally:
        db.close()


def _submit(api_client, headers, note: str | None = None):
    payload = {} if note is None else {"note": note}
    return api_client.post(REQUESTS_PATH, json=payload, headers=headers)


def _approve_latest(api_client, owner_headers) -> dict:
    """Owner approves the oldest pending request; returns the review body."""
    resp = api_client.get(
        "/api/v1/admin/verification-requests?status=pending", headers=owner_headers
    )
    assert resp.status_code == 200, resp.text
    pending = resp.json()
    assert pending, "expected a pending request in the queue"
    approve = api_client.post(
        f"/api/v1/admin/verification-requests/{pending[0]['id']}/approve",
        json={},
        headers=owner_headers,
    )
    assert approve.status_code == 200, approve.text
    return approve.json()


def _reject_latest(api_client, owner_headers, note: str = "needs clearer photo ID") -> dict:
    """Owner rejects the oldest pending request; returns the review body."""
    resp = api_client.get(
        "/api/v1/admin/verification-requests?status=pending", headers=owner_headers
    )
    assert resp.status_code == 200, resp.text
    pending = resp.json()
    assert pending, "expected a pending request in the queue"
    reject = api_client.post(
        f"/api/v1/admin/verification-requests/{pending[0]['id']}/reject",
        json={"review_note": note},
        headers=owner_headers,
    )
    assert reject.status_code == 200, reject.text
    return reject.json()


# ------------------------------------------------ new accounts + status


def test_new_account_starts_unverified_with_gate_on(api_client):
    """Brief item 1: every new account starts `unverified`, `user`, and
    the default policy requires verification (fail-closed starting point)."""
    _, h = register_user(api_client, "fresh@example.com")
    resp = api_client.get(STATUS_PATH, headers=h)
    assert resp.status_code == 200
    body = resp.json()
    assert body["verification_status"] == "unverified"
    assert body["role"] == "user"
    assert body["social_access_required"] is True  # secure default
    assert body["latest_request"] is None


def test_verification_status_requires_authentication(api_client):
    assert api_client.get(STATUS_PATH).status_code == 401
    assert api_client.post(REQUESTS_PATH, json={}).status_code == 401


def test_status_response_shape_exposes_only_own_safe_fields(api_client):
    """Privacy: the status view carries exactly four fields - no email,
    no password hash, no other account's data."""
    _, h = register_user(api_client, "shape@example.com")
    body = api_client.get(STATUS_PATH, headers=h).json()
    assert set(body) == STATUS_FIELDS
    flat = str(body).lower()
    assert "example.com" not in flat  # no email leaks into the status view
    assert "password" not in flat
    assert "firebase" not in flat


# ------------------------------------------------- self-elevation blocked


def test_register_cannot_send_role_or_verification_status(api_client):
    """A registration body trying to grant itself owner/verified is 422."""
    resp = api_client.post(
        "/api/v1/auth/register",
        json={
            "display_name": "Sneaky",
            "email": "sneaky@example.com",
            "password": "s3cure-Pass!",
            "role": "owner",
            "verification_status": "verified",
        },
    )
    assert resp.status_code == 422
    _, h = register_user(api_client, "legit@example.com")
    body = api_client.get(STATUS_PATH, headers=h).json()
    assert body["role"] == "user" and body["verification_status"] == "unverified"


def test_profile_update_cannot_change_role_or_verification_status(api_client):
    """PATCH /users/me is a strict schema: neither field exists there."""
    _, h = register_user(api_client, "patcher@example.com")
    resp = api_client.patch("/api/v1/users/me", json={"verification_status": "verified"}, headers=h)
    assert resp.status_code == 422
    resp = api_client.patch("/api/v1/users/me", json={"role": "owner"}, headers=h)
    assert resp.status_code == 422
    body = api_client.get(STATUS_PATH, headers=h).json()
    assert body["role"] == "user" and body["verification_status"] == "unverified"


def test_submit_body_cannot_choose_status_or_target_user(api_client):
    """The submit body only accepts an optional `note` - `status` and
    `user_id` are rejected outright (422), so a client can neither mark
    itself verified nor submit on someone else's behalf."""
    _, h = register_user(api_client, "smuggle@example.com")
    resp = api_client.post(REQUESTS_PATH, json={"status": "approved"}, headers=h)
    assert resp.status_code == 422
    resp = api_client.post(REQUESTS_PATH, json={"user_id": "someone-else"}, headers=h)
    assert resp.status_code == 422
    resp = api_client.post(REQUESTS_PATH, json={"role": "owner"}, headers=h)
    assert resp.status_code == 422


# ------------------------------------------------------ submit workflow


def test_submit_moves_account_to_pending_and_records_request(api_client):
    """unverified -> pending happens atomically with the request row."""
    _, h = register_user(api_client, "submit1@example.com")
    resp = _submit(api_client, h, note="  Trip organiser for the Lisbon group  ")
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert set(body) == REQUEST_FIELDS
    assert body["status"] == "pending"
    assert body["applicant_note"] == "Trip organiser for the Lisbon group"  # trimmed
    assert body["reviewed_at"] is None and body["review_note"] is None

    status = api_client.get(STATUS_PATH, headers=h).json()
    assert status["verification_status"] == "pending"
    assert status["latest_request"]["id"] == body["id"]


def test_submit_accepts_empty_body_and_blank_note_collapses(api_client):
    _, h = register_user(api_client, "submit2@example.com")
    resp = api_client.post(REQUESTS_PATH, json={}, headers=h)
    assert resp.status_code == 201, resp.text
    assert resp.json()["applicant_note"] is None

    _, h2 = register_user(api_client, "submit3@example.com")
    resp = api_client.post(REQUESTS_PATH, json={"note": "   "}, headers=h2)
    assert resp.status_code == 201, resp.text
    assert resp.json()["applicant_note"] is None


def test_submit_note_length_is_bounded(api_client):
    _, h = register_user(api_client, "longnote@example.com")
    resp = _submit(api_client, h, note="x" * 201)
    assert resp.status_code == 422


def test_duplicate_submit_while_pending_is_conflict(api_client):
    """Invalid transition: pending -> pending does not exist."""
    _, h = register_user(api_client, "dup@example.com")
    assert _submit(api_client, h).status_code == 201
    resp = _submit(api_client, h)
    assert resp.status_code == 409
    assert "already under review" in resp.json()["detail"]


def test_cannot_submit_when_already_verified(api_client, sqlite_engine):
    """Invalid transition: verified is terminal via the API."""
    _, h = register_user(api_client, "already@example.com")
    _set_state(sqlite_engine, "already@example.com", "verified")
    resp = _submit(api_client, h)
    assert resp.status_code == 409
    assert "already verified" in resp.json()["detail"]


def test_resubmit_after_rejection_is_allowed(api_client, sqlite_engine):
    """rejected -> pending is the documented retry path."""
    owner_h = register_user(api_client, "owner-a@example.com")[1]
    _make_owner(sqlite_engine, "owner-a@example.com")

    _, applicant_h = register_user(api_client, "retry@example.com")
    assert _submit(api_client, applicant_h).status_code == 201
    rejected = _reject_latest(api_client, owner_h, note="document unclear")
    assert rejected["status"] == "rejected"

    status = api_client.get(STATUS_PATH, headers=applicant_h).json()
    assert status["verification_status"] == "rejected"
    assert status["latest_request"]["review_note"] == "document unclear"

    resp = _submit(api_client, applicant_h, note="resubmitted with clearer details")
    assert resp.status_code == 201, resp.text
    assert resp.json()["status"] == "pending"
    assert (
        api_client.get(STATUS_PATH, headers=applicant_h).json()["verification_status"] == "pending"
    )


# ----------------------------------------------------------- the gate


def test_discovery_requires_authentication(api_client):
    assert api_client.get(DISCOVERY_PATH).status_code == 401


def test_unverified_user_denied_discovery(api_client):
    """Brief item 2: default policy -> unverified gets 403 with guidance."""
    _, h = register_user(api_client, "gate-unv@example.com")
    resp = api_client.get(DISCOVERY_PATH, headers=h)
    assert resp.status_code == 403
    detail = resp.json()["detail"]
    assert "verification is required" in detail
    assert "unverified" in detail  # tells the user where they stand


def test_pending_user_denied_discovery(api_client):
    _, h = register_user(api_client, "gate-pend@example.com")
    assert _submit(api_client, h).status_code == 201
    resp = api_client.get(DISCOVERY_PATH, headers=h)
    assert resp.status_code == 403
    assert "pending" in resp.json()["detail"]
    assert "under review" in resp.json()["detail"]


def test_rejected_user_denied_discovery(api_client, sqlite_engine):
    owner_h = register_user(api_client, "owner-b@example.com")[1]
    _make_owner(sqlite_engine, "owner-b@example.com")
    _, applicant_h = register_user(api_client, "gate-rej@example.com")
    assert _submit(api_client, applicant_h).status_code == 201
    _reject_latest(api_client, owner_h)

    resp = api_client.get(DISCOVERY_PATH, headers=applicant_h)
    assert resp.status_code == 403
    assert "rejected" in resp.json()["detail"]


def test_verified_user_passes_gate_after_owner_approval(api_client, sqlite_engine):
    """Brief item 3: the FULL flow - submit, owner approves, access opens.
    No test-only shortcuts: verification only ever happens through review."""
    owner_h = register_user(api_client, "owner-c@example.com")[1]
    _make_owner(sqlite_engine, "owner-c@example.com")

    _, applicant_h = register_user(api_client, "verified@example.com")
    # Denied before...
    assert api_client.get(DISCOVERY_PATH, headers=applicant_h).status_code == 403

    assert _submit(api_client, applicant_h, note="please verify").status_code == 201
    review = _approve_latest(api_client, owner_h)
    assert review["status"] == "approved"
    assert review["reviewed_at"] is not None and review["reviewed_by"]

    status = api_client.get(STATUS_PATH, headers=applicant_h).json()
    assert status["verification_status"] == "verified"

    # ...admitted after.
    resp = api_client.get(DISCOVERY_PATH, headers=applicant_h)
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {"profiles", "message"}
    assert body["profiles"] == []  # placeholder: no fabricated users
    assert "Phase 7" in body["message"]  # honest about what exists


def test_owner_role_itself_does_not_bypass_gate(api_client, sqlite_engine):
    """Being the owner does NOT skip identity verification - the gate
    applies to everyone, and no role value short-circuits it."""
    owner_h = register_user(api_client, "owner-d@example.com")[1]
    _make_owner(sqlite_engine, "owner-d@example.com")
    resp = api_client.get(DISCOVERY_PATH, headers=owner_h)
    assert resp.status_code == 403  # owner is unverified too
    assert "unverified" in resp.json()["detail"]


# ---------------------------------------- safety/account routes stay open


def test_safety_and_account_workflows_stay_open_when_unverified(api_client):
    """Audit result: verification gating applies ONLY to the social
    surface. Contacts, check-ins, SOS, reports, and profile keep working
    for an unverified account - nobody is locked out of safety tools."""
    _, h = register_user(api_client, "safety@example.com")
    # Account
    assert api_client.get("/api/v1/users/me", headers=h).status_code == 200
    # Trusted contact
    contact = api_client.post(
        "/api/v1/trusted-contacts/",
        json={"name": "Mom", "phone": "+911234567890"},
        headers=h,
    )
    assert contact.status_code == 201, contact.text
    # Check-in
    checkin = api_client.post(
        "/api/v1/check-ins/",
        json={"due_at": "2030-01-01T12:00:00Z", "note": "call me at the hostel"},
        headers=h,
    )
    assert checkin.status_code == 201, checkin.text
    # SOS (simulated - no external service is contacted)
    sos = api_client.post(
        "/api/v1/sos",
        json={"description": "unsafe crowd near the hostel gate"},
        headers=h,
    )
    assert sos.status_code == 201, sos.text
    # Community report
    report = api_client.post(
        "/api/v1/reports",
        json={
            "category": "poor_lighting",
            "description": "dark street behind the station",
            "latitude": 28.6139,
            "longitude": 77.2090,
        },
        headers=h,
    )
    assert report.status_code == 201, report.text
    # And none of this changed the verification state.
    status = api_client.get(STATUS_PATH, headers=h).json()
    assert status["verification_status"] == "unverified"


def test_discovery_of_other_users_never_leaks_via_status(api_client, sqlite_engine):
    """Ownership/privacy: status only ever describes the CALLER. Two
    accounts see only themselves; there is no user_id parameter to probe."""
    _, h1 = register_user(api_client, "iso1@example.com")
    _, h2 = register_user(api_client, "iso2@example.com")
    assert _submit(api_client, h1).status_code == 201  # h1 has a request

    body1 = api_client.get(STATUS_PATH, headers=h1).json()
    body2 = api_client.get(STATUS_PATH, headers=h2).json()
    assert body1["latest_request"] is not None
    assert body2["latest_request"] is None  # h2 cannot see h1's request
    # Asking for "someone else's status" is simply not a parameter.
    resp = api_client.get(f"{STATUS_PATH}?user_id=anything", headers=h2)
    assert resp.status_code in (200, 422)
    if resp.status_code == 200:
        assert resp.json()["verification_status"] == "unverified"
