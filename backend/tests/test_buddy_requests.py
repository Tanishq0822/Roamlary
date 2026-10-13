"""Endpoint tests for the travel-partner request lifecycle (Phase 7).

These prove the request integrity rules the brief demands: self-requests
are refused, duplicate active requests are prevented (including the
reverse direction and the concurrent case), only the recipient can
accept/reject, only the requester can cancel, invalid state transitions
are rejected with 409, non-parties see an identical 404, eligibility is
rechecked at the relevant transitions, and results never leak account
fields.

The verification GATE on the requester (403 while policy is on and the
account is unverified) is proven in test_verification.py and is
re-proved here for POST /travel-buddies/requests.
"""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.core.policy import set_policy
from app.models import TravelPartnerRequest, TravelPlan, TravelProfile, User
from tests.conftest import register_user

REQUESTS_PATH = "/api/v1/travel-buddies/requests"
DISCOVER_PATH = "/api/v1/travel-buddies/discover"

TODAY = datetime.now(UTC).date()


def _session(engine):
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    return factory()


def _set_verification(engine, email: str, state: str) -> None:
    db = _session(engine)
    try:
        user = db.scalar(select(User).where(User.email == email))
        user.verification_status = state
        db.commit()
    finally:
        db.close()


def _flip_policy(engine, required: bool, changed_by_email: str) -> None:
    db = _session(engine)
    try:
        owner = db.scalar(select(User).where(User.email == changed_by_email))
        set_policy(db, value=required, changed_by=owner.id)
        db.commit()
    finally:
        db.close()


def _seed_recipient(
    api_client, engine, tag="recip", *, discoverable=True, destination="Goa"
) -> tuple[str, str, dict]:
    """Register a user with a discoverable profile and plan.

    Returns (user_id, email, auth_headers) so tests can act as that user
    without re-registering (registration is one-shot per email).
    """
    email = f"{tag}-{uuid.uuid4().hex[:8]}@example.com"
    uid, headers = register_user(api_client, email, display_name=tag)
    db = _session(engine)
    try:
        user = db.scalar(select(User).where(User.email == email))
        db.add(TravelProfile(user_id=user.id, travel_nickname=tag, discoverable=discoverable))
        if destination is not None:
            db.add(
                TravelPlan(
                    user_id=user.id,
                    destination=destination,
                    destination_normalized=destination.casefold(),
                    start_date=TODAY + timedelta(days=30),
                    end_date=TODAY + timedelta(days=37),
                    status="active",
                    visibility="discoverable",
                )
            )
        db.commit()
    finally:
        db.close()
    return uid, email, headers


def _id_of(engine, email: str) -> str:
    db = _session(engine)
    try:
        return str(db.scalar(select(User).where(User.email == email)).id)
    finally:
        db.close()


def _plan_id_of(engine, email: str) -> str:
    db = _session(engine)
    try:
        user = db.scalar(select(User).where(User.email == email))
        plan = db.scalar(select(TravelPlan).where(TravelPlan.user_id == user.id))
        return str(plan.id)
    finally:
        db.close()


def _pair(api_client, engine, policy_off=True):
    """Two discoverable users ready to exchange a request.

    Returns (a_email, a_h, b_email, b_id, b_h): the asker's identity and
    headers, plus the recipient's identity, id, and headers. A is also
    given a discoverable profile so B can answer back - send-to-recipient
    eligibility is symmetric.
    """
    a_email = f"asker-{uuid.uuid4().hex[:8]}@example.com"
    _, a_h = register_user(api_client, a_email, display_name="asker")
    b_id, b_email, b_h = _seed_recipient(api_client, engine, tag="answer")
    db = _session(engine)
    try:
        a = db.scalar(select(User).where(User.email == a_email))
        db.add(TravelProfile(user_id=a.id, travel_nickname="asker", discoverable=True))
        db.commit()
    finally:
        db.close()
    if policy_off:
        _flip_policy(engine, False, a_email)
    return a_email, a_h, b_email, b_id, b_h


# --- sending ---------------------------------------------------------------


def test_send_requires_authentication(api_client) -> None:
    assert (
        api_client.post(REQUESTS_PATH, json={"recipient_id": str(uuid.uuid4())}).status_code == 401
    )


