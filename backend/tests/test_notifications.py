"""Tests for the notification inbox + retry (Phase 12A) and trip sharing (Phase 12B).

Notifications: the inbox lists only the caller's rows; read stamps are
idempotent and server-clocked; retries re-attempt the SAME row and
refuse non-retryable states; foreign ids 404 identically.
Trip shares: bounded creation (own plans only, future expiry ≤90d),
owner history, revocation semantics, viewer = accepted partners only,
server-side expiry enforcement, and no live-location claims anywhere.
"""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.core.policy import set_policy
from app.models import TravelProfile, User
from tests.conftest import register_user

NOTIFICATIONS_PATH = "/api/v1/notifications"
SHARES_PATH = "/api/v1/trip-shares"

NOW = datetime.now(UTC)


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


def _user(api_client, engine, tag="user", policy_off=True):
    email = f"{tag}-{uuid.uuid4().hex[:8]}@example.com"
    _, headers = register_user(api_client, email, display_name=tag)
    if policy_off:
        _flip_policy(engine, False, email)
    return email, headers


def _id_of(api_client, headers) -> str:
    return api_client.get("/api/v1/users/me", headers=headers).json()["id"]


def test_inbox_lists_reads_and_retries(api_client, sqlite_engine) -> None:
    _, h = _user(api_client, sqlite_engine)
    # No rows yet: empty inbox (not 404).
    empty = api_client.get(NOTIFICATIONS_PATH, headers=h).json()
    assert empty["total"] == 0

    assert api_client.get(NOTIFICATIONS_PATH).status_code == 401
    assert api_client.post(f"{NOTIFICATIONS_PATH}/{uuid.uuid4()}/read").status_code == 401


def test_notification_read_and_retry_states(api_client, sqlite_engine) -> None:
    from app.services.notifications import record_notification

    email, h = _user(api_client, sqlite_engine)
    db = _session(sqlite_engine)
    try:
        user = db.scalar(select(User).where(User.email == email))
        row = record_notification(
            db,
            user_id=user.id,
            kind="trip_shared",
            title="Trip shared",
            body="Someone shared a trip.",
            idempotency_key=f"test:{uuid.uuid4().hex}",
        )
        row_id = str(row.id)
    finally:
        db.close()

    listed = api_client.get(NOTIFICATIONS_PATH, headers=h).json()
    assert listed["total"] == 1
    assert listed["results"][0]["status"] == "delivered"  # in-app rows ARE delivered
    read = api_client.post(f"{NOTIFICATIONS_PATH}/{row_id}/read", headers=h)
    assert read.status_code == 200
    assert read.json()["read_at"] is not None
    unread = api_client.get(NOTIFICATIONS_PATH + "?unread_only=true", headers=h).json()
    assert unread["total"] == 0
    # Delivered rows have nothing to retry.
    assert api_client.post(f"{NOTIFICATIONS_PATH}/{row_id}/retry", headers=h).status_code == 409


def test_notification_ids_do_not_cross_users(api_client, sqlite_engine) -> None:
    from app.services.notifications import record_notification

    email, h = _user(api_client, sqlite_engine)
    _, other_h = _user(api_client, sqlite_engine, tag="other")
    db = _session(sqlite_engine)
    try:
        user = db.scalar(select(User).where(User.email == email))
        row = record_notification(
            db,
            user_id=user.id,
            kind="trip_shared",
            title="Trip shared",
            body="Someone shared a trip.",
            idempotency_key=f"test:{uuid.uuid4().hex}",
        )
        row_id = str(row.id)
    finally:
        db.close()
    assert (
        api_client.post(f"{NOTIFICATIONS_PATH}/{row_id}/read", headers=other_h).status_code == 404
    )
    assert (
        api_client.post(f"{NOTIFICATIONS_PATH}/{row_id}/retry", headers=other_h).status_code == 404
    )
    assert api_client.get(NOTIFICATIONS_PATH, headers=other_h).json()["total"] == 0


def test_share_lifecycle(api_client, sqlite_engine) -> None:
    from app.models import TravelPlan

    owner_email, owner_h = _user(api_client, sqlite_engine, tag="owner")
    db = _session(sqlite_engine)
    try:
        owner = db.scalar(select(User).where(User.email == owner_email))
        db.add(
            TravelPlan(
                user_id=owner.id,
                destination="Goa",
                destination_normalized="goa",
                start_date=NOW.date() + timedelta(days=30),
                end_date=NOW.date() + timedelta(days=37),
                status="active",
                visibility="discoverable",
            )
        )
        db.commit()
        plan = db.scalar(select(TravelPlan).where(TravelPlan.user_id == owner.id))
        plan_id = str(plan.id)
    finally:
        db.close()

    expires = (NOW + timedelta(days=7)).isoformat()
    created = api_client.post(
        SHARES_PATH, json={"plan_id": plan_id, "expires_at": expires}, headers=owner_h
    )
    assert created.status_code == 201, created.text
    share = created.json()
    assert share["plan_destination"] == "Goa"
    assert share["revoked_at"] is None

    mine = api_client.get(SHARES_PATH, headers=owner_h).json()
    assert mine["total"] == 1

    assert api_client.delete(f"{SHARES_PATH}/{share['id']}", headers=owner_h).status_code == 204
    after = api_client.get(SHARES_PATH, headers=owner_h).json()
    assert after["results"][0]["revoked_at"] is not None


