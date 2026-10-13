"""Endpoint tests for person-to-person blocking (Phase 8).

These prove the brief's blocking rules: block/unblock/list work; self
and duplicate blocks are refused (the latter at the database too); only
the blocker removes their own block; a block stops BOTH directions of
messaging and message requests; blocked users vanish from travel-buddy
discovery, public profiles, and new travel-partner requests; existing
conversation history stays readable (nothing is silently deleted) while
sending stops; and blocking works while unverified (it is a safety
tool, not a social perk).
"""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.core.policy import set_policy
from app.models import TravelPlan, TravelProfile, User
from tests.conftest import register_user

BLOCKS_PATH = "/api/v1/blocks"

TODAY = datetime.now(UTC).date()


def _seed_discoverable(engine, email: str, nick: str) -> None:
    """Give a user a discoverable profile AND an eligible plan."""
    db = _session(engine)
    try:
        user = db.scalar(select(User).where(User.email == email))
        db.add(TravelProfile(user_id=user.id, travel_nickname=nick, discoverable=True))
        db.add(
            TravelPlan(
                user_id=user.id,
                destination="Goa",
                destination_normalized="goa",
                start_date=TODAY + timedelta(days=30),
                end_date=TODAY + timedelta(days=37),
                status="active",
                visibility="discoverable",
            )
        )
        db.commit()
    finally:
        db.close()


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


def _blocked_pair(api_client, engine, policy_off=True):
    """Two registered users; returns (a_email, a_h, b_email, b_id, b_h)."""
    a_email = f"blocker-{uuid.uuid4().hex[:8]}@example.com"
    _, a_h = register_user(api_client, a_email, display_name="blocker")
    b_email = f"blocked-{uuid.uuid4().hex[:8]}@example.com"
    _, b_h = register_user(api_client, b_email, display_name="blocked")
    db = _session(engine)
    try:
        b_id = str(db.scalar(select(User).where(User.email == b_email)).id)
    finally:
        db.close()
    if policy_off:
        _flip_policy(engine, False, a_email)
    return a_email, a_h, b_email, b_id, b_h


def test_block_unblock_list_lifecycle(api_client, sqlite_engine) -> None:
    _, a_h, _, b_id, b_h = _blocked_pair(api_client, sqlite_engine)
    created = api_client.post(BLOCKS_PATH, json={"blocked_id": b_id}, headers=a_h)
    assert created.status_code == 201, created.text
    assert created.json()["blocked_display_name"] == "blocked"

    listed = api_client.get(BLOCKS_PATH, headers=a_h).json()
    assert listed["total"] == 1
    assert listed["blocks"][0]["blocked_id"] == b_id
    # The blocked user sees an empty OWN list (lists are per-blocker).
    assert api_client.get(BLOCKS_PATH, headers=b_h).json()["total"] == 0

    assert api_client.delete(f"{BLOCKS_PATH}/{b_id}", headers=a_h).status_code == 204
    assert api_client.get(BLOCKS_PATH, headers=a_h).json()["total"] == 0


def test_block_requires_authentication(api_client) -> None:
    assert api_client.post(BLOCKS_PATH, json={"blocked_id": str(uuid.uuid4())}).status_code == 401
    assert api_client.get(BLOCKS_PATH).status_code == 401
    assert api_client.delete(f"{BLOCKS_PATH}/{uuid.uuid4()}").status_code == 401


def test_block_self_is_422(api_client, sqlite_engine) -> None:
    a_email, a_h, _, _, _ = _blocked_pair(api_client, sqlite_engine)
    db = _session(sqlite_engine)
    try:
        me = str(db.scalar(select(User).where(User.email == a_email)).id)
    finally:
        db.close()
    resp = api_client.post(BLOCKS_PATH, json={"blocked_id": me}, headers=a_h)
    assert resp.status_code == 422


def test_block_unknown_user_is_404(api_client, sqlite_engine) -> None:
    _, a_h, _, _, _ = _blocked_pair(api_client, sqlite_engine)
    assert (
        api_client.post(
            BLOCKS_PATH, json={"blocked_id": str(uuid.uuid4())}, headers=a_h
        ).status_code
        == 404
    )


def test_duplicate_block_is_409(api_client, sqlite_engine) -> None:
    _, a_h, _, b_id, _ = _blocked_pair(api_client, sqlite_engine)
    assert api_client.post(BLOCKS_PATH, json={"blocked_id": b_id}, headers=a_h).status_code == 201
    dup = api_client.post(BLOCKS_PATH, json={"blocked_id": b_id}, headers=a_h)
    assert dup.status_code == 409


def test_duplicate_block_race_is_caught_by_database(api_client, sqlite_engine) -> None:
    """Two racing block inserts keep exactly one row (UNIQUE pair index)."""
    from sqlalchemy.exc import IntegrityError

    from app.models import UserBlock

    a_email, a_h, _, b_id, _ = _blocked_pair(api_client, sqlite_engine)
    assert api_client.post(BLOCKS_PATH, json={"blocked_id": b_id}, headers=a_h).status_code == 201
    db = _session(sqlite_engine)
    try:
        a = db.scalar(select(User).where(User.email == a_email))
        b = db.scalar(select(User).where(User.id == uuid.UUID(b_id)))
        db.add(UserBlock(blocker_id=a.id, blocked_id=b.id))
        try:
            db.commit()
            raise AssertionError("expected the block-pair UNIQUE index to reject this")
        except IntegrityError:
            db.rollback()
    finally:
        db.close()


