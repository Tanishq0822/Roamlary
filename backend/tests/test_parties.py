"""Endpoint tests for invitation-only house parties (Phase 10).

These prove the private-event rules: parties are forced private server-
side (never creatable or patchable public); they never appear in meetup
discovery; reads 404 for outsiders (no id enumeration); the exact venue
travels ONLY to host + approved (pending invitees decide without it);
invites check eligibility + blocks with 404-collapse; duplicate pending
invites are 409 (UNIQUE pair, race-proof); accept creates membership
atomically with capacity recheck; decline/revoke/leave work; ended or
cancelled parties freeze; and meetup/party id spaces never cross.
"""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.core.policy import set_policy
from app.models import User
from tests.conftest import register_user

PARTIES_PATH = "/api/v1/parties"
INVITATIONS_PATH = "/api/v1/invitations"

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
    email = f"{tag}-{uuid.uuid4().hex[:8]}@example.com"
    _, headers = register_user(api_client, email, display_name=tag)
    _flip_policy(engine, False, email)
    return email, headers


def _guest(api_client, tag="guest"):
    email = f"{tag}-{uuid.uuid4().hex[:8]}@example.com"
    _, headers = register_user(api_client, email, display_name=tag)
    return email, headers


def _create_party(api_client, headers, **overrides):
    body = {
        "title": "Rooftop Dinner",
        "description": "Bring dessert.",
        "category": "food",
        "start_at": START,
        "end_at": END,
        "capacity": 8,
        "location_text": "North Goa",
        "venue_details": "12 Palm Street, Apt 4",
    }
    body.update(overrides)
    return api_client.post(PARTIES_PATH, json=body, headers=headers)


def _id_of(api_client, headers) -> str:
    return api_client.get("/api/v1/users/me", headers=headers).json()["id"]


def test_party_forced_private_and_invisible(api_client, sqlite_engine) -> None:
    _, h = _host(api_client, sqlite_engine)
    resp = _create_party(api_client, h, visibility="public")
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["kind"] == "house_party"
    assert body["visibility"] == "private"  # forced, not trusted
    # Never in meetup discovery...
    feed = api_client.get("/api/v1/meetups", headers=h).json()
    assert all(m["kind"] == "meetup" for m in feed)
    assert not any(m["id"] == body["id"] for m in feed)
    # ...nor readable via the meetup surface (id spaces never cross).
    assert api_client.get(f"/api/v1/meetups/{body['id']}", headers=h).status_code == 404
    # Host sees their own venue.
    assert body["venue_details"] == "12 Palm Street, Apt 4"


def test_party_visibility_immutable(api_client, sqlite_engine) -> None:
    _, h = _host(api_client, sqlite_engine)
    party = _create_party(api_client, h).json()
    patched = api_client.patch(
        f"{PARTIES_PATH}/{party['id']}", json={"visibility": "public"}, headers=h
    )
    assert patched.status_code == 200
    assert patched.json()["visibility"] == "private"


def test_outsider_cannot_read_party(api_client, sqlite_engine) -> None:
    _, h = _host(api_client, sqlite_engine)
    _, o_h = _guest(api_client, tag="outsider")
    party = _create_party(api_client, h).json()
    assert api_client.get(f"{PARTIES_PATH}/{party['id']}", headers=o_h).status_code == 404
    assert (
        api_client.get(f"{PARTIES_PATH}/{party['id']}/participants", headers=o_h).status_code == 404
    )


