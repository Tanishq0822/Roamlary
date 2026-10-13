"""Tests for the meeting/trip safety workflow (Phase 15).

Optional features stay off until explicitly consented; consent is tied
to user + activity + disclosure version; declining never activates;
withdrawal (new all-off row) and expiry read as withdrawn; nobody
touches another user's rows; the risk acknowledgement is recorded per
activity; everything works with no providers configured; SOS creation
is never misrepresented as confirmed assistance.
"""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.core.policy import set_policy
from app.models import User
from tests.conftest import register_user

SAFETY_PATH = "/api/v1/safety"

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


def _user(api_client, engine, tag="safety"):
    email = f"{tag}-{uuid.uuid4().hex[:8]}@example.com"
    _, headers = register_user(api_client, email, display_name=tag)
    _flip_policy(engine, False, email)
    return email, headers


def _meetup(api_client, headers, visibility="public"):
    start = (NOW + timedelta(days=30)).isoformat()
    end = (NOW + timedelta(days=31)).isoformat()
    resp = api_client.post(
        "/api/v1/meetups",
        json={
            "title": "Safety Hike",
            "category": "hiking",
            "start_at": start,
            "end_at": end,
            "participation": "open",
            "visibility": visibility,
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def test_disclosure_and_capabilities_are_honest(api_client, sqlite_engine) -> None:
    _, h = _user(api_client, sqlite_engine)
    disclosure = api_client.get(f"{SAFETY_PATH}/disclosure", headers=h).json()
    assert disclosure["version"] == "2026-10-15.v1"
    assert disclosure["legal_review_pending"] is True
    assert "guarantee" in disclosure["text"].lower() or "does not guarantee" in disclosure["text"]
    assert "location_sharing" not in disclosure["features"]
    assert "location_sharing" in disclosure["unavailable_features"]
    assert "microphone_camera" in disclosure["unavailable_features"]

    caps = api_client.get(f"{SAFETY_PATH}/capabilities", headers=h).json()
    assert caps["trip_detail_sharing"] == "available"
    assert caps["checkin_reminders"] == "available"
    assert caps["sos_notify_attempts"] == "available"
    assert caps["location_sharing"] == "unavailable"
    assert caps["microphone_camera"] == "never"
    assert api_client.get(f"{SAFETY_PATH}/disclosure").status_code == 401


def test_accept_records_granular_consent(api_client, sqlite_engine) -> None:
    _, h = _user(api_client, sqlite_engine)
    mid = _meetup(api_client, h)
    resp = api_client.post(
        f"{SAFETY_PATH}/consents",
        json={
            "subject_type": "meetup",
            "subject_id": mid,
            "features": {"share_trip_details": True, "sos_notify": True},
            "decision": "accepted",
            "disclosure_version": "2026-10-15.v1",
        },
        headers=h,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["share_trip_details"] is True
    assert body["checkin_reminders"] is False  # not chosen: stays off
    assert body["sos_notify"] is True
    assert body["decision"] == "accepted"

    current = api_client.get(
        f"{SAFETY_PATH}/consents/current?subject_type=meetup&subject_id={mid}", headers=h
    ).json()
    assert current["id"] == body["id"]


def test_decline_records_acknowledgement_without_activating(api_client, sqlite_engine) -> None:
    """Declining stores an explicit declined row (features off even if
    the body sent flags as on) - never the absence of a row."""
    _, h = _user(api_client, sqlite_engine)
    mid = _meetup(api_client, h)
    resp = api_client.post(
        f"{SAFETY_PATH}/consents",
        json={
            "subject_type": "meetup",
            "subject_id": mid,
            "features": {"share_trip_details": True, "sos_notify": True},
            "decision": "declined",
            "disclosure_version": "2026-10-15.v1",
        },
        headers=h,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["decision"] == "declined"
    assert body["share_trip_details"] is False
    assert body["sos_notify"] is False
    history = api_client.get(f"{SAFETY_PATH}/consents?subject_id={mid}", headers=h).json()
    assert history["total"] == 1  # the declined row IS recorded


def test_unavailable_features_rejected(api_client, sqlite_engine) -> None:
    """Consent can never authorize what does not exist (location
    sharing has no GPS pipeline on this build)."""
    _, h = _user(api_client, sqlite_engine)
    mid = _meetup(api_client, h)
    resp = api_client.post(
        f"{SAFETY_PATH}/consents",
        json={
            "subject_type": "meetup",
            "subject_id": mid,
            "features": {"location_sharing": True},
            "decision": "accepted",
            "disclosure_version": "2026-10-15.v1",
        },
        headers=h,
    )
    assert resp.status_code == 422
    assert (
        api_client.post(
            f"{SAFETY_PATH}/consents",
            json={
                "subject_type": "meetup",
                "subject_id": mid,
                "features": {"telepathy": True},
                "decision": "accepted",
                "disclosure_version": "2026-10-15.v1",
            },
            headers=h,
        ).status_code
        == 422
    )
    assert (
        api_client.post(
            f"{SAFETY_PATH}/consents",
            json={
                "subject_type": "meetup",
                "subject_id": mid,
                "features": {},
                "decision": "maybe",
                "disclosure_version": "2026-10-15.v1",
            },
            headers=h,
        ).status_code
        == 422
    )


def test_stale_disclosure_version_refused(api_client, sqlite_engine) -> None:
    _, h = _user(api_client, sqlite_engine)
    mid = _meetup(api_client, h)
    resp = api_client.post(
        f"{SAFETY_PATH}/consents",
        json={
            "subject_type": "meetup",
            "subject_id": mid,
            "features": {},
            "decision": "accepted",
            "disclosure_version": "2000-01-01.v0",
        },
        headers=h,
    )
    assert resp.status_code == 409


def test_withdrawal_appends_all_off_row(api_client, sqlite_engine) -> None:
    """Withdrawing = a NEW all-off row (history tamper-resistant: no
    update/delete routes exist); current reads the latest row."""
    _, h = _user(api_client, sqlite_engine)
    mid = _meetup(api_client, h)
    base = {
        "subject_type": "meetup",
        "subject_id": mid,
        "features": {"share_trip_details": True},
        "decision": "accepted",
        "disclosure_version": "2026-10-15.v1",
    }
    assert api_client.post(f"{SAFETY_PATH}/consents", json=base, headers=h).status_code == 201
    withdrawn = api_client.post(
        f"{SAFETY_PATH}/consents",
        json={**base, "features": {}, "decision": "declined"},
        headers=h,
    )
    assert withdrawn.status_code == 201
    current = api_client.get(
        f"{SAFETY_PATH}/consents/current?subject_type=meetup&subject_id={mid}", headers=h
    ).json()
    assert current["id"] == withdrawn.json()["id"]
    assert current["share_trip_details"] is False
    history = api_client.get(f"{SAFETY_PATH}/consents?subject_id={mid}", headers=h).json()
    assert history["total"] == 2  # both rows preserved (audit trail)


def test_expired_consent_reads_withdrawn(api_client, sqlite_engine) -> None:
    """Expired rows are skipped by the current-state read (withdrawn),
    while history keeps them."""
    _, h = _user(api_client, sqlite_engine)
    mid = _meetup(api_client, h)
    body = {
        "subject_type": "meetup",
        "subject_id": mid,
        "features": {"sos_notify": True},
        "decision": "accepted",
        "disclosure_version": "2026-10-15.v1",
        "expires_at": (NOW + timedelta(hours=1)).isoformat(),
    }
    assert api_client.post(f"{SAFETY_PATH}/consents", json=body, headers=h).status_code == 201
    assert (
        api_client.post(
            f"{SAFETY_PATH}/consents",
            json={**body, "expires_at": (NOW - timedelta(hours=1)).isoformat()},
            headers=h,
        ).status_code
        == 422
    )  # past expiries are rejected at write
    db = _session(sqlite_engine)
    try:
        from app.models import SafetyConsent

        row = db.scalars(select(SafetyConsent)).first()
        row.expires_at = NOW - timedelta(seconds=1)  # time passes
        db.commit()
    finally:
        db.close()
    assert (
        api_client.get(
            f"{SAFETY_PATH}/consents/current?subject_type=meetup&subject_id={mid}", headers=h
        ).status_code
        == 404
    )


def test_consent_is_per_user_and_per_activity(api_client, sqlite_engine) -> None:
    """Nobody reads/writes another user's rows; invisible activities
    404 identically to missing ones (consent never widens access)."""
    _, h = _user(api_client, sqlite_engine)
    _, other_h = _user(api_client, sqlite_engine, tag="other")
    # A PRIVATE meetup: the stranger cannot even see it.
    mid = _meetup(api_client, h, visibility="private")
    assert (
        api_client.post(
            f"{SAFETY_PATH}/consents",
            json={
                "subject_type": "meetup",
                "subject_id": mid,
                "features": {},
                "decision": "accepted",
                "disclosure_version": "2026-10-15.v1",
            },
            headers=other_h,
        ).status_code
        == 404
    )
    assert api_client.get(f"{SAFETY_PATH}/consents", headers=other_h).json()["total"] == 0
    assert (
        api_client.get(
            f"{SAFETY_PATH}/consents/current?subject_type=meetup&subject_id={mid}", headers=other_h
        ).status_code
        == 404
    )
    # The owner's own row is untouched by the stranger's attempt.
    assert api_client.get(f"{SAFETY_PATH}/consents", headers=h).json()["total"] == 0
    # Unknown subject types are rejected without leaking.
    assert (
        api_client.post(
            f"{SAFETY_PATH}/consents",
            json={
                "subject_type": "spaceship",
                "subject_id": mid,
                "features": {},
                "decision": "accepted",
                "disclosure_version": "2026-10-15.v1",
            },
            headers=h,
        ).status_code
        == 422
    )


def test_trip_share_consent_subject(api_client, sqlite_engine) -> None:
    """Consents attach to trip shares too (visibility reuses the share
    rules: owner or accepted partner, live shares only)."""
    from app.models import TravelProfile

    owner_email, owner_h = _user(api_client, sqlite_engine, tag="owner")
    _, viewer_h = _user(api_client, sqlite_engine, tag="viewer")
    db = _session(sqlite_engine)
    try:
        for email, nick in ((owner_email, "oa"),):
            user = db.scalar(select(User).where(User.email == email))
            db.add(TravelProfile(user_id=user.id, travel_nickname=nick, discoverable=True))
        db.commit()
    finally:
        db.close()
    share = api_client.post(
        "/api/v1/trip-shares",
        json={"expires_at": (NOW + timedelta(days=7)).isoformat()},
        headers=owner_h,
    )
    assert share.status_code == 201, share.text
    sid = share.json()["id"]
    resp = api_client.post(
        f"{SAFETY_PATH}/consents",
        json={
            "subject_type": "trip_share",
            "subject_id": sid,
            "features": {"share_trip_details": True},
            "decision": "accepted",
            "disclosure_version": "2026-10-15.v1",
        },
        headers=owner_h,
    )
    assert resp.status_code == 201, resp.text
    # A stranger (not owner/partner) cannot consent to it (404).
    assert (
        api_client.post(
            f"{SAFETY_PATH}/consents",
            json={
                "subject_type": "trip_share",
                "subject_id": sid,
                "features": {},
                "decision": "accepted",
                "disclosure_version": "2026-10-15.v1",
            },
            headers=viewer_h,
        ).status_code
        == 404
    )
