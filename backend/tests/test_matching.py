"""Unit tests for the PURE matching rules (Phase 7).

These tests exercise `app/core/matching.py` with no database, no HTTP,
and no fixtures - exactly the isolation the phase brief requires ("make
the matching logic testable independently from HTTP routing"). Every
assertion pins down a documented rule: normalization, the date-overlap
classification (strict / flexible-grace / none), the scoring weights and
caps, and determinism.
"""

from datetime import date, timedelta

from app.core.matching import (
    FLEXIBLE_DATE_GRACE_DAYS,
    SCORE_DATE_FLEXIBLE,
    SCORE_DATE_STRICT,
    SCORE_DESTINATION_EXACT,
    SCORE_INTEREST_CAP,
    SCORE_MAX,
    SCORE_PER_SHARED_INTEREST,
    SCORE_PER_SHARED_STYLE,
    SCORE_REGION_MATCH,
    SCORE_SHARED_LANGUAGE,
    SCORE_STYLE_CAP,
    PlanFacts,
    ProfileFacts,
    QueryFacts,
    normalize_place,
    plan_matches_window,
    score_candidate,
)

TODAY = date(2026, 12, 1)


def _plan(dest="goa", region=None, start=None, end=None, flexible=False) -> PlanFacts:
    return PlanFacts(
        destination_normalized=dest,
        region_normalized=region,
        start_date=start or TODAY,
        end_date=end or (TODAY + timedelta(days=7)),
        flexible=flexible,
    )


def _profile(interests=(), styles=(), languages=()) -> ProfileFacts:
    return ProfileFacts(
        interests=frozenset(interests),
        travel_styles=frozenset(styles),
        languages=frozenset(languages),
    )


def _query(**kwargs) -> QueryFacts:
    return QueryFacts(**kwargs)


# --- normalization --------------------------------------------------------


def test_normalize_place_casefolds_and_collapses_whitespace() -> None:
    assert normalize_place("  New   YORK ") == "new york"
    assert normalize_place("GOA") == "goa"
    assert normalize_place("Rio De Janeiro") == "rio de janeiro"
    assert normalize_place("  goa\t") == "goa"


def test_normalize_place_is_idempotent() -> None:
    once = normalize_place("  Bogotá  ")
    assert normalize_place(once) == once


# --- date window ----------------------------------------------------------


def test_strict_overlap_before_during_after() -> None:
    plan_start, plan_end = TODAY, TODAY + timedelta(days=7)
    # Query window fully inside the plan.
    assert (
        plan_matches_window(
            plan_start, plan_end, TODAY + timedelta(days=1), TODAY + timedelta(days=2), False
        )
        == "strict"
    )
    # Plan fully inside the query window.
    assert (
        plan_matches_window(
            plan_start, plan_end, TODAY - timedelta(days=3), TODAY + timedelta(days=30), False
        )
        == "strict"
    )
    # Boundary touch counts as overlap (inclusive edges).
    assert (
        plan_matches_window(plan_start, plan_end, TODAY + timedelta(days=7), None, False)
        == "strict"
    )


def test_no_overlap_non_flexible_is_none() -> None:
    plan_start, plan_end = TODAY, TODAY + timedelta(days=7)
    assert plan_matches_window(plan_start, plan_end, TODAY + timedelta(days=8), None, False) is None
    assert plan_matches_window(plan_start, plan_end, None, TODAY - timedelta(days=1), False) is None


def test_flexible_grace_captures_near_miss_only_for_flexible_plans() -> None:
    plan_start, plan_end = TODAY, TODAY + timedelta(days=7)
    window_start = plan_end + timedelta(days=FLEXIBLE_DATE_GRACE_DAYS - 1)
    # Flexible: near miss within grace -> "flexible".
    assert plan_matches_window(plan_start, plan_end, window_start, None, True) == "flexible"
    # Rigid: same near miss -> excluded.
    assert plan_matches_window(plan_start, plan_end, window_start, None, False) is None
    # Beyond grace, even flexible is excluded.
    far = plan_end + timedelta(days=FLEXIBLE_DATE_GRACE_DAYS + 1)
    assert plan_matches_window(plan_start, plan_end, far, None, True) is None


def test_open_ended_windows_only_enforce_the_given_side() -> None:
    plan_start, plan_end = TODAY, TODAY + timedelta(days=7)
    assert plan_matches_window(plan_start, plan_end, None, None, False) == "strict"
    assert (
        plan_matches_window(plan_start, plan_end, TODAY + timedelta(days=1), None, False)
        == "strict"
    )
    assert plan_matches_window(plan_start, plan_end, None, plan_start, False) == "strict"


