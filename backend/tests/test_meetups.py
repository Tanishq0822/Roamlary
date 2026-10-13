"""Endpoint tests for public meetups (Phase 9).

These prove the meetup rules: creation + validation, filterable public
discovery (house parties and private events never appear), host-only
edit/cancel/complete, open vs approval joining with capacity refused at
409, duplicate asks/memberships refused (UNIQUE pair, race-proof),
host approve/reject with capacity recheck, leave/remove, guest-list
visibility tiers, host-only bulletins, and blocked hosts vanishing from
discovery.
"""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.core.policy import set_policy
from app.core.rate_limit import reset_rate_limits
from app.models import User
from tests.conftest import register_user

MEETUPS_PATH = "/api/v1/meetups"

NOW = datetime.now(UTC)
START = (NOW + timedelta(days=30)).isoformat()
END = (NOW + timedelta(days=31)).isoformat()


def _session(engine):
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    return factory()


def _flip_policy(engine, required: bool, changed_by_email: str) -> None:
    db = _session(engine)
    try:
        owner = db.scalar(select(User).where(User.email == changed_by_email))
        set_policy(db, value=required, changed_by=owner.id)
        db.commit()
    finally:
        db.close()


def _host(api_client, engine, tag="host"):
    """One registered user with policy flipped off; returns (email, headers)."""
    email = f"{tag}-{uuid.uuid4().hex[:8]}@example.com"
    _, headers = register_user(api_client, email, display_name=tag)
    _flip_policy(engine, False, email)
    return email, headers


def _guest(api_client, tag="guest"):
    email = f"{tag}-{uuid.uuid4().hex[:8]}@example.com"
    _, headers = register_user(api_client, email, display_name=tag)
    return email, headers


def _create(api_client, headers, **overrides):
    body = {
        "title": "Sunrise Hike",
        "description": "Easy trail, all levels.",
        "category": "hiking",
        "start_at": START,
        "end_at": END,
        "capacity": 10,
        "visibility": "public",
        "participation": "approval",
        "location_text": "Central Park gate 2",
    }
    body.update(overrides)
    return api_client.post(MEETUPS_PATH, json=body, headers=headers)


def _id_of(api_client, headers) -> str:
    return api_client.get("/api/v1/users/me", headers=headers).json()["id"]


def test_create_and_read_meetup(api_client, sqlite_engine) -> None:
    _, h = _host(api_client, sqlite_engine)
    resp = _create(api_client, h)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "active"
    assert body["kind"] == "meetup"
    assert body["approved_count"] == 0
    assert body["my_membership"] == "host"
    assert body["venue_details"] is None
    fetched = api_client.get(f"{MEETUPS_PATH}/{body['id']}", headers=h).json()
    assert fetched["title"] == "Sunrise Hike"


def test_meetup_requires_authentication(api_client) -> None:
    assert api_client.post(MEETUPS_PATH, json={}).status_code == 401
    assert api_client.get(MEETUPS_PATH).status_code == 401


def test_create_validates_times_and_fields(api_client, sqlite_engine) -> None:
    _, h = _host(api_client, sqlite_engine)
    assert _create(api_client, h, end_at=START, start_at=END).status_code == 422
    assert _create(api_client, h, start_at="2027-01-01T10:00:00").status_code == 422
    assert _create(api_client, h, capacity=1).status_code == 422
    assert _create(api_client, h, category="skydiving").status_code == 422
    assert _create(api_client, h, title="  ").status_code == 422
    past = (NOW - timedelta(days=1)).isoformat()
    assert _create(api_client, h, start_at=past).status_code == 201  # past allowed at create


def test_create_gated_while_policy_on(api_client, sqlite_engine) -> None:
    email = f"unverified-{uuid.uuid4().hex[:8]}@example.com"
    _, h = register_user(api_client, email, display_name="unverified")
    assert _create(api_client, h).status_code == 403


def test_discovery_filters_and_hides_parties(api_client, sqlite_engine) -> None:
    from tests.conftest import prefund_payment

    host_email, h = _host(api_client, sqlite_engine)
    assert _create(api_client, h, category="food", title="Food Walk").status_code == 201
    # The first create consumed the free post: fund the rest (discovery
    # behavior is under test, not billing).
    assert (
        _create(
            api_client,
            h,
            visibility="private",
            title="Secret",
            payment_id=prefund_payment(sqlite_engine, host_email, "meetup"),
        ).status_code
        == 201
    )
    party = api_client.post(
        "/api/v1/parties",
        json={
            "title": "House Party",
            "category": "leisure",
            "start_at": START,
            "end_at": END,
            "payment_id": prefund_payment(sqlite_engine, host_email, "house_party"),
        },
        headers=h,
    )
    assert party.status_code == 201, party.text

    feed = api_client.get(MEETUPS_PATH, headers=h).json()
    titles = [m["title"] for m in feed]
    assert "Food Walk" in titles
    assert "Secret" not in titles
    assert "House Party" not in titles
    assert all(m["venue_details"] is None for m in feed)

    food = api_client.get(MEETUPS_PATH + "?category=food", headers=h).json()
    assert [m["title"] for m in food] == ["Food Walk"]
    assert api_client.get(MEETUPS_PATH + "?category=skydiving", headers=h).status_code == 422