def test_send_gate_denies_unverified_when_policy_on(api_client, sqlite_engine) -> None:
    """While policy is on, an unverified requester is denied with 403."""
    asker = f"gate-{uuid.uuid4().hex[:8]}@example.com"
    _, asker_h = register_user(api_client, asker, display_name="gate")
    recipient_id, recipient_email, _ = _seed_recipient(api_client, sqlite_engine)
    _flip_policy(sqlite_engine, True, recipient_email)
    # asker stays unverified (default) while recipient is verified.
    _set_verification(sqlite_engine, recipient_email, "verified")

    resp = api_client.post(REQUESTS_PATH, json={"recipient_id": recipient_id}, headers=asker_h)
    assert resp.status_code == 403
    assert "verification" in resp.json()["detail"].lower()


def test_send_valid_request_is_201_and_pending(api_client, sqlite_engine) -> None:
    _, h, b_email, b_id, _ = _pair(api_client, sqlite_engine)
    resp = api_client.post(REQUESTS_PATH, json={"recipient_id": b_id}, headers=h)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["status"] == "pending"
    assert data["recipient_display_name"] == "answer"
    assert data["plan_id"] is None  # plan-agnostic request
    assert data["responded_at"] is None


def test_send_to_self_is_422(api_client, sqlite_engine) -> None:
    a_email, h, _, _, _ = _pair(api_client, sqlite_engine)
    my_id = _id_of(sqlite_engine, a_email)
    resp = api_client.post(REQUESTS_PATH, json={"recipient_id": my_id}, headers=h)
    assert resp.status_code == 422
    assert "yourself" in resp.json()["detail"]


def test_send_to_nonexistent_or_hidden_or_unverified_is_404(api_client, sqlite_engine) -> None:
    a_email, h, _, _, _ = _pair(api_client, sqlite_engine, policy_off=False)
    _flip_policy(sqlite_engine, True, a_email)
    _set_verification(sqlite_engine, a_email, "verified")

    hidden_id, hidden_email, _ = _seed_recipient(
        api_client, sqlite_engine, tag="hidden", discoverable=False
    )
    plain_id, plain_email, _ = _seed_recipient(api_client, sqlite_engine, tag="plain")
    _set_verification(sqlite_engine, plain_email, "unverified")

    unknown = api_client.post(REQUESTS_PATH, json={"recipient_id": str(uuid.uuid4())}, headers=h)
    hidden = api_client.post(REQUESTS_PATH, json={"recipient_id": hidden_id}, headers=h)
    unverified = api_client.post(REQUESTS_PATH, json={"recipient_id": plain_id}, headers=h)
    assert unknown.status_code == hidden.status_code == unverified.status_code == 404
    # Identical bodies: eligibility cannot be probed.
    assert unknown.json() == hidden.json() == unverified.json()


def test_duplicate_pending_in_either_direction_is_409(api_client, sqlite_engine) -> None:
    a_email, a_h, b_email, b_id, b_h = _pair(api_client, sqlite_engine)
    first = api_client.post(REQUESTS_PATH, json={"recipient_id": b_id}, headers=a_h)
    assert first.status_code == 201
    # Same direction again -> 409.
    again = api_client.post(REQUESTS_PATH, json={"recipient_id": b_id}, headers=a_h)
    assert again.status_code == 409

    # Reverse direction (B -> A) while A -> B is pending -> also 409.
    a_id = _id_of(sqlite_engine, a_email)
    reverse = api_client.post(REQUESTS_PATH, json={"recipient_id": a_id}, headers=b_h)
    assert reverse.status_code == 409


def test_accepted_pair_cannot_request_again(api_client, sqlite_engine) -> None:
    a_email, a_h, b_email, b_id, _ = _pair(api_client, sqlite_engine)
    db = _session(sqlite_engine)
    try:
        a = db.scalar(select(User).where(User.email == a_email))
        b = db.scalar(select(User).where(User.email == b_email))
        db.add(TravelPartnerRequest(requester_id=a.id, recipient_id=b.id, status="accepted"))
        db.commit()
    finally:
        db.close()
    resp = api_client.post(REQUESTS_PATH, json={"recipient_id": b_id}, headers=a_h)
    assert resp.status_code == 409
    assert "already travel partners" in resp.json()["detail"]


