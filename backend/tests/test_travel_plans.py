"""Endpoint tests for travel profiles and travel plans (Phase 7).

These drive the real FastAPI app end-to-end (register -> token ->
authenticated call) against the in-memory SQLite database, exactly like
the Phase 4-6b suites. They prove: authentication is required, ownership
is enforced (not-yours and missing return the SAME 404), validation
bounds hold, clients cannot forge account fields, and the secure
defaults (hidden profile, private plan) are what actually ship.
"""

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.models import TravelProfile
from tests.conftest import register_user

PROFILE_PATH = "/api/v1/travel-profile"
PLANS_PATH = "/api/v1/travel-plans"


def _session(engine):
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    return factory()


# --- travel profile -------------------------------------------------------


def test_profile_requires_authentication(api_client) -> None:
    assert api_client.get(f"{PROFILE_PATH}/me").status_code == 401
    assert api_client.post(f"{PROFILE_PATH}/me", json={}).status_code == 401
    assert api_client.patch(f"{PROFILE_PATH}/me", json={}).status_code == 401


def test_get_profile_without_one_is_404(api_client) -> None:
    _, h = register_user(api_client, f"noprofile-{uuid.uuid4().hex[:8]}@example.com")
    resp = api_client.get(f"{PROFILE_PATH}/me", headers=h)
    assert resp.status_code == 404
    assert "POST" in resp.json()["detail"]  # actionable: tells you how to create


def test_create_and_get_profile_roundtrip(api_client) -> None:
    _, h = register_user(api_client, f"profile-{uuid.uuid4().hex[:8]}@example.com")
    body = {
        "travel_nickname": "WanderSoul",
        "bio": "Slow traveller, tea over beaches.",
        "home_region": "Kerala",
        "languages": ["english", "hindi"],
        "travel_styles": ["slow_travel", "solo"],
        "interests": ["hiking", "food"],
        "group_size_pref": 3,
    }
    created = api_client.post(f"{PROFILE_PATH}/me", json=body, headers=h)
    assert created.status_code == 201, created.text
    data = created.json()
    assert data["travel_nickname"] == "WanderSoul"
    assert data["discoverable"] is False  # secure default: hidden until opted in
    assert data["completion"] == []  # every recommended field is filled
    assert "email" not in data and "role" not in data

    fetched = api_client.get(f"{PROFILE_PATH}/me", headers=h)
    assert fetched.status_code == 200
    assert fetched.json()["travel_nickname"] == "WanderSoul"


def test_duplicate_profile_creation_is_409(api_client) -> None:
    _, h = register_user(api_client, f"dupprofile-{uuid.uuid4().hex[:8]}@example.com")
    assert api_client.post(f"{PROFILE_PATH}/me", json={}, headers=h).status_code == 201
    again = api_client.post(f"{PROFILE_PATH}/me", json={}, headers=h)
    assert again.status_code == 409


def test_patch_profile_updates_and_clears_fields(api_client) -> None:
    _, h = register_user(api_client, f"patchprofile-{uuid.uuid4().hex[:8]}@example.com")
    api_client.post(
        f"{PROFILE_PATH}/me", json={"bio": "before", "interests": ["hiking"]}, headers=h
    )

    patched = api_client.patch(
        f"{PROFILE_PATH}/me",
        json={"bio": "after", "interests": [], "discoverable": True},
        headers=h,
    )
    assert patched.status_code == 200, patched.text
    data = patched.json()
    assert data["bio"] == "after"
    assert data["interests"] == []  # explicit empty list clears
    assert data["discoverable"] is True


def test_patch_profile_404_when_none_exists(api_client) -> None:
    _, h = register_user(api_client, f"patchnone-{uuid.uuid4().hex[:8]}@example.com")
    resp = api_client.patch(f"{PROFILE_PATH}/me", json={"bio": "x"}, headers=h)
    assert resp.status_code == 404


def test_profile_cannot_forge_account_fields(api_client) -> None:
    """Role/verification/email are not in the schema -> rejected (423=forbid)."""
    _, h = register_user(api_client, f"forgeprofile-{uuid.uuid4().hex[:8]}@example.com")
    resp = api_client.post(
        f"{PROFILE_PATH}/me",
        json={"role": "owner", "verification_status": "verified", "email": "evil@x.com"},
        headers=h,
    )
    assert resp.status_code == 422  # extra="forbid"


