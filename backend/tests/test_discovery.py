"""Endpoint tests for travel-buddy discovery and public profiles (Phase 7).

These prove the discovery guarantees the phase brief demands: mandatory
eligibility and privacy filters run first; destinations, dates, and
preferences are honoured; the searcher never sees themselves, private
plans, hidden profiles, or ineligible accounts; dedupe collapses a
traveller's multiple plans into one result; pagination and filters are
bounded and validated; and results never leak account fields.

The verification GATE on the searcher (403 when policy is on and the
account is not verified) is proven in test_verification.py and is
re-proved here for the new /travel-buddies/discover route.
"""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.core.policy import set_policy
from app.models import TravelPlan, TravelProfile, User
from tests.conftest import register_user

DISCOVER_PATH = "/api/v1/travel-buddies/discover"
PROFILE_PATH = "/api/v1/travel-profile"
PLANS_PATH = "/api/v1/travel-plans"

TODAY = datetime.now(UTC).date()


def _session(engine):
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    return factory()


def _set_verification(engine, email: str, state: str) -> None:
    """Set verification state directly (test shortcut for review outcomes)."""
    db = _session(engine)
    try:
        user = db.scalar(select(User).where(User.email == email))
        user.verification_status = state
        db.commit()
    finally:
        db.close()


def _flip_policy(engine, required: bool, changed_by_email: str) -> None:
    """Set the live social policy via the real writer (audited upsert)."""
    db = _session(engine)
    try:
        owner = db.scalar(select(User).where(User.email == changed_by_email))
        set_policy(db, value=required, changed_by=owner.id)
        db.commit()
    finally:
        db.close()


def _seed_candidate(
    engine,
    email: str,
    *,
    nickname="Traveller",
    destination="Goa",
    region=None,
    start=None,
    end=None,
    flexible=False,
    discoverable=True,
    plan_visibility="discoverable",
    plan_status="active",
    interests=None,
    styles=None,
    languages=None,
) -> None:
    """Give a user a travel profile and one plan, all in one step.

    The account row is created directly when it does not exist yet:
    these candidate users never authenticate (they are discovery
    fixtures), so a dummy password hash and the default unverified
    state are enough.
    """
    db = _session(engine)
    try:
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            user = User(email=email, password_hash="fixture-not-a-login", display_name=nickname)
            db.add(user)
            db.flush()
        db.add(
            TravelProfile(
                user_id=user.id,
                travel_nickname=nickname,
                discoverable=discoverable,
                interests=interests,
                travel_styles=styles,
                languages=languages,
            )
        )
        dest = destination.casefold()
        db.add(
            TravelPlan(
                user_id=user.id,
                destination=destination,
                destination_normalized=dest,
                region=region,
                region_normalized=region.casefold() if region else None,
                start_date=start or (TODAY + timedelta(days=30)),
                end_date=end or (TODAY + timedelta(days=37)),
                flexible_dates=flexible,
                status=plan_status,
                visibility=plan_visibility,
            )
        )
        db.commit()
    finally:
        db.close()


def _make_searcher(api_client, tag="searcher"):
    email = f"{tag}-{uuid.uuid4().hex[:8]}@example.com"
    uid, headers = register_user(api_client, email, display_name=tag)
    return uid, headers, email


# --- gate and authentication ----------------------------------------------


def test_discover_requires_authentication(api_client) -> None:
    assert api_client.get(DISCOVER_PATH).status_code == 401


def test_unverified_searcher_denied_when_policy_on(api_client, sqlite_engine) -> None:
    uid, h, email = _make_searcher(api_client)
    _flip_policy(sqlite_engine, True, email)
    resp = api_client.get(DISCOVER_PATH, headers=h)
    assert resp.status_code == 403
    assert "verification" in resp.json()["detail"].lower()