def test_send_with_plan_context_validates_ownership_and_eligibility(
    api_client, sqlite_engine
) -> None:
    a_email, a_h, b_email, b_id, _ = _pair(api_client, sqlite_engine)
    b_plan = _plan_id_of(sqlite_engine, b_email)

    # Valid: the recipient's own discoverable plan as context.
    ok = api_client.post(REQUESTS_PATH, json={"recipient_id": b_id, "plan_id": b_plan}, headers=a_h)
    assert ok.status_code == 201, ok.text
    assert ok.json()["plan_destination"] == "Goa"

    # Invalid: someone else's plan id (or a bogus one) -> same 404.
    bogus = api_client.post(
        REQUESTS_PATH, json={"recipient_id": b_id, "plan_id": str(uuid.uuid4())}, headers=a_h
    )
    assert bogus.status_code == 404


def test_send_rate_limited_after_burst(api_client, sqlite_engine) -> None:
    from app.core.rate_limit import reset_rate_limits

    reset_rate_limits()
    a_email, a_h, _, _, _ = _pair(api_client, sqlite_engine)
    # Each burst recipient must be eligible (discoverable + plan), or the
    # send would 404 before ever reaching the rate limiter.
    allowed = 0
    blocked = None
    for i in range(32):
        rid, _, _ = _seed_recipient(api_client, sqlite_engine, tag=f"burst{i}")
        resp = api_client.post(REQUESTS_PATH, json={"recipient_id": rid}, headers=a_h)
        if resp.status_code == 201:
            allowed += 1
        elif resp.status_code == 429:
            blocked = resp
            break
    assert allowed == 30, f"expected 30 allowed before limiting, got {allowed}"
    assert blocked is not None and blocked.status_code == 429
    reset_rate_limits()


# --- listing and inspection ------------------------------------------------


def test_list_incoming_outgoing_and_status_filter(api_client, sqlite_engine) -> None:
    a_email, a_h, b_email, b_id, b_h = _pair(api_client, sqlite_engine)
    api_client.post(REQUESTS_PATH, json={"recipient_id": b_id}, headers=a_h)

    outgoing = api_client.get(f"{REQUESTS_PATH}?direction=outgoing", headers=a_h).json()
    assert outgoing["total"] == 1
    assert outgoing["results"][0]["status"] == "pending"

    incoming = api_client.get(f"{REQUESTS_PATH}?direction=incoming", headers=b_h).json()
    assert incoming["total"] == 1
    assert incoming["results"][0]["requester_display_name"] == "asker"

    # Filtering by a status with no matches -> empty, not an error.
    none = api_client.get(
        f"{REQUESTS_PATH}?direction=outgoing&request_status=accepted", headers=a_h
    )
    assert none.status_code == 200 and none.json()["total"] == 0

    # Invalid direction -> 422.
    assert api_client.get(f"{REQUESTS_PATH}?direction=sideways", headers=a_h).status_code == 422


def test_inspect_one_request_parties_only(api_client, sqlite_engine) -> None:
    a_email, a_h, b_email, b_id, b_h = _pair(api_client, sqlite_engine)
    sent = api_client.post(REQUESTS_PATH, json={"recipient_id": b_id}, headers=a_h).json()

    both = {
        api_client.get(f"{REQUESTS_PATH}/{sent['id']}", headers=a_h).status_code,
        api_client.get(f"{REQUESTS_PATH}/{sent['id']}", headers=b_h).status_code,
    }
    assert both == {200}

    # A stranger gets the same 404 as an unknown id (existence privacy).
    _, stranger_h = register_user(api_client, f"stranger-{uuid.uuid4().hex[:8]}@example.com")
    stranger = api_client.get(f"{REQUESTS_PATH}/{sent['id']}", headers=stranger_h)
    missing = api_client.get(f"{REQUESTS_PATH}/{uuid.uuid4()}", headers=a_h)
    assert stranger.status_code == missing.status_code == 404
    assert stranger.json() == missing.json()


# --- state transitions -----------------------------------------------------


def _pending_request(api_client, sqlite_engine):
    a_email, a_h, b_email, b_id, b_h = _pair(api_client, sqlite_engine)
    sent = api_client.post(REQUESTS_PATH, json={"recipient_id": b_id}, headers=a_h).json()
    return sent, a_h, b_h


