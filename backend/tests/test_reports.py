"""Community safety report endpoint tests (Phase 6).

Covers authentication on all four routes, strict creation validation
(closed category set, description rules, coordinate ranges, strict
bodies), public-read privacy (submitter identity never exposed),
moderation visibility (`rejected` hidden everywhere), category/status
filters, offset/limit pagination bounds, and the nearby search
(radius unit/bounds, ordering, antimeridian wrap, high latitudes,
NULL-coordinate rows).
"""

from uuid import UUID

from tests.conftest import register_user

BASE = "/api/v1/reports"

READ_FIELDS = {
    "id",
    "category",
    "status",
    "description",
    "latitude",
    "longitude",
    "created_at",
    "updated_at",
}

ALL_CATEGORIES = [
    "unsafe_area",
    "harassment",
    "suspicious_activity",
    "road_hazard",
    "poor_lighting",
    "other",
]


def _create(client, headers, **overrides):
    payload = {
        "category": "poor_lighting",
        "description": "dark street behind the station",
        "latitude": 28.6139,
        "longitude": 77.2090,
    }
    payload.update(overrides)
    return client.post(BASE, json=payload, headers=headers)


def _seed_report(db_session, user_id, **overrides):
    """Insert a report directly into the shared test database.

    Needed for rows the API cannot create (approved/rejected statuses,
    NULL coordinates) - the moderation states belong to a future phase.
    """
    from app.models.community_report import CommunityReport
    from app.models.enums import ReportStatus

    fields = {
        "user_id": user_id,
        "category": "road_hazard",
        "description": "seeded row",
        "latitude": 28.60,
        "longitude": 77.20,
        "status": ReportStatus.PENDING,
    }
    fields.update(overrides)
    report = CommunityReport(**fields)
    db_session.add(report)
    db_session.commit()
    return report


# --------------------------------------------------------------- creation


def test_create_report_returns_pending_with_public_fields(api_client):
    uid, h = register_user(api_client, "r1@example.com")
    resp = _create(api_client, h)
    assert resp.status_code == 201
    body = resp.json()
    assert set(body) == READ_FIELDS  # exactly these 8 - never user_id/email
    assert body["status"] == "pending"  # server-chosen, not client
    assert body["category"] == "poor_lighting"
    assert body["description"] == "dark street behind the station"
    assert body["latitude"] == 28.6139
    assert body["longitude"] == 77.2090
    UUID(body["id"])  # valid UUID
    assert "user_id" not in body and uid is not None


def test_all_six_categories_accepted(api_client):
    _, h = register_user(api_client, "r2@example.com")
    for category in ALL_CATEGORIES:
        resp = _create(api_client, h, category=category)
        assert resp.status_code == 201, category
        assert resp.json()["category"] == category


def test_unknown_category_rejected(api_client):
    _, h = register_user(api_client, "r3@example.com")
    assert _create(api_client, h, category="theft").status_code == 422
    assert _create(api_client, h, category="").status_code == 422


def test_missing_required_fields_rejected(api_client):
    _, h = register_user(api_client, "r4@example.com")
    assert api_client.post(BASE, json={}, headers=h).status_code == 422
    assert _create(api_client, h, category=None).status_code == 422
    assert _create(api_client, h, description=None).status_code == 422
    assert _create(api_client, h, latitude=None).status_code == 422
    assert _create(api_client, h, longitude=None).status_code == 422


def test_blank_or_overlong_description_rejected(api_client):
    _, h = register_user(api_client, "r5@example.com")
    assert _create(api_client, h, description="").status_code == 422
    assert _create(api_client, h, description="   ").status_code == 422
    assert _create(api_client, h, description="x" * 501).status_code == 422


def test_out_of_range_coordinates_rejected(api_client):
    _, h = register_user(api_client, "r6@example.com")
    assert _create(api_client, h, latitude=90.01).status_code == 422
    assert _create(api_client, h, latitude=-90.01).status_code == 422
    assert _create(api_client, h, longitude=180.01).status_code == 422
    assert _create(api_client, h, longitude=-180.01).status_code == 422
    # Exact edges are accepted.
    assert _create(api_client, h, latitude=90, longitude=180).status_code == 201
    assert _create(api_client, h, latitude=-90, longitude=-180).status_code == 201