def test_unverified_searcher_passes_when_policy_off(api_client, sqlite_engine) -> None:
    uid, h, email = _make_searcher(api_client)
    _flip_policy(sqlite_engine, False, email)
    resp = api_client.get(DISCOVER_PATH, headers=h)
    assert resp.status_code == 200


# --- eligibility and matching ---------------------------------------------


def test_matching_candidate_is_returned_with_score(api_client, sqlite_engine) -> None:
    _, h, me = _make_searcher(api_client)
    _flip_policy(sqlite_engine, False, me)
    _seed_candidate(
        sqlite_engine,
        "cand-a@example.com",
        destination="Goa",
        start=TODAY + timedelta(days=10),
        end=TODAY + timedelta(days=15),
    )
    resp = api_client.get(f"{DISCOVER_PATH}?destination=Goa", headers=h)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["total"] == 1
    item = data["results"][0]
    assert item["plan"]["destination"] == "Goa"
    assert item["compatibility_score"] >= 40  # destination credit at minimum
    assert item["existing_request"] == "none"
    assert "not a guarantee" in data["note"]  # honesty note travels with the score


def test_incompatible_destination_excluded(api_client, sqlite_engine) -> None:
    _, h, me = _make_searcher(api_client)
    _flip_policy(sqlite_engine, False, me)
    _seed_candidate(sqlite_engine, "cand-b@example.com", destination="Manali")
    resp = api_client.get(f"{DISCOVER_PATH}?destination=Goa", headers=h)
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