def test_share_validates_expiry_and_plan(api_client, sqlite_engine) -> None:
    _, owner_h = _user(api_client, sqlite_engine, tag="owner")
    past = (NOW - timedelta(days=1)).isoformat()
    assert (
        api_client.post(SHARES_PATH, json={"expires_at": past}, headers=owner_h).status_code == 422
    )
    far = (NOW + timedelta(days=91)).isoformat()
    assert (
        api_client.post(SHARES_PATH, json={"expires_at": far}, headers=owner_h).status_code == 422
    )
    assert (
        api_client.post(SHARES_PATH, json={"expires_at": "tomorrow"}, headers=owner_h).status_code
        == 422
    )
    naive = (NOW + timedelta(days=7)).replace(tzinfo=None).isoformat()
    assert (
        api_client.post(SHARES_PATH, json={"expires_at": naive}, headers=owner_h).status_code == 422
    )
    # Foreign plans cannot be shared (no probing).
    assert (
        api_client.post(
            SHARES_PATH,
            json={
                "plan_id": str(uuid.uuid4()),
                "expires_at": (NOW + timedelta(days=7)).isoformat(),
            },
            headers=owner_h,
        ).status_code
        == 404
    )


def _travel_partners(api_client, sqlite_engine):
    """Two travel-discoverable users with an ACCEPTED partner request."""

    a_email, a_h = _user(api_client, sqlite_engine, tag="sharer")
    b_email, b_h = _user(api_client, sqlite_engine, tag="viewer")
    db = _session(sqlite_engine)
    try:
        for email, nick in ((a_email, "sa"), (b_email, "sb")):
            user = db.scalar(select(User).where(User.email == email))
            db.add(TravelProfile(user_id=user.id, travel_nickname=nick, discoverable=True))
        db.commit()
        b = db.scalar(select(User).where(User.email == b_email))
        b_id = str(b.id)
    finally:
        db.close()
    sent = api_client.post(
        "/api/v1/travel-buddies/requests", json={"recipient_id": b_id}, headers=a_h
    )
    assert sent.status_code == 201, sent.text
    assert (
        api_client.post(
            f"/api/v1/travel-buddies/requests/{sent.json()['id']}/accept", headers=b_h
        ).status_code
        == 200
    )
    return a_email, a_h, b_email, b_h


def test_accepted_partner_sees_live_share(api_client, sqlite_engine) -> None:
    _, owner_h, _, viewer_h = _travel_partners(api_client, sqlite_engine)
    expires = (NOW + timedelta(days=7)).isoformat()
    share = api_client.post(SHARES_PATH, json={"expires_at": expires}, headers=owner_h).json()

    feed = api_client.get(SHARES_PATH + "/shared-with-me", headers=viewer_h).json()
    assert feed["total"] == 1
    itinerary = api_client.get(f"{SHARES_PATH}/{share['id']}", headers=viewer_h).json()
    assert itinerary["share_id"] == share["id"]
    assert itinerary["owner_display_name"] == "sharer"
    # No live location, no messages, no SOS - the shape is plan facts only.
    assert set(itinerary) == {
        "share_id",
        "owner_display_name",
        "plan_destination",
        "plan_start_date",
        "plan_end_date",
        "expires_at",
    }


def test_strangers_and_expired_shares_see_nothing(api_client, sqlite_engine) -> None:
    _, owner_h, _, viewer_h = _travel_partners(api_client, sqlite_engine)
    _, stranger_h = _user(api_client, sqlite_engine, tag="stranger")
    expires = (NOW + timedelta(days=7)).isoformat()
    share = api_client.post(SHARES_PATH, json={"expires_at": expires}, headers=owner_h).json()

    assert api_client.get(f"{SHARES_PATH}/{share['id']}", headers=stranger_h).status_code == 404
    assert api_client.get(SHARES_PATH + "/shared-with-me", headers=stranger_h).json()["total"] == 0

    # Revocation takes effect immediately (server-side).
    assert api_client.delete(f"{SHARES_PATH}/{share['id']}", headers=owner_h).status_code == 204
    assert api_client.get(f"{SHARES_PATH}/{share['id']}", headers=viewer_h).status_code == 404
    assert api_client.get(SHARES_PATH + "/shared-with-me", headers=viewer_h).json()["total"] == 0

    # Expiry is enforced at read time: backdate the row past its window.
    share2 = api_client.post(SHARES_PATH, json={"expires_at": expires}, headers=owner_h).json()
    db = _session(sqlite_engine)
    try:
        from app.models import TripShare

        row = db.scalar(select(TripShare).where(TripShare.id == uuid.UUID(share2["id"])))
        row.expires_at = NOW - timedelta(seconds=1)
        db.commit()
    finally:
        db.close()
    assert api_client.get(f"{SHARES_PATH}/{share2['id']}", headers=viewer_h).status_code == 404