def test_client_cannot_supply_server_controlled_fields(api_client):
    _, h = register_user(api_client, "r7@example.com")
    for smuggle in (
        {"user_id": "00000000-0000-0000-0000-000000000000"},
        {"status": "approved"},
        {"id": "00000000-0000-0000-0000-000000000000"},
        {"created_at": "2000-01-01T00:00:00Z"},
        {"updated_at": "2000-01-01T00:00:00Z"},
    ):
        assert _create(api_client, h, **smuggle).status_code == 422, smuggle


# ------------------------------------------------------------------- auth


def test_unauthenticated_requests_rejected(api_client):
    fake = "00000000-0000-0000-0000-000000000000"
    assert api_client.post(BASE, json={}).status_code == 401
    assert api_client.get(BASE).status_code == 401
    assert api_client.get(f"{BASE}/nearby?latitude=0&longitude=0&radius_m=100").status_code == 401
    assert api_client.get(f"{BASE}/{fake}").status_code == 401


def test_invalid_token_rejected(api_client):
    forged = {"Authorization": "Bearer not-a-real-token"}
    assert api_client.get(BASE, headers=forged).status_code == 401
    assert _create(api_client, forged).status_code == 401


# ------------------------------------------------------- reads & privacy


def test_get_report_by_id(api_client):
    _, h = register_user(api_client, "p1@example.com")
    created = _create(api_client, h, description="blocked alley").json()
    resp = api_client.get(f"{BASE}/{created['id']}", headers=h)
    assert resp.status_code == 200
    assert resp.json() == created


def test_get_missing_report_404(api_client):
    _, h = register_user(api_client, "p2@example.com")
    resp = api_client.get(f"{BASE}/00000000-0000-0000-0000-000000000000", headers=h)
    assert resp.status_code == 404
    assert resp.json() == {"detail": "Report not found."}


def test_list_is_newest_first_and_shares_no_identity(api_client):
    """Reports are community content: every authenticated user sees them,
    and no response ever carries the submitter's identity."""
    _, h_a = register_user(api_client, "p3@example.com")
    _, h_b = register_user(api_client, "p4@example.com")
    _create(api_client, h_a, description="first")
    _create(api_client, h_a, description="second")

    # A different user sees the same reports (public read, no identity).
    b_view = api_client.get(BASE, headers=h_b).json()
    a_view = api_client.get(BASE, headers=h_a).json()
    assert [row["description"] for row in b_view] == ["second", "first"]
    assert b_view == a_view  # identical for every viewer
    for row in b_view:
        assert set(row) == READ_FIELDS  # never user_id, email, phone, ...


def test_persisted_row_matches_response_and_stores_user(api_client, db_session):
    from sqlalchemy import select

    from app.models.community_report import CommunityReport

    uid_str, h = register_user(api_client, "p5@example.com")
    body = _create(api_client, h, category="harassment").json()
    row = db_session.scalar(select(CommunityReport).where(CommunityReport.id == UUID(body["id"])))
    assert row is not None
    # The submitter IS stored (accountability) but never returned.
    assert row.user_id == UUID(uid_str)
    assert row.status == "pending"
    assert row.category == "harassment"
    assert "user_id" not in body


# --------------------------------------------- moderation & visibility


