"""Tests for report moderation (Phase 11) and SOS/acknowledgement/notify improvements (Phase 12C).

Reports: the owner-only moderation lifecycle (pending -> approved/
rejected, approved -> resolved/rejected, terminal lock), audit stamps,
ordinary-user impotence, and continued identity-free responses.
SOS: owner acknowledgement with compare-and-set semantics, contact
notification attempts recorded honestly at activation (idempotent), a
safe retry that never duplicates, and an observable attempts listing.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.models import User
from tests.conftest import register_user

REPORTS_PATH = "/api/v1/reports"
SOS_PATH = "/api/v1/sos"


def _session(engine):
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    return factory()


def _make_owner(api_client, engine, email: str):
    db = _session(engine)
    try:
        user = db.scalar(select(User).where(User.email == email))
        user.role = "owner"
        db.commit()
    finally:
        db.close()


def _user(api_client, engine, tag="user"):
    email = f"{tag}-{uuid.uuid4().hex[:8]}@example.com"
    _, headers = register_user(api_client, email, display_name=tag)
    return email, headers


def _report(api_client, headers):
    resp = api_client.post(
        REPORTS_PATH,
        json={
            "category": "poor_lighting",
            "description": "Dark alley behind the station.",
            "latitude": 15.5,
            "longitude": 73.8,
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_moderation_lifecycle(api_client, sqlite_engine) -> None:
    owner_email, owner_h = _user(api_client, sqlite_engine, tag="owner")
    _make_owner(api_client, sqlite_engine, owner_email)
    _, user_h = _user(api_client, sqlite_engine)
    report = _report(api_client, user_h)

    approved = api_client.patch(
        f"{REPORTS_PATH}/{report['id']}/moderate", json={"status": "approved"}, headers=owner_h
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    assert approved.json()["reviewed_at"] is not None
    # No submitter identity leaks through moderation either.
    assert "user_id" not in approved.json()
    assert "reviewed_by" not in approved.json()

    resolved = api_client.patch(
        f"{REPORTS_PATH}/{report['id']}/moderate", json={"status": "resolved"}, headers=owner_h
    )
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "resolved"

    # Terminal states lock (resolved cannot move, even back to approved).
    assert (
        api_client.patch(
            f"{REPORTS_PATH}/{report['id']}/moderate", json={"status": "approved"}, headers=owner_h
        ).status_code
        == 409
    )
    second = _report(api_client, user_h)
    assert (
        api_client.patch(
            f"{REPORTS_PATH}/{second['id']}/moderate", json={"status": "resolved"}, headers=owner_h
        ).status_code
        == 409
    )  # pending cannot skip to resolved


def test_moderation_requires_owner(api_client, sqlite_engine) -> None:
    _, user_h = _user(api_client, sqlite_engine)
    report = _report(api_client, user_h)
    assert (
        api_client.patch(
            f"{REPORTS_PATH}/{report['id']}/moderate", json={"status": "approved"}, headers=user_h
        ).status_code
        == 403
    )
    assert (
        api_client.patch(
            f"{REPORTS_PATH}/{report['id']}/moderate", json={"status": "approved"}
        ).status_code
        == 401
    )
    # Owner gate runs before existence (403 even for unknown ids).
    assert (
        api_client.patch(
            f"{REPORTS_PATH}/{uuid.uuid4()}/moderate", json={"status": "approved"}, headers=user_h
        ).status_code
        == 403
    )


def test_rejected_reports_stay_hidden(api_client, sqlite_engine) -> None:
    owner_email, owner_h = _user(api_client, sqlite_engine, tag="owner")
    _make_owner(api_client, sqlite_engine, owner_email)
    _, user_h = _user(api_client, sqlite_engine)
    report = _report(api_client, user_h)
    assert (
        api_client.patch(
            f"{REPORTS_PATH}/{report['id']}/moderate", json={"status": "rejected"}, headers=owner_h
        ).status_code
        == 200
    )
    assert api_client.get(f"{REPORTS_PATH}/{report['id']}", headers=user_h).status_code == 404
    assert all(r["id"] != report["id"] for r in api_client.get(REPORTS_PATH, headers=user_h).json())


def test_resolved_reports_listable_by_status(api_client, sqlite_engine) -> None:
    owner_email, owner_h = _user(api_client, sqlite_engine, tag="owner")
    _make_owner(api_client, sqlite_engine, owner_email)
    _, user_h = _user(api_client, sqlite_engine)
    report = _report(api_client, user_h)
    api_client.patch(
        f"{REPORTS_PATH}/{report['id']}/moderate", json={"status": "approved"}, headers=owner_h
    )
    api_client.patch(
        f"{REPORTS_PATH}/{report['id']}/moderate", json={"status": "resolved"}, headers=owner_h
    )
    resolved = api_client.get(REPORTS_PATH + "?status=resolved", headers=user_h).json()
    assert [r["id"] for r in resolved] == [report["id"]]


def test_sos_acknowledge_lifecycle(api_client, sqlite_engine) -> None:
    _, h = _user(api_client, sqlite_engine)
    created = api_client.post(SOS_PATH, json={"description": "Need help"}, headers=h)
    assert created.status_code == 201
    sos_id = created.json()["id"]

    acked = api_client.post(f"{SOS_PATH}/{sos_id}/acknowledge", headers=h)
    assert acked.status_code == 200
    assert acked.json()["status"] == "acknowledged"
    assert acked.json()["acknowledged_at"] is not None

    # acknowledged still closes normally...
    resolved = api_client.post(f"{SOS_PATH}/{sos_id}/resolve", headers=h)
    assert resolved.status_code == 200
    # ...but repeats and contradictions stay 409.
    assert api_client.post(f"{SOS_PATH}/{sos_id}/acknowledge", headers=h).status_code == 409
    assert api_client.post(f"{SOS_PATH}/{sos_id}/cancel", headers=h).status_code == 409


def test_sos_activation_records_honest_contact_attempts(api_client, sqlite_engine) -> None:
    _, h = _user(api_client, sqlite_engine)
    assert (
        api_client.post(
            "/api/v1/trusted-contacts/",
            json={"name": "Mom", "phone": "+911234567890"},
            headers=h,
        ).status_code
        == 201
    )
    created = api_client.post(SOS_PATH, json={"description": "Need help"}, headers=h)
    sos_id = created.json()["id"]

    attempts = api_client.get(f"{SOS_PATH}/{sos_id}/notifications", headers=h).json()
    assert len(attempts) == 1
    row = attempts[0]
    assert row["kind"] == "sos_created"
    assert row["channel"] == "sms"
    # Honest: nothing was sent (no provider), and the row says so.
    assert row["status"] == "unavailable"
    assert row["attempts"] == 1
    assert (
        "no messaging provider" in row["last_error"].lower()
        or "no provider" in row["last_error"].lower()
    )

    # The owner's inbox carries the same row (in-app visibility of the attempt).
    inbox = api_client.get("/api/v1/notifications", headers=h).json()
    assert any(n["id"] == row["id"] for n in inbox["results"])


def test_sos_retry_never_duplicates(api_client, sqlite_engine) -> None:
    _, h = _user(api_client, sqlite_engine)
    api_client.post(
        "/api/v1/trusted-contacts/", json={"name": "Mom", "phone": "+911234567890"}, headers=h
    )
    sos_id = api_client.post(SOS_PATH, json={"description": "Need help"}, headers=h).json()["id"]

    first = api_client.post(f"{SOS_PATH}/{sos_id}/notify-retry", headers=h).json()
    assert len(first) == 1
    assert first[0]["attempts"] == 2  # same row, attempts + 1
    second = api_client.post(f"{SOS_PATH}/{sos_id}/notify-retry", headers=h).json()
    assert len(second) == 1
    assert second[0]["attempts"] == 3
    assert second[0]["id"] == first[0]["id"]  # still the SAME row
    listed = api_client.get(f"{SOS_PATH}/{sos_id}/notifications", headers=h).json()
    assert len(listed) == 1  # never duplicated

    # Closed incidents refuse retries (history is not rewritten).
    api_client.post(f"{SOS_PATH}/{sos_id}/resolve", headers=h)
    assert api_client.post(f"{SOS_PATH}/{sos_id}/notify-retry", headers=h).status_code == 409


def test_sos_notification_privacy(api_client, sqlite_engine) -> None:
    _, h = _user(api_client, sqlite_engine)
    _, other_h = _user(api_client, sqlite_engine, tag="other")
    sos_id = api_client.post(SOS_PATH, json={"description": "Need help"}, headers=h).json()["id"]
    assert api_client.get(f"{SOS_PATH}/{sos_id}/notifications", headers=other_h).status_code == 404
    assert api_client.post(f"{SOS_PATH}/{sos_id}/notify-retry", headers=other_h).status_code == 404
    assert api_client.post(f"{SOS_PATH}/{sos_id}/acknowledge", headers=other_h).status_code == 404