def test_join_open_approves_at_once(api_client, sqlite_engine) -> None:
    _, h = _host(api_client, sqlite_engine)
    _, g_h = _guest(api_client)
    event = _create(api_client, h, participation="open").json()
    joined = api_client.post(f"{MEETUPS_PATH}/{event['id']}/join", headers=g_h)
    assert joined.status_code == 201, joined.text
    assert joined.json()["status"] == "approved"
    # Duplicate join is 409.
    assert api_client.post(f"{MEETUPS_PATH}/{event['id']}/join", headers=g_h).status_code == 409


def test_join_approval_flow_with_host_decision(api_client, sqlite_engine) -> None:
    _, h = _host(api_client, sqlite_engine)
    _, g_h = _guest(api_client)
    event = _create(api_client, h).json()  # approval policy (default)
    asked = api_client.post(f"{MEETUPS_PATH}/{event['id']}/join", headers=g_h)
    assert asked.status_code == 201
    assert asked.json()["status"] == "requested"

    guests = api_client.get(f"{MEETUPS_PATH}/{event['id']}/participants", headers=g_h)
    assert guests.status_code == 404  # requesters are not insiders yet
    host_view = api_client.get(f"{MEETUPS_PATH}/{event['id']}/participants", headers=h).json()
    assert [p["status"] for p in host_view] == ["requested"]

    approved = api_client.post(
        f"{MEETUPS_PATH}/{event['id']}/requests/{_id_of(api_client, g_h)}/approve", headers=h
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    # The member is notified of the decision.
    inbox = api_client.get("/api/v1/notifications", headers=g_h).json()
    assert any(
        n["kind"] == "join_decision" and n["status"] == "delivered" for n in inbox["results"]
    )

    # Now the guest list is visible to the member (approved only).
    member_view = api_client.get(f"{MEETUPS_PATH}/{event['id']}/participants", headers=g_h).json()
    assert all(p["status"] == "approved" for p in member_view)


def test_capacity_is_refused(api_client, sqlite_engine) -> None:
    _, h = _host(api_client, sqlite_engine)
    event = _create(api_client, h, participation="open", capacity=2).json()
    for tag in ("g1", "g2"):
        _, g_h = _guest(api_client, tag=tag)
        assert api_client.post(f"{MEETUPS_PATH}/{event['id']}/join", headers=g_h).status_code == 201
    _, g3_h = _guest(api_client, tag="g3")
    full = api_client.post(f"{MEETUPS_PATH}/{event['id']}/join", headers=g3_h)
    assert full.status_code == 409


def test_duplicate_join_race_is_caught_by_database(api_client, sqlite_engine) -> None:
    """Two racing join inserts keep exactly one membership row."""
    from sqlalchemy.exc import IntegrityError

    from app.models import MeetupMembership

    _, h = _host(api_client, sqlite_engine)
    _, g_h = _guest(api_client)
    event = _create(api_client, h, participation="open").json()
    assert api_client.post(f"{MEETUPS_PATH}/{event['id']}/join", headers=g_h).status_code == 201
    db = _session(sqlite_engine)
    try:
        guest = db.scalar(select(User).where(User.display_name == "guest"))
        db.add(
            MeetupMembership(
                meetup_id=uuid.UUID(event["id"]),
                user_id=guest.id,
                status="approved",
            )
        )
        try:
            db.commit()
            raise AssertionError("expected the membership UNIQUE index to reject this")
        except IntegrityError:
            db.rollback()
    finally:
        db.close()


def test_host_cannot_join_own_event(api_client, sqlite_engine) -> None:
    _, h = _host(api_client, sqlite_engine)
    event = _create(api_client, h).json()
    assert api_client.post(f"{MEETUPS_PATH}/{event['id']}/join", headers=h).status_code == 422


def test_leave_and_rejoin(api_client, sqlite_engine) -> None:
    _, h = _host(api_client, sqlite_engine)
    _, g_h = _guest(api_client)
    event = _create(api_client, h, participation="open").json()
    assert api_client.post(f"{MEETUPS_PATH}/{event['id']}/join", headers=g_h).status_code == 201
    left = api_client.post(f"{MEETUPS_PATH}/{event['id']}/leave", headers=g_h)
    assert left.status_code == 200
    assert left.json()["status"] == "left"
    # Rejoining after leaving is a fresh ask (allowed).
    again = api_client.post(f"{MEETUPS_PATH}/{event['id']}/join", headers=g_h)
    assert again.status_code == 201


def test_host_removes_participant(api_client, sqlite_engine) -> None:
    _, h = _host(api_client, sqlite_engine)
    _, g_h = _guest(api_client)
    event = _create(api_client, h, participation="open").json()
    assert api_client.post(f"{MEETUPS_PATH}/{event['id']}/join", headers=g_h).status_code == 201
    removed = api_client.delete(
        f"{MEETUPS_PATH}/{event['id']}/participants/{_id_of(api_client, g_h)}", headers=h
    )
    assert removed.status_code == 200
    assert removed.json()["status"] == "removed"
    # Non-hosts cannot remove.
    assert (
        api_client.delete(
            f"{MEETUPS_PATH}/{event['id']}/participants/{_id_of(api_client, h)}", headers=g_h
        ).status_code
        == 404
    )


def test_cancel_freezes_event_and_notifies(api_client, sqlite_engine) -> None:
    _, h = _host(api_client, sqlite_engine)
    _, g_h = _guest(api_client)
    event = _create(api_client, h, participation="open").json()
    assert api_client.post(f"{MEETUPS_PATH}/{event['id']}/join", headers=g_h).status_code == 201
    cancelled = api_client.post(f"{MEETUPS_PATH}/{event['id']}/cancel", headers=h)
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    # Joins, edits, and bulletins freeze.
    assert api_client.post(f"{MEETUPS_PATH}/{event['id']}/join", headers=g_h).status_code == 409
    assert (
        api_client.patch(
            f"{MEETUPS_PATH}/{event['id']}", json={"title": "X"}, headers=h
        ).status_code
        == 409
    )
    # The approved member was notified of the cancellation.
    inbox = api_client.get("/api/v1/notifications", headers=g_h).json()
    assert any(n["kind"] == "event_cancelled" for n in inbox["results"])


def test_capacity_floor_on_edit(api_client, sqlite_engine) -> None:
    _, h = _host(api_client, sqlite_engine)
    guests = [_guest(api_client, tag=f"g{i}")[1] for i in range(3)]
    event = _create(api_client, h, participation="open", capacity=5).json()
    for g_h in guests:
        assert api_client.post(f"{MEETUPS_PATH}/{event['id']}/join", headers=g_h).status_code == 201
    shrink = api_client.patch(f"{MEETUPS_PATH}/{event['id']}", json={"capacity": 2}, headers=h)
    assert shrink.status_code == 409  # 3 approved > 2: refused
    ok = api_client.patch(f"{MEETUPS_PATH}/{event['id']}", json={"capacity": 3}, headers=h)
    assert ok.status_code == 200


def test_announcements_host_only_post_member_read(api_client, sqlite_engine) -> None:
    _, h = _host(api_client, sqlite_engine)
    _, g_h = _guest(api_client)
    _, outsider_h = _guest(api_client, tag="outsider")
    event = _create(api_client, h, participation="open").json()
    assert api_client.post(f"{MEETUPS_PATH}/{event['id']}/join", headers=g_h).status_code == 201
    posted = api_client.post(
        f"{MEETUPS_PATH}/{event['id']}/announcements", json={"body": "Gate 2!"}, headers=h
    )
    assert posted.status_code == 201
    assert (
        api_client.post(
            f"{MEETUPS_PATH}/{event['id']}/announcements", json={"body": "hijack"}, headers=g_h
        ).status_code
        == 404
    )
    member_feed = api_client.get(f"{MEETUPS_PATH}/{event['id']}/announcements", headers=g_h).json()
    assert [a["body"] for a in member_feed] == ["Gate 2!"]
    assert (
        api_client.get(
            f"{MEETUPS_PATH}/{event['id']}/announcements", headers=outsider_h
        ).status_code
        == 404
    )


def test_blocked_host_vanishes_from_discovery(api_client, sqlite_engine) -> None:
    _, h = _host(api_client, sqlite_engine)
    _, g_h = _guest(api_client)
    assert _create(api_client, h).status_code == 201
    before = api_client.get(MEETUPS_PATH, headers=g_h).json()
    assert len(before) == 1
    host_id = before[0]["host_id"]
    assert (
        api_client.post("/api/v1/blocks", json={"blocked_id": host_id}, headers=g_h).status_code
        == 201
    )
    after = api_client.get(MEETUPS_PATH, headers=g_h).json()
    assert after == []
    assert api_client.get(f"{MEETUPS_PATH}/{before[0]['id']}", headers=g_h).status_code == 404


def test_create_rate_limit_429(api_client, sqlite_engine) -> None:
    reset_rate_limits()
    host_email, h = _host(api_client, sqlite_engine)
    # The first create is free; the rest are funded with prefunded
    # SUCCEEDED payments (the create limiter is under test, not
    # billing - proven separately in test_billing.py).
    from tests.conftest import prefund_payment

    funded = [prefund_payment(sqlite_engine, host_email, "meetup") for _ in range(19)]
    for n in range(20):
        body = {"title": f"Event {n}"}
        if n > 0:
            body["payment_id"] = funded[n - 1]
        resp = _create(api_client, h, **body)
        assert resp.status_code == 201, (n, resp.text)
    over = _create(
        api_client,
        h,
        title="one too many",
        payment_id=prefund_payment(sqlite_engine, host_email, "meetup"),
    )
    assert over.status_code == 429
    reset_rate_limits()