# --- scoring --------------------------------------------------------------


def test_destination_match_scores_full_destination_credit() -> None:
    breakdown = score_candidate(_plan(dest="goa"), _profile(), _query(destination_normalized="goa"))
    assert breakdown.destination == SCORE_DESTINATION_EXACT
    assert breakdown.total == SCORE_DESTINATION_EXACT


def test_region_match_scores_region_credit_when_no_destination_filter() -> None:
    breakdown = score_candidate(
        _plan(dest="goa", region="goa"), _profile(), _query(region_normalized="goa")
    )
    assert breakdown.destination == SCORE_REGION_MATCH
    # Mismatched region scores zero.
    miss = score_candidate(
        _plan(dest="goa", region="kerala"), _profile(), _query(region_normalized="goa")
    )
    assert miss.destination == 0


def test_no_place_filter_scores_no_place_credit() -> None:
    breakdown = score_candidate(_plan(dest="goa"), _profile(), _query())
    assert breakdown.destination == 0


def test_date_overlap_strict_beats_flexible_and_no_window() -> None:
    plan = _plan(start=TODAY, end=TODAY + timedelta(days=7), flexible=True)
    window = (TODAY + timedelta(days=1), TODAY + timedelta(days=2))
    strict = score_candidate(plan, _profile(), _query(window_start=window[0], window_end=window[1]))
    assert strict.dates == SCORE_DATE_STRICT

    near_miss_start = plan.end_date + timedelta(days=FLEXIBLE_DATE_GRACE_DAYS - 1)
    flexible = score_candidate(plan, _profile(), _query(window_start=near_miss_start))
    assert flexible.dates == SCORE_DATE_FLEXIBLE

    no_window = score_candidate(plan, _profile(), _query())
    assert no_window.dates == 0


def test_shared_preferences_score_and_cap() -> None:
    profile = _profile(
        interests={"hiking", "beaches", "food", "photography", "museums"},
        styles={"solo", "backpacker", "adventure"},
        languages={"english", "hindi"},
    )
    query = _query(
        my_interests=frozenset({"hiking", "beaches", "food", "photography", "museums"}),
        my_styles=frozenset({"solo", "backpacker", "adventure"}),
        my_languages=frozenset({"hindi", "spanish"}),
    )
    breakdown = score_candidate(_plan(), profile, query)
    assert breakdown.interests == min(5 * SCORE_PER_SHARED_INTEREST, SCORE_INTEREST_CAP)
    assert breakdown.travel_style == min(3 * SCORE_PER_SHARED_STYLE, SCORE_STYLE_CAP)
    assert breakdown.language == SCORE_SHARED_LANGUAGE


def test_no_shared_preferences_score_zero() -> None:
    breakdown = score_candidate(
        _plan(), _profile(interests={"diving"}), _query(my_interests=frozenset({"hiking"}))
    )
    assert breakdown.interests == 0
    assert breakdown.travel_style == 0
    assert breakdown.language == 0


def test_total_is_capped_at_max() -> None:
    profile = _profile(
        interests={"hiking", "beaches", "food", "photography"},
        styles={"solo", "adventure"},
        languages={"english"},
    )
    query = _query(
        destination_normalized="goa",
        window_start=TODAY,
        window_end=TODAY + timedelta(days=3),
        my_interests=frozenset({"hiking", "beaches", "food", "photography"}),
        my_styles=frozenset({"solo", "adventure"}),
        my_languages=frozenset({"english"}),
    )
    breakdown = score_candidate(_plan(dest="goa"), profile, query)
    raw = (
        SCORE_DESTINATION_EXACT
        + SCORE_DATE_STRICT
        + SCORE_INTEREST_CAP
        + SCORE_STYLE_CAP
        + SCORE_SHARED_LANGUAGE
    )
    # The documented weights sum to exactly SCORE_MAX, so a perfect match
    # saturates the scale; the min() guard in ScoreBreakdown.total keeps
    # any future weight change from pushing the score past 100.
    assert raw == SCORE_MAX
    assert breakdown.total == SCORE_MAX


def test_scoring_is_deterministic() -> None:
    plan, profile, query = (
        _plan(dest="goa"),
        _profile(interests={"hiking"}),
        _query(destination_normalized="goa", my_interests=frozenset({"hiking"})),
    )
    assert score_candidate(plan, profile, query) == score_candidate(plan, profile, query)
