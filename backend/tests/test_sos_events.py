"""SOS incident endpoint tests (Phase 5).

Covers authentication on all five routes, activation validation
(coordinates as a pair, ranges, blank/overlong descriptions, strict
bodies), ownership and privacy (identical 404s, own-only listing), the
active -> cancelled / active -> resolved lifecycle with server-only
timestamps, and the explicit safety boundary that activation writes a
row and nothing else.
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from tests.conftest import register_user

BASE = "/api/v1/sos"

READ_FIELDS = {
    "id",
    "user_id",
    "status",
    "description",
    "latitude",
    "longitude",
    "location_recorded_at",
    "created_at",
    "updated_at",
    "cancelled_at",
    "resolved_at",
}


def _create(client, headers, **overrides):
    return client.post(BASE, json=overrides, headers=headers)


# --------------------------------------------------------------- creation


def test_create_sos_returns_active_incident_with_public_fields(api_client):
    uid, h = register_user(api_client, "s1@example.com")
    resp = _create(api_client, h, description="Ambulance needed at the hostel")
    assert resp.status_code == 201
    body = resp.json()
    assert set(body) == READ_FIELDS
    assert body["user_id"] == uid
    assert body["status"] == "active"  # server-chosen, not client
    assert body["description"] == "Ambulance needed at the hostel"
    assert body["cancelled_at"] is None
    assert body["resolved_at"] is None


def test_create_minimal_sos_no_description_no_location(api_client):
    _, h = register_user(api_client, "s2@example.com")
    resp = _create(api_client, h)
    assert resp.status_code == 201
    body = resp.json()
    assert body["description"] is None
    assert body["latitude"] is None
    assert body["longitude"] is None
    assert body["location_recorded_at"] is None


def test_create_with_coordinates_records_server_location_timestamp(api_client):
    _, h = register_user(api_client, "s3@example.com")
    before = datetime.now(UTC)
    resp = _create(api_client, h, latitude=27.1751, longitude=78.0421)
    assert resp.status_code == 201
    body = resp.json()
    assert body["latitude"] == 27.1751
    assert body["longitude"] == 78.0421
    assert body["location_recorded_at"] is not None
    recorded = datetime.fromisoformat(body["location_recorded_at"])
    assert recorded >= before - timedelta(seconds=5)  # server clock, ≈now
    assert recorded.utcoffset() == timedelta(0)  # UTC on the wire


def test_coordinates_accepted_at_exact_range_edges(api_client):
    _, h = register_user(api_client, "s4@example.com")
    assert _create(api_client, h, latitude=90, longitude=180).status_code == 201
    assert _create(api_client, h, latitude=-90, longitude=-180).status_code == 201


def test_latitude_without_longitude_rejected(api_client):
    _, h = register_user(api_client, "s5@example.com")
    assert _create(api_client, h, latitude=27.1751).status_code == 422


def test_longitude_without_latitude_rejected(api_client):
    _, h = register_user(api_client, "s6@example.com")
    assert _create(api_client, h, longitude=78.0421).status_code == 422


def test_out_of_range_coordinates_rejected(api_client):
    _, h = register_user(api_client, "s7@example.com")
    assert _create(api_client, h, latitude=90.01, longitude=0).status_code == 422
    assert _create(api_client, h, latitude=-90.01, longitude=0).status_code == 422
    assert _create(api_client, h, latitude=0, longitude=180.01).status_code == 422
    assert _create(api_client, h, latitude=0, longitude=-180.01).status_code == 422


def test_blank_description_rejected(api_client):
    """Blank descriptions are refused (422), not silently stored as NULL."""
    _, h = register_user(api_client, "s8@example.com")
    assert _create(api_client, h, description="").status_code == 422
    assert _create(api_client, h, description="   ").status_code == 422


def test_overlong_description_rejected(api_client):
    _, h = register_user(api_client, "s9@example.com")
    assert _create(api_client, h, description="x" * 501).status_code == 422


def test_client_cannot_supply_server_controlled_fields(api_client):
    """Injected ownership/lifecycle/timestamp fields are 422, never honored."""
    uid, h = register_user(api_client, "s10@example.com")
    for smuggle in (
        {"user_id": "00000000-0000-0000-0000-000000000000"},
        {"status": "resolved"},
        {"id": "00000000-0000-0000-0000-000000000000"},
        {"created_at": "2000-01-01T00:00:00Z"},
        {"cancelled_at": "2000-01-01T00:00:00Z"},
        {"resolved_at": "2000-01-01T00:00:00Z"},
        {"location_recorded_at": "2000-01-01T00:00:00Z"},
    ):
        assert _create(api_client, h, **smuggle).status_code == 422, smuggle
    # The account still owns exactly its own (server-built) records.
    mine = api_client.get(BASE, headers=h).json()
    assert all(row["user_id"] == uid for row in mine)


# ------------------------------------------------------------------- auth


def test_unauthenticated_requests_rejected(api_client):
    fake = "00000000-0000-0000-0000-000000000000"
    assert api_client.post(BASE, json={}).status_code == 401
    assert api_client.get(BASE).status_code == 401
    assert api_client.get(f"{BASE}/{fake}").status_code == 401
    assert api_client.post(f"{BASE}/{fake}/cancel").status_code == 401
    assert api_client.post(f"{BASE}/{fake}/resolve").status_code == 401


def test_invalid_token_rejected(api_client):
    forged = {"Authorization": "Bearer not-a-real-token"}
    assert api_client.get(BASE, headers=forged).status_code == 401
    assert _create(api_client, forged, description="x").status_code == 401


# ---------------------------------------------------- ownership & privacy


def test_list_returns_only_own_incidents_newest_first(api_client):
    uid_a, h_a = register_user(api_client, "o1@example.com")
    _, h_b = register_user(api_client, "o2@example.com")
    _create(api_client, h_a, description="first")
    _create(api_client, h_a, description="second")
    _create(api_client, h_b, description="b-only")

    a_list = api_client.get(BASE, headers=h_a).json()
    assert [row["description"] for row in a_list] == ["second", "first"]  # newest first
    assert all(row["user_id"] == uid_a for row in a_list)

    b_list = api_client.get(BASE, headers=h_b).json()
    assert [row["description"] for row in b_list] == ["b-only"]


def test_cannot_touch_another_users_incident(api_client):
    _, h_owner = register_user(api_client, "o3@example.com")
    _, h_thief = register_user(api_client, "o4@example.com")
    mine = _create(api_client, h_owner).json()
    assert api_client.get(f"{BASE}/{mine['id']}", headers=h_thief).status_code == 404
    assert api_client.post(f"{BASE}/{mine['id']}/cancel", headers=h_thief).status_code == 404
    assert api_client.post(f"{BASE}/{mine['id']}/resolve", headers=h_thief).status_code == 404
    # The owner's record is untouched by the thief's attempts.
    assert api_client.get(f"{BASE}/{mine['id']}", headers=h_owner).json()["status"] == "active"


def test_missing_and_foreign_ids_return_identical_404(api_client):
    """No ownership probing: a foreign ID and a nonexistent ID are
    byte-identical responses."""
    _, h_owner = register_user(api_client, "o5@example.com")
    _, h_thief = register_user(api_client, "o6@example.com")
    mine = _create(api_client, h_owner).json()
    missing = api_client.get(f"{BASE}/00000000-0000-0000-0000-000000000000", headers=h_thief)
    foreign = api_client.get(f"{BASE}/{mine['id']}", headers=h_thief)
    assert missing.status_code == foreign.status_code == 404
    assert missing.content == foreign.content


# --------------------------------------------------------------- lifecycle


def test_cancel_sets_status_and_server_timestamp(api_client):
    _, h = register_user(api_client, "l1@example.com")
    mine = _create(api_client, h).json()
    before = datetime.now(UTC)
    resp = api_client.post(f"{BASE}/{mine['id']}/cancel", headers=h)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "cancelled"
    assert body["cancelled_at"] is not None
    cancelled = datetime.fromisoformat(body["cancelled_at"])
    assert cancelled >= before - timedelta(seconds=5)  # server clock, ≈now
    assert body["resolved_at"] is None


def test_resolve_sets_status_and_server_timestamp(api_client):
    _, h = register_user(api_client, "l2@example.com")
    mine = _create(api_client, h).json()
    before = datetime.now(UTC)
    resp = api_client.post(f"{BASE}/{mine['id']}/resolve", headers=h)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "resolved"
    assert body["resolved_at"] is not None
    resolved = datetime.fromisoformat(body["resolved_at"])
    assert resolved >= before - timedelta(seconds=5)  # server clock, ≈now
    assert body["cancelled_at"] is None


def test_cancelled_incident_cannot_be_resolved(api_client):
    _, h = register_user(api_client, "l3@example.com")
    mine = _create(api_client, h).json()
    first = api_client.post(f"{BASE}/{mine['id']}/cancel", headers=h).json()
    resp = api_client.post(f"{BASE}/{mine['id']}/resolve", headers=h)
    assert resp.status_code == 409
    # Record unchanged: still cancelled, original timestamp intact.
    body = api_client.get(f"{BASE}/{mine['id']}", headers=h).json()
    assert body["status"] == "cancelled"
    assert body["cancelled_at"] == first["cancelled_at"]
    assert body["resolved_at"] is None


def test_resolved_incident_cannot_be_cancelled(api_client):
    _, h = register_user(api_client, "l4@example.com")
    mine = _create(api_client, h).json()
    first = api_client.post(f"{BASE}/{mine['id']}/resolve", headers=h).json()
    resp = api_client.post(f"{BASE}/{mine['id']}/cancel", headers=h)
    assert resp.status_code == 409
    body = api_client.get(f"{BASE}/{mine['id']}", headers=h).json()
    assert body["status"] == "resolved"
    assert body["resolved_at"] == first["resolved_at"]
    assert body["cancelled_at"] is None


def test_repeated_transitions_conflict_and_keep_first_timestamp(api_client):
    """Terminal states are locked: repeats are 409, never silent no-ops
    (unlike Phase 4's idempotent /complete - SOS repeats conflict)."""
    _, h = register_user(api_client, "l5@example.com")
    cancelled = _create(api_client, h, description="c-twice").json()
    first = api_client.post(f"{BASE}/{cancelled['id']}/cancel", headers=h).json()
    again = api_client.post(f"{BASE}/{cancelled['id']}/cancel", headers=h)
    assert again.status_code == 409
    assert again.json()["detail"]  # a clear error body, not an incident body
    assert again.json().get("cancelled_at") is None  # no incident fields
    after = api_client.get(f"{BASE}/{cancelled['id']}", headers=h).json()
    assert after["cancelled_at"] == first["cancelled_at"]  # first time kept

    resolved = _create(api_client, h, description="r-twice").json()
    api_client.post(f"{BASE}/{resolved['id']}/resolve", headers=h)
    assert api_client.post(f"{BASE}/{resolved['id']}/resolve", headers=h).status_code == 409


def test_cancel_and_resolve_ignore_client_supplied_timestamps(api_client):
    """The transition routes take NO body, so a client timestamp is
    never applied - the server clock always wins."""
    _, h = register_user(api_client, "l6@example.com")
    mine = _create(api_client, h).json()
    ancient = "2000-01-01T00:00:00Z"
    resp = api_client.post(f"{BASE}/{mine['id']}/resolve", json={"resolved_at": ancient}, headers=h)
    assert resp.status_code == 200
    assert resp.json()["resolved_at"] != ancient
    assert datetime.fromisoformat(resp.json()["resolved_at"]) > datetime(2001, 1, 1, tzinfo=UTC)


def test_failed_transition_leaves_record_and_timestamps_unchanged(api_client):
    _, h = register_user(api_client, "l7@example.com")
    mine = _create(api_client, h, description="unchanged").json()
    assert api_client.post(f"{BASE}/{mine['id']}/resolve", headers=h).status_code == 200
    # Snapshot the resolved record, then try an invalid move
    # (resolved -> cancel): nothing at all may change.
    before = api_client.get(f"{BASE}/{mine['id']}", headers=h).json()
    assert api_client.post(f"{BASE}/{mine['id']}/cancel", headers=h).status_code == 409
    after = api_client.get(f"{BASE}/{mine['id']}", headers=h).json()
    assert after["status"] == before["status"] == "resolved"
    assert after["created_at"] == before["created_at"]
    assert after["updated_at"] == before["updated_at"]
    assert after["resolved_at"] == before["resolved_at"]
    assert after["cancelled_at"] is None


# ------------------------------------------------------------ persistence


def test_persisted_row_matches_response(api_client, db_session):
    from sqlalchemy import select

    from app.models.sos_event import SosEvent

    uid_str, h = register_user(api_client, "p1@example.com")
    resp = _create(
        api_client, h, description="group of three, dark street", latitude=1.3, longitude=103.8
    )
    api_value = resp.json()

    row = db_session.scalar(select(SosEvent).where(SosEvent.id == UUID(api_value["id"])))
    assert row is not None
    assert row.user_id == UUID(uid_str)
    assert row.status == "active"
    assert row.description == "group of three, dark street"
    assert row.latitude == 1.3
    assert row.longitude == 103.8
    assert row.location_recorded_at is not None
    assert row.resolved_at is None and row.cancelled_at is None


# --------------------------------------------------------- safety boundary


def test_activation_writes_only_a_row(api_client, db_session):
    """Phase 5 records an incident locally and does NOTHING outward: no
    notification flag in the response, no dispatcher, no contacts."""
    from sqlalchemy import func, select

    from app.models.community_report import CommunityReport

    _, h = register_user(api_client, "b1@example.com")
    body = _create(api_client, h, description="test", latitude=27.1, longitude=78.0).json()
    # Exact approved field set - no 'notified', 'dispatched', 'alert', ...
    assert set(body) == READ_FIELDS
    # No other safety table was touched.
    count = db_session.scalar(select(func.count()).select_from(CommunityReport))
    assert count == 0