def test_accept_by_recipient_only(api_client, sqlite_engine) -> None:
    sent, a_h, b_h = _pending_request(api_client, sqlite_engine)
    # The requester cannot accept their own request (404, existence privacy).
    wrong = api_client.post(f"{REQUESTS_PATH}/{sent['id']}/accept", headers=a_h)
    assert wrong.status_code == 404
    ok = api_client.post(f"{REQUESTS_PATH}/{sent['id']}/accept", headers=b_h)
    assert ok.status_code == 200, ok.text
    body = ok.json()
    assert body["status"] == "accepted"
    assert body["responded_at"] is not None


def test_reject_by_recipient_only(api_client, sqlite_engine) -> None:
    sent, a_h, b_h = _pending_request(api_client, sqlite_engine)
    wrong = api_client.post(f"{REQUESTS_PATH}/{sent['id']}/reject", headers=a_h)
    assert wrong.status_code == 404
    ok = api_client.post(f"{REQUESTS_PATH}/{sent['id']}/reject", headers=b_h)
    assert ok.status_code == 200
    assert ok.json()["status"] == "rejected"


def test_cancel_by_requester_only(api_client, sqlite_engine) -> None:
    sent, a_h, b_h = _pending_request(api_client, sqlite_engine)
    wrong = api_client.post(f"{REQUESTS_PATH}/{sent['id']}/cancel", headers=b_h)
    assert wrong.status_code == 404
    ok = api_client.post(f"{REQUESTS_PATH}/{sent['id']}/cancel", headers=a_h)
    assert ok.status_code == 200
    assert ok.json()["status"] == "cancelled"


def test_terminal_states_refuse_further_moves(api_client, sqlite_engine) -> None:
    sent, a_h, b_h = _pending_request(api_client, sqlite_engine)
    accepted = api_client.post(f"{REQUESTS_PATH}/{sent['id']}/accept", headers=b_h)
    assert accepted.status_code == 200

    # From 'accepted': the recipient cannot accept or reject again (409),
    # and the requester cannot cancel (409 - right party, wrong state).
    for action in ("reject", "accept"):
        resp = api_client.post(f"{REQUESTS_PATH}/{sent['id']}/{action}", headers=b_h)
        assert resp.status_code == 409, (action, resp.text)
    # And the requester cannot cancel an accepted request either.
    assert api_client.post(f"{REQUESTS_PATH}/{sent['id']}/cancel", headers=a_h).status_code == 409


def test_resend_after_rejection_is_allowed(api_client, sqlite_engine) -> None:
    """A rejected request does not permanently block a new attempt."""
    sent, a_h, b_h = _pending_request(api_client, sqlite_engine)
    assert api_client.post(f"{REQUESTS_PATH}/{sent['id']}/reject", headers=b_h).status_code == 200
    b_id = sent["recipient_id"]
    resend = api_client.post(REQUESTS_PATH, json={"recipient_id": b_id}, headers=a_h)
    assert resend.status_code == 201


def test_accept_rechecks_requester_eligibility(api_client, sqlite_engine) -> None:
    """If the requester's verification lapses, accept fails and stays pending."""
    a_email = f"elig-{uuid.uuid4().hex[:8]}@example.com"
    _, a_h = register_user(api_client, a_email, display_name="elig")
    b_id, b_email, b_h = _seed_recipient(api_client, sqlite_engine, tag="stable")
    _flip_policy(sqlite_engine, True, a_email)
    _set_verification(sqlite_engine, a_email, "verified")
    _set_verification(sqlite_engine, b_email, "verified")

    sent = api_client.post(REQUESTS_PATH, json={"recipient_id": b_id}, headers=a_h).json()
    # Requester's verification lapses (server-side review outcome).
    _set_verification(sqlite_engine, a_email, "rejected")

    accept = api_client.post(f"{REQUESTS_PATH}/{sent['id']}/accept", headers=b_h)
    assert accept.status_code == 409
    assert "no longer eligible" in accept.json()["detail"]
    # The request is still pending, so the recipient can still reject it.
    still = api_client.get(f"{REQUESTS_PATH}/{sent['id']}", headers=b_h).json()
    assert still["status"] == "pending"
    assert api_client.post(f"{REQUESTS_PATH}/{sent['id']}/reject", headers=b_h).status_code == 200