def test_invite_accept_flow_with_venue_gating(api_client, sqlite_engine) -> None:
    _, h = _host(api_client, sqlite_engine)
    _, g_h = _guest(api_client)
    party = _create_party(api_client, h).json()
    invited = api_client.post(
        f"{PARTIES_PATH}/{party['id']}/invite",
        json={"invitee_id": _id_of(api_client, g_h)},
        headers=h,
    )
    assert invited.status_code == 201, invited.text
    invite = invited.json()
    assert invite["status"] == "pending"

    # The invitee sees the invitation (and the party listing) but NOT the venue.
    inbox = api_client.get(INVITATIONS_PATH, headers=g_h).json()
    assert inbox["total"] == 1
    pending_view = api_client.get(f"{PARTIES_PATH}/{party['id']}", headers=g_h).json()
    assert pending_view["venue_details"] is None
    assert pending_view["location_text"] == "North Goa"

    accepted = api_client.post(f"{INVITATIONS_PATH}/{invite['id']}/accept", headers=g_h)
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "accepted"
    # Approved: the venue is now visible, and the guest list shows them.
    insider = api_client.get(f"{PARTIES_PATH}/{party['id']}", headers=g_h).json()
    assert insider["venue_details"] == "12 Palm Street, Apt 4"
    assert insider["my_membership"] == "approved"
    guests = api_client.get(f"{PARTIES_PATH}/{party['id']}/participants", headers=g_h).json()
    assert len(guests) == 1


def test_invite_validates_recipient(api_client, sqlite_engine) -> None:
    _, h = _host(api_client, sqlite_engine)
    party = _create_party(api_client, h).json()
    assert (
        api_client.post(
            f"{PARTIES_PATH}/{party['id']}/invite",
            json={"invitee_id": str(uuid.uuid4())},
            headers=h,
        ).status_code
        == 404
    )
    assert (
        api_client.post(
            f"{PARTIES_PATH}/{party['id']}/invite",
            json={"invitee_id": _id_of(api_client, h)},
            headers=h,
        ).status_code
        == 422
    )


def test_duplicate_invite_is_409(api_client, sqlite_engine) -> None:
    _, h = _host(api_client, sqlite_engine)
    _, g_h = _guest(api_client)
    party = _create_party(api_client, h).json()
    guest_id = _id_of(api_client, g_h)
    assert (
        api_client.post(
            f"{PARTIES_PATH}/{party['id']}/invite", json={"invitee_id": guest_id}, headers=h
        ).status_code
        == 201
    )
    assert (
        api_client.post(
            f"{PARTIES_PATH}/{party['id']}/invite", json={"invitee_id": guest_id}, headers=h
        ).status_code
        == 409
    )


def test_duplicate_invite_race_is_caught_by_database(api_client, sqlite_engine) -> None:
    """Two racing invite inserts keep exactly one invitation row."""
    from sqlalchemy.exc import IntegrityError

    from app.models import EventInvitation

    _, h = _host(api_client, sqlite_engine)
    _, g_h = _guest(api_client)
    party = _create_party(api_client, h).json()
    guest_id = _id_of(api_client, g_h)
    assert (
        api_client.post(
            f"{PARTIES_PATH}/{party['id']}/invite", json={"invitee_id": guest_id}, headers=h
        ).status_code
        == 201
    )
    db = _session(sqlite_engine)
    try:
        host = db.scalar(select(User).where(User.display_name == "host"))
        db.add(
            EventInvitation(
                meetup_id=uuid.UUID(party["id"]),
                inviter_id=host.id,
                invitee_id=uuid.UUID(guest_id),
                status="pending",
            )
        )
        try:
            db.commit()
            raise AssertionError("expected the invitation UNIQUE index to reject this")
        except IntegrityError:
            db.rollback()
    finally:
        db.close()


def test_decline_then_reinvite(api_client, sqlite_engine) -> None:
    _, h = _host(api_client, sqlite_engine)
    _, g_h = _guest(api_client)
    party = _create_party(api_client, h).json()
    guest_id = _id_of(api_client, g_h)
    first = api_client.post(
        f"{PARTIES_PATH}/{party['id']}/invite", json={"invitee_id": guest_id}, headers=h
    ).json()
    assert (
        api_client.post(f"{INVITATIONS_PATH}/{first['id']}/decline", headers=g_h).status_code == 200
    )
    # Accepting the declined invite is over (409)...
    assert (
        api_client.post(f"{INVITATIONS_PATH}/{first['id']}/accept", headers=g_h).status_code == 409
    )
    # ...but the host may invite again (same row, fresh pending).
    second = api_client.post(
        f"{PARTIES_PATH}/{party['id']}/invite", json={"invitee_id": guest_id}, headers=h
    )
    assert second.status_code == 201
    assert second.json()["id"] == first["id"]
    assert second.json()["status"] == "pending"