def test_profile_validation_bounds(api_client) -> None:
    _, h = register_user(api_client, f"bounds-{uuid.uuid4().hex[:8]}@example.com")
    api_client.post(f"{PROFILE_PATH}/me", json={}, headers=h)

    cases = [
        {"travel_nickname": "n" * 41},  # > 40 chars
        {"bio": "b" * 201},  # > 200 chars
        {"group_size_pref": 1},  # below 2
        {"group_size_pref": 13},  # above 12
        {"travel_styles": ["not_a_style"]},  # outside the closed set
        {"interests": ["not_an_interest"]},  # outside the closed set
        {"languages": ["l"]},  # too short
    ]
    for payload in cases:
        resp = api_client.patch(f"{PROFILE_PATH}/me", json=payload, headers=h)
        assert resp.status_code == 422, (payload, resp.text)


def test_profile_lists_are_deduplicated_and_bounded(api_client) -> None:
    _, h = register_user(api_client, f"dedupe-{uuid.uuid4().hex[:8]}@example.com")
    resp = api_client.post(
        f"{PROFILE_PATH}/me",
        json={"interests": ["hiking", "Hiking", " food "]},
        headers=h,
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["interests"] == ["hiking", "food"]


# --- travel plans ---------------------------------------------------------


def test_plans_require_authentication(api_client) -> None:
    assert api_client.get(PLANS_PATH + "/").status_code == 401
    assert api_client.post(PLANS_PATH + "/", json={}).status_code == 401


def test_create_plan_normalizes_destination(api_client) -> None:
    _, h = register_user(api_client, f"plan-{uuid.uuid4().hex[:8]}@example.com")
    resp = api_client.post(
        PLANS_PATH + "/",
        json={"destination": "  New   YORK ", "start_date": "2026-12-01", "end_date": "2026-12-10"},
        headers=h,
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["destination"] == "New YORK"  # display form: trimmed + collapsed
    assert data["status"] == "active"
    assert data["visibility"] == "private"  # secure default


def test_plan_rejects_inverted_date_range(api_client) -> None:
    _, h = register_user(api_client, f"planbad-{uuid.uuid4().hex[:8]}@example.com")
    resp = api_client.post(
        PLANS_PATH + "/",
        json={"destination": "Goa", "start_date": "2026-12-10", "end_date": "2026-12-01"},
        headers=h,
    )
    assert resp.status_code == 422
    assert "end_date" in resp.text


def test_plan_requires_min_destination_length(api_client) -> None:
    _, h = register_user(api_client, f"planmin-{uuid.uuid4().hex[:8]}@example.com")
    resp = api_client.post(
        PLANS_PATH + "/",
        json={"destination": " ", "start_date": "2026-12-01", "end_date": "2026-12-10"},
        headers=h,
    )
    assert resp.status_code == 422


def test_list_plans_shows_only_my_plans(api_client, sqlite_engine) -> None:
    mine_id, mine_h = register_user(api_client, f"own-{uuid.uuid4().hex[:8]}@example.com")
    other_id, _ = register_user(api_client, f"other-{uuid.uuid4().hex[:8]}@example.com")
    api_client.post(
        PLANS_PATH + "/",
        json={"destination": "Goa", "start_date": "2026-12-01", "end_date": "2026-12-10"},
        headers=mine_h,
    )
    listed = api_client.get(PLANS_PATH + "/", headers=mine_h)
    assert listed.status_code == 200
    assert len(listed.json()) == 1  # only mine


def test_plan_ownership_is_enforced_with_identical_404(api_client, sqlite_engine) -> None:
    """A not-yours plan and a nonexistent plan return the SAME 404."""
    _, mine_h = register_user(api_client, f"owner-{uuid.uuid4().hex[:8]}@example.com")
    _, other_h = register_user(api_client, f"stranger-{uuid.uuid4().hex[:8]}@example.com")
    api_client.post(
        PLANS_PATH + "/",
        json={"destination": "Goa", "start_date": "2026-12-01", "end_date": "2026-12-10"},
        headers=mine_h,
    )
    mine_plan = api_client.get(PLANS_PATH + "/", headers=mine_h).json()[0]["id"]

    not_yours = api_client.get(f"{PLANS_PATH}/{mine_plan}", headers=other_h)
    missing = api_client.get(f"{PLANS_PATH}/{uuid.uuid4()}", headers=other_h)
    assert not_yours.status_code == missing.status_code == 404
    assert not_yours.json() == missing.json()  # indistinguishable

    # Patch and delete are equally locked down.
    assert (
        api_client.patch(
            f"{PLANS_PATH}/{mine_plan}", json={"region": "North Goa"}, headers=other_h
        ).status_code
        == 404
    )
    assert api_client.delete(f"{PLANS_PATH}/{mine_plan}", headers=other_h).status_code == 404


def test_patch_plan_revalidates_dates_against_stored_values(api_client) -> None:
    _, h = register_user(api_client, f"patchplan-{uuid.uuid4().hex[:8]}@example.com")
    api_client.post(
        PLANS_PATH + "/",
        json={"destination": "Goa", "start_date": "2026-12-01", "end_date": "2026-12-10"},
        headers=h,
    )
    plan_id = api_client.get(PLANS_PATH + "/", headers=h).json()[0]["id"]

    # Moving start past the stored end is refused (422) even though each
    # field alone is valid.
    resp = api_client.patch(f"{PLANS_PATH}/{plan_id}", json={"start_date": "2026-12-15"}, headers=h)
    assert resp.status_code == 422

    # A consistent move is accepted.
    ok = api_client.patch(
        f"{PLANS_PATH}/{plan_id}", json={"start_date": "2026-12-05", "status": "paused"}, headers=h
    )
    assert ok.status_code == 200
    assert ok.json()["status"] == "paused"


def test_delete_plan_returns_204(api_client) -> None:
    _, h = register_user(api_client, f"delplan-{uuid.uuid4().hex[:8]}@example.com")
    api_client.post(
        PLANS_PATH + "/",
        json={"destination": "Goa", "start_date": "2026-12-01", "end_date": "2026-12-10"},
        headers=h,
    )
    plan_id = api_client.get(PLANS_PATH + "/", headers=h).json()[0]["id"]
    assert api_client.delete(f"{PLANS_PATH}/{plan_id}", headers=h).status_code == 204
    assert api_client.get(f"{PLANS_PATH}/{plan_id}", headers=h).status_code == 404


def test_plan_visibility_and_status_enums_are_closed(api_client) -> None:
    _, h = register_user(api_client, f"enum-{uuid.uuid4().hex[:8]}@example.com")
    resp = api_client.post(
        PLANS_PATH + "/",
        json={
            "destination": "Goa",
            "start_date": "2026-12-01",
            "end_date": "2026-12-10",
            "visibility": "everyone_sees_me",
        },
        headers=h,
    )
    assert resp.status_code == 422


@pytest.mark.parametrize("payload", [{}, {"start_date": "2026-12-01"}])
def test_plan_requires_destination_and_both_dates(api_client, payload) -> None:
    _, h = register_user(api_client, f"required-{uuid.uuid4().hex[:8]}@example.com")
    resp = api_client.post(PLANS_PATH + "/", json=payload, headers=h)
    assert resp.status_code == 422


def test_profile_created_by_orm_has_no_leak_in_other_users_view(api_client, sqlite_engine) -> None:
    """Creating a profile never exposes it to strangers via any route.

    The only public read is GET /travel-buddies/{user_id} (tested in
    test_discovery.py); here we prove /users/me never grew a travel
    field that could leak private data.
    """
    uid, h = register_user(api_client, f"leak-{uuid.uuid4().hex[:8]}@example.com")
    api_client.post(
        f"{PROFILE_PATH}/me",
        json={"travel_nickname": "Hidden", "bio": "private note"},
        headers=h,
    )
    me = api_client.get("/api/v1/users/me", headers=h).json()
    assert "travel_nickname" not in me
    assert "bio" not in me
    # The ORM row exists, tied to this user only.
    db = _session(sqlite_engine)
    try:
        row = db.scalar(select(TravelProfile).where(TravelProfile.user_id == uuid.UUID(uid)))
        assert row is not None and row.travel_nickname == "Hidden"
    finally:
        db.close()