def test_rejected_reports_are_hidden_everywhere(api_client, db_session):
    """`rejected` rows are invisible: list, nearby, and get-by-id all
    behave as if they never existed (identical 404 for get)."""
    _, h = register_user(api_client, "m1@example.com")
    hidden = _seed_report(
        db_session,
        UUID(register_user(api_client, "m2@example.com")[0]),
        status="rejected",
        description="hidden row",
    )
    _create(api_client, h, description="visible row")

    listed = api_client.get(BASE, headers=h).json()
    assert [row["description"] for row in listed] == ["visible row"]

    got = api_client.get(f"{BASE}/{hidden.id}", headers=h)
    assert got.status_code == 404
    missing = api_client.get(f"{BASE}/00000000-0000-0000-0000-000000000000", headers=h)
    assert got.content == missing.content  # indistinguishable

    nearby = api_client.get(
        f"{BASE}/nearby?latitude=28.60&longitude=77.20&radius_m=50000", headers=h
    ).json()
    assert all(row["description"] != "hidden row" for row in nearby)


def test_status_filter_allows_pending_and_approved_but_not_rejected(api_client, db_session):
    _, h = register_user(api_client, "m3@example.com")
    uid = UUID(register_user(api_client, "m4@example.com")[0])
    _seed_report(db_session, uid, status="approved", description="moderated row")
    _create(api_client, h, description="fresh row")

    approved = api_client.get(f"{BASE}?status=approved", headers=h).json()
    assert [row["description"] for row in approved] == ["moderated row"]
    assert all(row["status"] == "approved" for row in approved)

    pending = api_client.get(f"{BASE}?status=pending", headers=h).json()
    assert [row["description"] for row in pending] == ["fresh row"]

    # Rejected is hidden, not filterable.
    assert api_client.get(f"{BASE}?status=rejected", headers=h).status_code == 422
    assert api_client.get(f"{BASE}?status=bogus", headers=h).status_code == 422


def test_category_filter(api_client):
    _, h = register_user(api_client, "m5@example.com")
    _create(api_client, h, category="road_hazard", description="r1")
    _create(api_client, h, category="unsafe_area", description="u1")
    _create(api_client, h, category="road_hazard", description="r2")

    roads = api_client.get(f"{BASE}?category=road_hazard", headers=h).json()
    assert [row["description"] for row in roads] == ["r2", "r1"]
    assert api_client.get(f"{BASE}?category=theft", headers=h).status_code == 422


# ----------------------------------------------------------- pagination


def test_pagination_offset_and_limit(api_client):
    _, h = register_user(api_client, "g1@example.com")
    for i in range(3):
        _create(api_client, h, description=f"report {i}")

    first_page = api_client.get(f"{BASE}?limit=2", headers=h).json()
    assert [row["description"] for row in first_page] == ["report 2", "report 1"]
    second_page = api_client.get(f"{BASE}?offset=2&limit=2", headers=h).json()
    assert [row["description"] for row in second_page] == ["report 0"]
    # Default returns everything at this scale (3 < default limit 20).
    assert len(api_client.get(BASE, headers=h).json()) == 3


def test_pagination_bounds_validated(api_client):
    _, h = register_user(api_client, "g2@example.com")
    assert api_client.get(f"{BASE}?limit=0", headers=h).status_code == 422
    assert api_client.get(f"{BASE}?limit=101", headers=h).status_code == 422
    assert api_client.get(f"{BASE}?offset=-1", headers=h).status_code == 422


def test_default_limit_caps_at_twenty(api_client, db_session):
    uid = UUID(register_user(api_client, "g3@example.com")[0])
    for i in range(21):
        _seed_report(db_session, uid, description=f"bulk {i}")
    listed = api_client.get(BASE, headers=register_user(api_client, "g4@example.com")[1]).json()
    assert len(listed) == 20


# --------------------------------------------------------------- nearby


def test_nearby_includes_reports_inside_radius(api_client):
    _, h = register_user(api_client, "n1@example.com")
    # ~3 km from the report's position.
    _create(api_client, h, description="close one")
    resp = api_client.get(
        f"{BASE}/nearby?latitude=28.6300&longitude=77.2300&radius_m=10000",
        headers=h,
    )
    assert resp.status_code == 200
    assert [row["description"] for row in resp.json()] == ["close one"]