def test_overlapping_dates_included_nonoverlapping_excluded(api_client, sqlite_engine) -> None:
    _, h, me = _make_searcher(api_client)
    _flip_policy(sqlite_engine, False, me)
    # Overlaps the requested window.
    _seed_candidate(
        sqlite_engine,
        "overlap@example.com",
        destination="Goa",
        start=TODAY + timedelta(days=5),
        end=TODAY + timedelta(days=12),
    )
    # Starts after the window closes.
    _seed_candidate(
        sqlite_engine,
        "late@example.com",
        destination="Goa",
        start=TODAY + timedelta(days=40),
        end=TODAY + timedelta(days=47),
    )
    resp = api_client.get(
        f"{DISCOVER_PATH}?destination=Goa&start_date={TODAY + timedelta(days=10)}"
        f"&end_date={TODAY + timedelta(days=20)}",
        headers=h,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["results"][0]["plan"]["start_date"] == str(TODAY + timedelta(days=5))


def test_flexible_plan_scores_lower_than_strict_overlap(api_client, sqlite_engine) -> None:
    _, h, me = _make_searcher(api_client)
    _flip_policy(sqlite_engine, False, me)
    strict = f"strict-{uuid.uuid4().hex[:6]}@example.com"
    flexible = f"flex-{uuid.uuid4().hex[:6]}@example.com"
    # Strict overlap.
    _seed_candidate(
        sqlite_engine,
        strict,
        destination="Goa",
        start=TODAY + timedelta(days=10),
        end=TODAY + timedelta(days=20),
    )
    # Near miss (ends 2 days before the window opens) saved by grace.
    _seed_candidate(
        sqlite_engine,
        flexible,
        destination="Goa",
        start=TODAY + timedelta(days=1),
        end=TODAY + timedelta(days=8),
        flexible=True,
    )
    resp = api_client.get(
        f"{DISCOVER_PATH}?destination=Goa&start_date={TODAY + timedelta(days=10)}"
        f"&end_date={TODAY + timedelta(days=20)}",
        headers=h,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    # Ranking: strict (30 date credit) above flexible (15 date credit).
    assert data["results"][0]["compatibility_score"] > data["results"][1]["compatibility_score"]


def test_searcher_is_never_in_their_own_results(api_client, sqlite_engine) -> None:
    _, h, me = _make_searcher(api_client)
    _flip_policy(sqlite_engine, False, me)
    _seed_candidate(sqlite_engine, me, destination="Goa")  # me, discoverable
    resp = api_client.get(f"{DISCOVER_PATH}?destination=Goa", headers=h)
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


def test_duplicate_plans_collapse_to_one_result(api_client, sqlite_engine) -> None:
    _, h, me = _make_searcher(api_client)
    _flip_policy(sqlite_engine, False, me)
    # One traveller with TWO matching Goa plans.
    _seed_candidate(sqlite_engine, "two-plans@example.com", destination="Goa")
    db = _session(sqlite_engine)
    try:
        user = db.scalar(select(User).where(User.email == "two-plans@example.com"))
        db.add(
            TravelPlan(
                user_id=user.id,
                destination="Goa",
                destination_normalized="goa",
                start_date=TODAY + timedelta(days=60),
                end_date=TODAY + timedelta(days=67),
                status="active",
                visibility="discoverable",
            )
        )
        db.commit()
    finally:
        db.close()
    resp = api_client.get(f"{DISCOVER_PATH}?destination=Goa", headers=h)
    assert resp.status_code == 200
    assert resp.json()["total"] == 1  # deduped to a single user


def test_private_plan_and_hidden_profile_and_expired_excluded(api_client, sqlite_engine) -> None:
    _, h, me = _make_searcher(api_client)
    _flip_policy(sqlite_engine, False, me)
    _seed_candidate(
        sqlite_engine, "private-plan@example.com", destination="Goa", plan_visibility="private"
    )
    _seed_candidate(
        sqlite_engine, "hidden-profile@example.com", destination="Goa", discoverable=False
    )
    _seed_candidate(
        sqlite_engine,
        "expired@example.com",
        destination="Goa",
        start=TODAY - timedelta(days=40),
        end=TODAY - timedelta(days=33),  # ended a week ago
    )
    _seed_candidate(sqlite_engine, "paused@example.com", destination="Goa", plan_status="paused")
    resp = api_client.get(f"{DISCOVER_PATH}?destination=Goa", headers=h)
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


def test_unverified_candidate_hidden_when_policy_on(api_client, sqlite_engine) -> None:
    _, h, me = _make_searcher(api_client)
    _flip_policy(sqlite_engine, True, me)
    _set_verification(sqlite_engine, me, "verified")
    _seed_candidate(sqlite_engine, "unverified-cand@example.com", destination="Goa")
    _seed_candidate(sqlite_engine, "verified-cand@example.com", destination="Goa")
    _set_verification(sqlite_engine, "verified-cand@example.com", "verified")

    resp = api_client.get(f"{DISCOVER_PATH}?destination=Goa", headers=h)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["results"][0]["display_name"] == "Traveller"  # nickname of the verified one


def test_accepted_partner_disappears_from_discovery(api_client, sqlite_engine) -> None:
    """An accepted request removes BOTH parties from each other's results."""
    _, h, me = _make_searcher(api_client)
    _flip_policy(sqlite_engine, False, me)
    _seed_candidate(sqlite_engine, "buddy@example.com", destination="Goa")
    # Fabricate an accepted relationship (state machine proven elsewhere).
    db = _session(sqlite_engine)
    try:
        searcher = db.scalar(select(User).where(User.email == me))
        buddy = db.scalar(select(User).where(User.email == "buddy@example.com"))
        from app.models import TravelPartnerRequest

        db.add(
            TravelPartnerRequest(
                requester_id=searcher.id,
                recipient_id=buddy.id,
                status="accepted",
            )
        )
        db.commit()
    finally:
        db.close()
    resp = api_client.get(f"{DISCOVER_PATH}?destination=Goa", headers=h)
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


# --- filters and pagination ------------------------------------------------


def test_interest_style_language_filters_narrow_results(api_client, sqlite_engine) -> None:
    _, h, me = _make_searcher(api_client)
    _flip_policy(sqlite_engine, False, me)
    _seed_candidate(
        sqlite_engine,
        "hiker@example.com",
        destination="Goa",
        interests=["hiking", "food"],
        styles=["solo"],
        languages=["english"],
    )
    _seed_candidate(
        sqlite_engine,
        "diver@example.com",
        destination="Goa",
        interests=["diving"],
        styles=["luxury"],
        languages=["french"],
    )
    base = api_client.get(f"{DISCOVER_PATH}?destination=Goa", headers=h).json()
    assert base["total"] == 2

    by_interest = api_client.get(
        f"{DISCOVER_PATH}?destination=Goa&interests=hiking", headers=h
    ).json()
    assert by_interest["total"] == 1

    by_style = api_client.get(
        f"{DISCOVER_PATH}?destination=Goa&travel_style=solo", headers=h
    ).json()
    assert by_style["total"] == 1

    by_language = api_client.get(
        f"{DISCOVER_PATH}?destination=Goa&language=french", headers=h
    ).json()
    assert by_language["total"] == 1


def test_min_score_filters_and_is_bounded(api_client, sqlite_engine) -> None:
    _, h, me = _make_searcher(api_client)
    _flip_policy(sqlite_engine, False, me)
    # Without a place filter and without shared preferences, a candidate
    # scores 0; with min_score=1 they are dropped.
    _seed_candidate(sqlite_engine, "low@example.com", destination="Goa")
    keep = api_client.get(f"{DISCOVER_PATH}?destination=Goa&min_score=40", headers=h).json()
    assert keep["total"] == 1  # destination credit is 40
    drop = api_client.get(f"{DISCOVER_PATH}?min_score=1", headers=h).json()
    assert drop["total"] == 0  # no place filter -> no place credit -> score 0
    # min_score out of range is rejected.
    assert api_client.get(f"{DISCOVER_PATH}?min_score=101", headers=h).status_code == 422


def test_pagination_offset_limit_is_deterministic(api_client, sqlite_engine) -> None:
    _, h, me = _make_searcher(api_client)
    _flip_policy(sqlite_engine, False, me)
    for i in range(5):
        _seed_candidate(
            sqlite_engine,
            f"page-{i}@example.com",
            destination="Goa",
            start=TODAY + timedelta(days=10 + i),
            end=TODAY + timedelta(days=15 + i),
        )
    page1 = api_client.get(f"{DISCOVER_PATH}?destination=Goa&limit=2&offset=0", headers=h).json()
    page2 = api_client.get(f"{DISCOVER_PATH}?destination=Goa&limit=2&offset=2", headers=h).json()
    assert page1["total"] == page2["total"] == 5
    assert len(page1["results"]) == 2 and len(page2["results"]) == 2
    ids1 = [r["user_id"] for r in page1["results"]]
    ids2 = [r["user_id"] for r in page2["results"]]
    assert not set(ids1) & set(ids2)  # stable, non-overlapping pages
    # Re-fetching page 1 yields the identical order (determinism).
    again = api_client.get(f"{DISCOVER_PATH}?destination=Goa&limit=2&offset=0", headers=h).json()
    assert [r["user_id"] for r in again["results"]] == ids1


def test_limit_over_100_rejected(api_client, sqlite_engine) -> None:
    _, h, me = _make_searcher(api_client)
    _flip_policy(sqlite_engine, False, me)
    assert api_client.get(f"{DISCOVER_PATH}?limit=101", headers=h).status_code == 422


def test_malformed_date_filter_rejected(api_client, sqlite_engine) -> None:
    _, h, me = _make_searcher(api_client)
    _flip_policy(sqlite_engine, False, me)
    assert api_client.get(f"{DISCOVER_PATH}?start_date=not-a-date", headers=h).status_code == 422
    inverted = api_client.get(
        f"{DISCOVER_PATH}?start_date={TODAY}&end_date={TODAY - timedelta(days=1)}", headers=h
    )
    assert inverted.status_code == 422


def test_empty_result_is_200_with_empty_list(api_client, sqlite_engine) -> None:
    _, h, me = _make_searcher(api_client)
    _flip_policy(sqlite_engine, False, me)
    resp = api_client.get(f"{DISCOVER_PATH}?destination=Atlantis", headers=h)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0 and data["results"] == []


# --- privacy of results ----------------------------------------------------


def test_discovery_results_never_leak_account_fields(api_client, sqlite_engine) -> None:
    _, h, me = _make_searcher(api_client)
    _flip_policy(sqlite_engine, True, me)
    _set_verification(sqlite_engine, me, "verified")
    _seed_candidate(
        sqlite_engine,
        "leaky@example.com",
        destination="Goa",
        nickname="SafeName",
        interests=["hiking"],
        languages=["english"],
    )
    _set_verification(sqlite_engine, "leaky@example.com", "verified")
    item = api_client.get(f"{DISCOVER_PATH}?destination=Goa", headers=h).json()["results"][0]
    forbidden = {"email", "phone", "role", "verification_status", "password", "firebase_uid"}
    assert forbidden.isdisjoint(item.keys())
    assert item["display_name"] == "SafeName"
    # The plan summary is limited to trip facts, no owner identity.
    assert "user_id" not in item["plan"]


def test_region_filter_matches_broad_region(api_client, sqlite_engine) -> None:
    _, h, me = _make_searcher(api_client)
    _flip_policy(sqlite_engine, False, me)
    _seed_candidate(sqlite_engine, "goa-region@example.com", region="Goa")
    _seed_candidate(sqlite_engine, "kerala-region@example.com", region="Kerala")
    resp = api_client.get(f"{DISCOVER_PATH}?region=goa", headers=h)
    assert resp.status_code == 200
    assert resp.json()["total"] == 1


# --- public profile route --------------------------------------------------


def test_public_profile_requires_authentication(api_client) -> None:
    assert api_client.get(f"/api/v1/travel-buddies/{uuid.uuid4()}").status_code == 401


def test_public_profile_of_eligible_user_is_limited(api_client, sqlite_engine) -> None:
    _, h, me = _make_searcher(api_client)
    _flip_policy(sqlite_engine, False, me)
    _seed_candidate(sqlite_engine, "pub@example.com", nickname="PublicNick", destination="Goa")
    db = _session(sqlite_engine)
    try:
        target = db.scalar(select(User).where(User.email == "pub@example.com"))
        target_id = str(target.id)
    finally:
        db.close()
    resp = api_client.get(f"/api/v1/travel-buddies/{target_id}", headers=h)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["display_name"] == "PublicNick"
    forbidden = {"email", "phone", "role", "verification_status"}
    assert forbidden.isdisjoint(data.keys())
    assert data["plan"]["destination"] == "Goa"


def test_public_profile_404_for_hidden_or_unknown_or_self(api_client, sqlite_engine) -> None:
    uid, h, me = _make_searcher(api_client)
    _flip_policy(sqlite_engine, False, me)
    _seed_candidate(sqlite_engine, "hidden@example.com", discoverable=False, destination="Goa")

    db = _session(sqlite_engine)
    try:
        hidden = db.scalar(select(User).where(User.email == "hidden@example.com"))
        hidden_id = str(hidden.id)
    finally:
        db.close()

    hidden_resp = api_client.get(f"/api/v1/travel-buddies/{hidden_id}", headers=h)
    unknown_resp = api_client.get(f"/api/v1/travel-buddies/{uuid.uuid4()}", headers=h)
    self_resp = api_client.get(f"/api/v1/travel-buddies/{uid}", headers=h)
    # Hidden, unknown, and self all return the SAME 404 body.
    assert hidden_resp.status_code == unknown_resp.status_code == self_resp.status_code == 404
    assert hidden_resp.json() == unknown_resp.json() == self_resp.json()
