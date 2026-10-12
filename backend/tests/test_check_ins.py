"""Safety check-in endpoint tests (Phase 4).

Covers the status lifecycle (pending -> safe/needs_help/cancelled, with
all terminal states locked), the timezone and future-deadline policies,
server-controlled ownership and completion timestamps, and the explicit
safety boundary that no notification or SOS side effect exists.
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from tests.conftest import register_user

BASE = "/api/v1/check-ins/"


def _future(hours=2):
    """A timezone-aware timestamp `hours` from now, in ISO format."""
    return (datetime.now(UTC) + timedelta(hours=hours)).isoformat()


def _create(client, headers, **overrides):
    payload = {"note": "North trail hike"}
    payload.update(overrides)
    return client.post(BASE, json=payload, headers=headers)


# --------------------------------------------------------------- creation


def test_create_checkin_succeeds_and_returns_public_fields(api_client):
    uid, h = register_user(api_client, "c1@example.com")
    resp = _create(api_client, h, due_at=_future())
    assert resp.status_code == 201
    body = resp.json()
    assert set(body) == {
        "id",
        "user_id",
        "status",
        "note",
        "due_at",
        "completed_at",
        "created_at",
        "updated_at",
    }
    assert body["user_id"] == uid
    assert body["status"] == "pending"  # server-chosen, not client
    assert body["note"] == "North trail hike"
    assert body["completed_at"] is None  # not answered yet


def test_create_minimal_checkin_no_note_no_deadline(api_client):
    _, h = register_user(api_client, "c2@example.com")
    resp = api_client.post(BASE, json={}, headers=h)
    assert resp.status_code == 201
    assert resp.json()["note"] is None
    assert resp.json()["due_at"] is None


def test_unauthenticated_requests_rejected(api_client):
    assert api_client.post(BASE, json={}).status_code == 401
    assert api_client.get(BASE).status_code == 401
    assert api_client.get(BASE + "00000000-0000-0000-0000-000000000000").status_code == 401


def test_past_deadline_rejected(api_client):
    """Documented policy: due_at must be in the future at create time."""
    _, h = register_user(api_client, "c3@example.com")
    past = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    assert _create(api_client, h, due_at=past).status_code == 422


def test_naive_timestamp_rejected(api_client):
    """Documented policy: timestamps must carry a timezone."""
    _, h = register_user(api_client, "c4@example.com")
    naive = datetime.now().replace(tzinfo=None).isoformat()  # no zone info
    assert _create(api_client, h, due_at=naive).status_code == 422


def test_malformed_payload_rejected(api_client):
    _, h = register_user(api_client, "c5@example.com")
    assert _create(api_client, h, due_at="not-a-timestamp").status_code == 422
    assert _create(api_client, h, note="x" * 501).status_code == 422


def test_client_cannot_supply_status_user_id_or_protected_fields(api_client):
    _, h = register_user(api_client, "c6@example.com")
    # status is server-chosen on create -> 422 if smuggled.
    assert _create(api_client, h, status="safe").status_code == 422
    assert (
        _create(
            api_client,
            h,
            user_id="00000000-0000-0000-0000-000000000000",
        ).status_code
        == 422
    )
    assert _create(api_client, h, completed_at=datetime.now(UTC).isoformat()).status_code == 422


# ----------------------------------------------------------------- reads


def test_list_returns_only_own_checkins_newest_first(api_client):
    uid_a, h_a = register_user(api_client, "l1@example.com")
    _, h_b = register_user(api_client, "l2@example.com")
    _create(api_client, h_a, note="first")
    _create(api_client, h_a, note="second")
    _create(api_client, h_b, note="b-only")

    a_list = api_client.get(BASE, headers=h_a).json()
    assert [c["note"] for c in a_list] == ["second", "first"]  # newest first
    assert all(c["user_id"] == uid_a for c in a_list)

    b_list = api_client.get(BASE, headers=h_b).json()
    assert [c["note"] for c in b_list] == ["b-only"]


def test_list_status_filter(api_client):
    _, h = register_user(api_client, "l3@example.com")
    done = _create(api_client, h, note="done").json()
    api_client.post(BASE + done["id"] + "/complete", headers=h)
    _create(api_client, h, note="open")

    pending = api_client.get(BASE + "?status=pending", headers=h).json()
    assert [c["note"] for c in pending] == ["open"]
    safe = api_client.get(BASE + "?status=safe", headers=h).json()
    assert [c["note"] for c in safe] == ["done"]
    # Unknown status value is a 422, not a silent empty list.
    assert api_client.get(BASE + "?status=bogus", headers=h).status_code == 422


def test_cannot_access_another_users_checkin(api_client):
    _, h_owner = register_user(api_client, "l4@example.com")
    _, h_thief = register_user(api_client, "l5@example.com")
    mine = _create(api_client, h_owner).json()
    assert api_client.get(BASE + mine["id"], headers=h_thief).status_code == 404
    assert (
        api_client.patch(BASE + mine["id"], json={"note": "x"}, headers=h_thief).status_code == 404
    )
    assert api_client.post(BASE + mine["id"] + "/complete", headers=h_thief).status_code == 404


# ---------------------------------------------------------------- update


def test_update_note_and_deadline_succeeds_while_pending(api_client):
    _, h = register_user(api_client, "u1@example.com")
    mine = _create(api_client, h).json()
    new_due = _future(hours=5)
    resp = api_client.patch(
        BASE + mine["id"], json={"note": "updated", "due_at": new_due}, headers=h
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["note"] == "updated"
    # The API normalizes timestamps to UTC, so compare the INSTANT, not
    # the raw string ("+00:00" in, "Z" back out are the same moment).
    assert datetime.fromisoformat(body["due_at"]) == datetime.fromisoformat(new_due)


def test_update_rejects_past_deadline(api_client):
    _, h = register_user(api_client, "u2@example.com")
    mine = _create(api_client, h).json()
    past = (datetime.now(UTC) - timedelta(minutes=5)).isoformat()
    assert api_client.patch(BASE + mine["id"], json={"due_at": past}, headers=h).status_code == 422


def test_status_transitions_from_pending_allowed(api_client):
    _, h = register_user(api_client, "u3@example.com")
    for target in ("safe", "needs_help", "cancelled"):
        mine = _create(api_client, h, note=f"go-{target}").json()
        resp = api_client.patch(BASE + mine["id"], json={"status": target}, headers=h)
        assert resp.status_code == 200, target
        assert resp.json()["status"] == target


def test_terminal_states_cannot_be_reactivated(api_client):
    """No transition leaves safe/needs_help/cancelled - no reactivation."""
    _, h = register_user(api_client, "u4@example.com")
    for terminal in ("safe", "needs_help", "cancelled"):
        mine = _create(api_client, h, note=f"t-{terminal}").json()
        api_client.patch(BASE + mine["id"], json={"status": terminal}, headers=h)
        # Try to move it to pending (reactivate) and to another state.
        for target in ("pending", "safe", "needs_help", "cancelled"):
            resp = api_client.patch(BASE + mine["id"], json={"status": target}, headers=h)
            if target == terminal:
                # Same-value set is rejected too (409), never silently ok.
                assert resp.status_code == 409, (terminal, target)
            else:
                assert resp.status_code == 409, (terminal, target)


def test_editing_note_on_terminal_checkin_rejected(api_client):
    _, h = register_user(api_client, "u5@example.com")
    mine = _create(api_client, h).json()
    api_client.patch(BASE + mine["id"], json={"status": "safe"}, headers=h)
    resp = api_client.patch(BASE + mine["id"], json={"note": "late edit"}, headers=h)
    assert resp.status_code == 409


def test_update_cannot_touch_protected_fields(api_client):
    uid, h = register_user(api_client, "u6@example.com")
    mine = _create(api_client, h).json()
    for smuggle in (
        {"id": "00000000-0000-0000-0000-000000000000"},
        {"user_id": "00000000-0000-0000-0000-000000000000"},
        {"created_at": "2000-01-01T00:00:00Z"},
        {"completed_at": "2000-01-01T00:00:00Z"},
    ):
        assert api_client.patch(BASE + mine["id"], json=smuggle, headers=h).status_code == 422
    # Record unchanged, still owned by caller.
    body = api_client.get(BASE + mine["id"], headers=h).json()
    assert body["user_id"] == uid
    assert body["completed_at"] is None


# -------------------------------------------------------------- complete


def test_complete_sets_status_and_server_timestamp(api_client):
    _, h = register_user(api_client, "x1@example.com")
    mine = _create(api_client, h).json()
    before = datetime.now(UTC)
    resp = api_client.post(BASE + mine["id"] + "/complete", headers=h)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "safe"
    assert body["completed_at"] is not None
    # completed_at is server time, roughly now (not client-supplied).
    completed = datetime.fromisoformat(body["completed_at"])
    assert completed >= before - timedelta(seconds=5)


def test_complete_is_idempotent_and_preserves_first_timestamp(api_client):
    """Repeat completion succeeds (200) and keeps the FIRST completed_at."""
    _, h = register_user(api_client, "x2@example.com")
    mine = _create(api_client, h).json()
    first = api_client.post(BASE + mine["id"] + "/complete", headers=h).json()
    second = api_client.post(BASE + mine["id"] + "/complete", headers=h)
    assert second.status_code == 200
    assert second.json()["completed_at"] == first["completed_at"]


def test_complete_rejects_non_pending_states(api_client):
    """needs_help and cancelled cannot be 'completed' to safe."""
    _, h = register_user(api_client, "x3@example.com")
    for state in ("needs_help", "cancelled"):
        mine = _create(api_client, h, note=f"z-{state}").json()
        api_client.patch(BASE + mine["id"], json={"status": state}, headers=h)
        resp = api_client.post(BASE + mine["id"] + "/complete", headers=h)
        assert resp.status_code == 409, state
        assert "detail" in resp.json()  # error body, not a check-in body
        # The record is unchanged - still in its original state.
        assert api_client.get(BASE + mine["id"], headers=h).json()["status"] == state


def test_cancelled_leaves_completed_at_null(api_client):
    """cancelled is an abandonment, not an answer - no completion time."""
    _, h = register_user(api_client, "x4@example.com")
    mine = _create(api_client, h).json()
    body = api_client.patch(BASE + mine["id"], json={"status": "cancelled"}, headers=h).json()
    assert body["status"] == "cancelled"
    assert body["completed_at"] is None


# --------------------------------------------------------- safety boundary


def test_no_notification_or_sos_side_effect(api_client, db_session):
    """Phase 4 writes rows only. Completing a check-in must not create
    an SOS event or report anything outward."""
    from sqlalchemy import func, select

    from app.models.sos_event import SosEvent

    uid_str, h = register_user(api_client, "safe1@example.com")
    mine = _create(api_client, h).json()
    api_client.post(BASE + mine["id"] + "/complete", headers=h)

    # No SOS event was created by the completion.
    count = db_session.scalar(
        select(func.count()).select_from(SosEvent).where(SosEvent.user_id == UUID(uid_str))
    )
    assert count == 0
    # The response contains only approved fields (no 'notified' flag etc).
    body = api_client.get(BASE + mine["id"], headers=h).json()
    assert "notified" not in body
    assert "sos" not in body
    assert "alert" not in body