def test_nearby_excludes_reports_outside_radius(api_client):
    _, h = register_user(api_client, "n2@example.com")
    _create(api_client, h)  # Delhi
    resp = api_client.get(
        f"{BASE}/nearby?latitude=51.5007&longitude=-0.1246&radius_m=5000", headers=h
    )
    assert resp.status_code == 200
    assert resp.json() == []


def test_nearby_orders_nearest_first(api_client):
    _, h = register_user(api_client, "n3@example.com")
    _create(api_client, h, description="far", latitude=28.70, longitude=77.25)
    _create(api_client, h, description="near", latitude=28.62, longitude=77.21)
    resp = api_client.get(f"{BASE}/nearby?latitude=28.61&longitude=77.20&radius_m=50000", headers=h)
    assert [row["description"] for row in resp.json()] == ["near", "far"]


def test_nearby_radius_unit_and_bounds_validated(api_client):
    _, h = register_user(api_client, "n4@example.com")
    base = f"{BASE}/nearby?latitude=28.61&longitude=77.20"
    assert api_client.get(base, headers=h).status_code == 422  # radius required
    assert api_client.get(f"{base}&radius_m=0", headers=h).status_code == 422
    assert api_client.get(f"{base}&radius_m=-1", headers=h).status_code == 422
    assert api_client.get(f"{base}&radius_m=50001", headers=h).status_code == 422
    assert api_client.get(f"{base}&radius_m=50000", headers=h).status_code == 200  # edge ok


def test_nearby_center_coordinates_validated(api_client):
    _, h = register_user(api_client, "n5@example.com")
    base = f"{BASE}/nearby?radius_m=1000"
    assert api_client.get(f"{base}&latitude=91&longitude=0", headers=h).status_code == 422
    assert api_client.get(f"{base}&latitude=0&longitude=181", headers=h).status_code == 422
    assert api_client.get(f"{base}&longitude=0", headers=h).status_code == 422  # lat required


def test_nearby_wraps_the_antimeridian(api_client):
    """179.9°E and 179.9°W of the prime meridian are ~22 km apart across
    the antimeridian - the haversine must see them as neighbours."""
    _, h = register_user(api_client, "n6@example.com")
    _create(api_client, h, description="dateline", latitude=0.0, longitude=179.9)
    resp = api_client.get(f"{BASE}/nearby?latitude=0.0&longitude=-179.9&radius_m=25000", headers=h)
    assert [row["description"] for row in resp.json()] == ["dateline"]


def test_nearby_accurate_at_high_latitude(api_client):
    _, h = register_user(api_client, "n7@example.com")
    _create(api_client, h, description="arctic", latitude=78.0, longitude=15.0)
    resp = api_client.get(f"{BASE}/nearby?latitude=78.02&longitude=15.05&radius_m=5000", headers=h)
    assert [row["description"] for row in resp.json()] == ["arctic"]


def test_nearby_skips_rows_without_coordinates(api_client, db_session):
    """NULL-coordinate rows cannot match a distance query and must be
    skipped without errors (the API cannot create them; the DB allows)."""
    uid = UUID(register_user(api_client, "n8@example.com")[0])
    _seed_report(db_session, uid, latitude=None, longitude=None)
    _, h = register_user(api_client, "n9@example.com")
    resp = api_client.get(f"{BASE}/nearby?latitude=28.61&longitude=77.20&radius_m=50000", headers=h)
    assert resp.status_code == 200
    assert resp.json() == []


def test_nearby_category_filter_and_pagination_bounds(api_client):
    _, h = register_user(api_client, "n10@example.com")
    _create(api_client, h, category="road_hazard", description="r")
    _create(api_client, h, category="unsafe_area", description="u")
    base = f"{BASE}/nearby?latitude=28.61&longitude=77.20&radius_m=50000"
    roads = api_client.get(f"{base}&category=road_hazard", headers=h).json()
    assert [row["description"] for row in roads] == ["r"]
    assert api_client.get(f"{base}&category=theft", headers=h).status_code == 422
    assert api_client.get(f"{base}&limit=101", headers=h).status_code == 422
    assert api_client.get(f"{base}&offset=-1", headers=h).status_code == 422