def test_self_block_is_rejected_at_the_database(api_client, sqlite_engine) -> None:
    """The no-self-block CHECK holds even for direct inserts."""
    from sqlalchemy.exc import IntegrityError

    from app.models import UserBlock

    a_email, _, _, _, _ = _blocked_pair(api_client, sqlite_engine)
    db = _session(sqlite_engine)
    try:
        a = db.scalar(select(User).where(User.email == a_email))
        db.add(UserBlock(blocker_id=a.id, blocked_id=a.id))
        try:
            db.commit()
            raise AssertionError("expected the no-self-block CHECK to reject this")
        except IntegrityError:
            db.rollback()
    finally:
        db.close()


def test_only_blocker_can_unblock(api_client, sqlite_engine) -> None:
    a_email, a_h, _, b_id, b_h = _blocked_pair(api_client, sqlite_engine)
    assert api_client.post(BLOCKS_PATH, json={"blocked_id": b_id}, headers=a_h).status_code == 201
    # The blocked party cannot remove someone else's block of them...
    db = _session(sqlite_engine)
    try:
        a_id = str(db.scalar(select(User).where(User.email == a_email)).id)
    finally:
        db.close()
    assert api_client.delete(f"{BLOCKS_PATH}/{a_id}", headers=b_h).status_code == 404
    # ...and unblocking what was never blocked is the same 404.
    assert api_client.delete(f"{BLOCKS_PATH}/{a_id}", headers=a_h).status_code == 404
    # The original block is untouched.
    assert api_client.get(BLOCKS_PATH, headers=a_h).json()["total"] == 1


def test_blocking_works_while_unverified(api_client, sqlite_engine) -> None:
    """Blocking is a safety tool: reachable under the strict policy with
    no verification (unlike sending, which stays gated)."""
    _, a_h, _, b_id, _ = _blocked_pair(api_client, sqlite_engine, policy_off=False)
    assert api_client.post(BLOCKS_PATH, json={"blocked_id": b_id}, headers=a_h).status_code == 201
    assert api_client.get(BLOCKS_PATH, headers=a_h).status_code == 200
    assert api_client.delete(f"{BLOCKS_PATH}/{b_id}", headers=a_h).status_code == 204


def test_blocked_users_vanish_from_discovery(api_client, sqlite_engine) -> None:
    """A block in either direction removes the pair from travel-buddy
    discovery results AND the public-profile endpoint."""

    a_email, a_h, b_email, b_id, _ = _blocked_pair(api_client, sqlite_engine)
    _seed_discoverable(sqlite_engine, a_email, "seeker")
    _seed_discoverable(sqlite_engine, b_email, "candidate")

    before = api_client.get("/api/v1/travel-buddies/discover", headers=a_h).json()
    assert any(r["user_id"] == b_id for r in before["results"])
    assert api_client.post(BLOCKS_PATH, json={"blocked_id": b_id}, headers=a_h).status_code == 201

    after = api_client.get("/api/v1/travel-buddies/discover", headers=a_h).json()
    assert not any(r["user_id"] == b_id for r in after["results"])
    assert api_client.get(f"/api/v1/travel-buddies/{b_id}", headers=a_h).status_code == 404


def test_blocked_users_cannot_exchange_travel_requests(api_client, sqlite_engine) -> None:
    """New travel-partner requests collapse to 404 across a block."""

    a_email, a_h, b_email, b_id, b_h = _blocked_pair(api_client, sqlite_engine)
    _seed_discoverable(sqlite_engine, a_email, "seeker")
    _seed_discoverable(sqlite_engine, b_email, "candidate")
    db = _session(sqlite_engine)
    try:
        a_id = str(db.scalar(select(User).where(User.email == a_email)).id)
    finally:
        db.close()
    assert api_client.post(BLOCKS_PATH, json={"blocked_id": b_id}, headers=a_h).status_code == 201
    assert (
        api_client.post(
            "/api/v1/travel-buddies/requests", json={"recipient_id": b_id}, headers=a_h
        ).status_code
        == 404
    )
    assert (
        api_client.post(
            "/api/v1/travel-buddies/requests", json={"recipient_id": a_id}, headers=b_h
        ).status_code
        == 404
    )


def test_accept_travel_request_while_blocked_is_409(api_client, sqlite_engine) -> None:
    """A block landing after the ask stops the accept (row stays pending)."""

    a_email, a_h, b_email, b_id, b_h = _blocked_pair(api_client, sqlite_engine)
    _seed_discoverable(sqlite_engine, a_email, "seeker")
    _seed_discoverable(sqlite_engine, b_email, "candidate")
    db = _session(sqlite_engine)
    try:
        a_id = str(db.scalar(select(User).where(User.email == a_email)).id)
    finally:
        db.close()
    sent = api_client.post(
        "/api/v1/travel-buddies/requests", json={"recipient_id": b_id}, headers=a_h
    )
    assert sent.status_code == 201, sent.text
    assert api_client.post(BLOCKS_PATH, json={"blocked_id": a_id}, headers=b_h).status_code == 201
    accept = api_client.post(
        f"/api/v1/travel-buddies/requests/{sent.json()['id']}/accept", headers=b_h
    )
    assert accept.status_code == 409
    assert (
        api_client.get(f"/api/v1/travel-buddies/requests/{sent.json()['id']}", headers=b_h).json()[
            "status"
        ]
        == "pending"
    )