def test_duplicate_insert_race_is_caught_by_database(api_client, sqlite_engine) -> None:
    """Concurrent duplicate submissions cannot create two pending rows.

    The UNIQUE indexes are the source of truth: inserting a second
    pending row with the same directed key - bypassing the endpoint
    pre-check, exactly as a racing request would - raises
    IntegrityError (per-direction indexes). Phase 8 closed the
    cross-direction race the same way: the canonical-pair pending index
    rejects a simultaneous opposite-direction insert at the database
    (the last assertion below is that fix, proven with raw inserts).
    """
    from sqlalchemy.exc import IntegrityError

    from app.core.pairing import canonical_pair

    a_email, a_h, b_email, b_id, _ = _pair(api_client, sqlite_engine)
    assert (
        api_client.post(REQUESTS_PATH, json={"recipient_id": b_id}, headers=a_h).status_code == 201
    )

    db = _session(sqlite_engine)
    try:
        a = db.scalar(select(User).where(User.email == a_email))
        b = db.scalar(select(User).where(User.email == b_email))
        low, high = canonical_pair(a.id, b.id)
        # Same-direction duplicate loses at the database.
        db.add(
            TravelPartnerRequest(
                requester_id=a.id,
                recipient_id=b.id,
                status="pending",
                pair_low_id=low,
                pair_high_id=high,
            )
        )
        try:
            db.commit()
            raise AssertionError("expected the pending-pair UNIQUE index to reject this")
        except IntegrityError:
            db.rollback()
        # Cross-direction duplicate ALSO loses at the database now (the
        # Phase 8 canonical-pair index): a racing B->A send cannot land
        # while A->B is pending, even past the endpoint pre-check.
        db.add(
            TravelPartnerRequest(
                requester_id=b.id,
                recipient_id=a.id,
                status="pending",
                pair_low_id=low,
                pair_high_id=high,
            )
        )
        try:
            db.commit()
            raise AssertionError("expected the canonical-pair UNIQUE index to reject this")
        except IntegrityError:
            db.rollback()
    finally:
        db.close()


def test_self_request_is_blocked_at_the_database(api_client, sqlite_engine) -> None:
    """The no-self-request CHECK holds even for direct inserts."""
    from sqlalchemy.exc import IntegrityError

    a_email, _, _, _, _ = _pair(api_client, sqlite_engine)
    db = _session(sqlite_engine)
    try:
        a = db.scalar(select(User).where(User.email == a_email))
        db.add(TravelPartnerRequest(requester_id=a.id, recipient_id=a.id, status="pending"))
        try:
            db.commit()
            raise AssertionError("expected the no-self-request CHECK to reject this")
        except IntegrityError:
            db.rollback()
    finally:
        db.close()


def test_requests_hide_account_fields(api_client, sqlite_engine) -> None:
    sent, a_h, b_h = _pending_request(api_client, sqlite_engine)
    forbidden = {"email", "phone", "role", "verification_status", "password"}
    assert forbidden.isdisjoint(sent.keys())
    incoming = api_client.get(f"{REQUESTS_PATH}?direction=incoming", headers=b_h).json()
    assert forbidden.isdisjoint(incoming["results"][0].keys())


def test_social_discovery_broad_feed_returns_real_profiles(api_client, sqlite_engine) -> None:
    """The Phase 6 route keeps its gate and contract, now with real data."""
    a_email = f"feed-{uuid.uuid4().hex[:8]}@example.com"
    _, a_h = register_user(api_client, a_email, display_name="feed")
    _flip_policy(sqlite_engine, False, a_email)
    _seed_recipient(api_client, sqlite_engine, tag="visible", destination="Goa")
    _seed_recipient(api_client, sqlite_engine, tag="invisible", discoverable=False)

    resp = api_client.get("/api/v1/social/discovery", headers=a_h)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert set(body.keys()) == {"profiles", "message"}  # unchanged Phase 6 contract
    assert len(body["profiles"]) == 1  # hidden profile excluded
    assert body["profiles"][0]["display_name"] == "visible"
    assert "not a guarantee" in body["message"]