def test_revoke_invitation(api_client, sqlite_engine) -> None:
    _, h = _host(api_client, sqlite_engine)
    _, g_h = _guest(api_client)
    party = _create_party(api_client, h).json()
    guest_id = _id_of(api_client, g_h)
    api_client.post(
        f"{PARTIES_PATH}/{party['id']}/invite", json={"invitee_id": guest_id}, headers=h
    )
    revoked = api_client.delete(f"{PARTIES_PATH}/{party['id']}/invite/{guest_id}", headers=h)
    assert revoked.status_code == 200
    assert revoked.json()["status"] == "revoked"
    inbox = api_client.get(INVITATIONS_PATH, headers=g_h).json()
    assert inbox["results"][0]["status"] == "revoked"


def test_full_party_refuses_accept_but_keeps_invite(api_client, sqlite_engine) -> None:
    _, h = _host(api_client, sqlite_engine)
    _, g1_h = _guest(api_client, tag="g1")
    _, g2_h = _guest(api_client, tag="g2")
    party = _create_party(api_client, h, capacity=2).json()
    for g_h in (g1_h, g2_h):
        inv = api_client.post(
            f"{PARTIES_PATH}/{party['id']}/invite",
            json={"invitee_id": _id_of(api_client, g_h)},
            headers=h,
        ).json()
        assert (
            api_client.post(f"{INVITATIONS_PATH}/{inv['id']}/accept", headers=g_h).status_code
            == 200
        )
    _, g3_h = _guest(api_client, tag="g3")
    inv3 = api_client.post(
        f"{PARTIES_PATH}/{party['id']}/invite",
        json={"invitee_id": _id_of(api_client, g3_h)},
        headers=h,
    ).json()
    refused = api_client.post(f"{INVITATIONS_PATH}/{inv3['id']}/accept", headers=g3_h)
    assert refused.status_code == 409
    assert (
        api_client.get(INVITATIONS_PATH, headers=g3_h).json()["results"][0]["status"] == "pending"
    )


def test_blocked_invite_is_404(api_client, sqlite_engine) -> None:
    _, h = _host(api_client, sqlite_engine)
    _, g_h = _guest(api_client)
    party = _create_party(api_client, h).json()
    guest_id = _id_of(api_client, g_h)
    assert (
        api_client.post("/api/v1/blocks", json={"blocked_id": guest_id}, headers=h).status_code
        == 201
    )
    assert (
        api_client.post(
            f"{PARTIES_PATH}/{party['id']}/invite", json={"invitee_id": guest_id}, headers=h
        ).status_code
        == 404
    )


def test_cancelled_party_freezes_invites(api_client, sqlite_engine) -> None:
    _, h = _host(api_client, sqlite_engine)
    _, g_h = _guest(api_client)
    party = _create_party(api_client, h).json()
    assert api_client.post(f"{PARTIES_PATH}/{party['id']}/cancel", headers=h).status_code == 200
    assert (
        api_client.post(
            f"{PARTIES_PATH}/{party['id']}/invite",
            json={"invitee_id": _id_of(api_client, g_h)},
            headers=h,
        ).status_code
        == 409
    )


def test_only_invitee_answers(api_client, sqlite_engine) -> None:
    _, h = _host(api_client, sqlite_engine)
    _, g_h = _guest(api_client)
    _, s_h = _guest(api_client, tag="stranger")
    party = _create_party(api_client, h).json()
    inv = api_client.post(
        f"{PARTIES_PATH}/{party['id']}/invite",
        json={"invitee_id": _id_of(api_client, g_h)},
        headers=h,
    ).json()
    assert api_client.post(f"{INVITATIONS_PATH}/{inv['id']}/accept", headers=s_h).status_code == 404
    assert api_client.post(f"{INVITATIONS_PATH}/{inv['id']}/accept", headers=h).status_code == 404
    assert api_client.get(INVITATIONS_PATH, headers=s_h).json()["total"] == 0
