"""Deterministic travel-buddy matching logic (Phase 7).

Plain language: this module answers "how compatible is this traveller's
plan with what the searcher asked for?" using ONLY arithmetic over data
the project already stores - destination text, dates, and the two
travellers' declared preferences. No AI, no external API, no vector
database, no paid provider: the rules are small, explicit, and every
input and weight is documented below, so a score can be explained and
reproduced exactly.

HONESTY BOUNDARY (repeated in API docs and responses): the score is a
CONVENIENCE RANKING of travel logistics and stated preferences. It is
NOT, and must never be presented as, proof that two people are safe or
will get along. Identity verification (Phase 6b) confirms an account
passed a manual review - it does not make anyone safe either.

Everything here is pure: same inputs -> same outputs, no clock reads,
no database access. That makes the rules unit-testable without HTTP or
SQL, as the phase requires.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

# --- Scoring weights (documented; sum of maxima = 100) -------------------
# Primary conditions (what the searcher filtered on):
#   destination exact (normalized) match ......... 40
#   region match when no destination matched ..... 20
#   date overlap: strict ......................... 30
#   date overlap: only via flexible-date grace ... 15
# Secondary signals (shared declared preferences):
#   +5 per shared travel interest (cap 15) ....... 15
#   +5 per shared travel style (cap 10) .......... 10
#   shared language ..............................  5
# Total maximum: 40 + 30 + 15 + 10 + 5 = 100.
SCORE_DESTINATION_EXACT = 40
SCORE_REGION_MATCH = 20
SCORE_DATE_STRICT = 30
SCORE_DATE_FLEXIBLE = 15
SCORE_PER_SHARED_INTEREST = 5
SCORE_INTEREST_CAP = 15
SCORE_PER_SHARED_STYLE = 5
SCORE_STYLE_CAP = 10
SCORE_SHARED_LANGUAGE = 5
SCORE_MAX = 100

# A plan marked `flexible_dates` may overlap the searcher's window by up
# to this many days on each side and still count as a (weaker) match.
# The stored dates are never rewritten - the grace applies only while
# scoring an overlap.
FLEXIBLE_DATE_GRACE_DAYS = 7

# Closed sets for preference fields. Validation and scoring agree on
# these values; anything else is rejected at the schema layer. Languages
# are deliberately NOT a closed set (too many to enumerate) - they are
# validated by length instead.
ALLOWED_TRAVEL_STYLES: frozenset[str] = frozenset(
    {
        "solo",
        "backpacker",
        "luxury",
        "family",
        "group",
        "budget",
        "adventure",
        "cultural",
        "business",
        "road_trip",
        "nature",
        "slow_travel",
    }
)

ALLOWED_INTERESTS: frozenset[str] = frozenset(
    {
        "hiking",
        "beaches",
        "food",
        "history",
        "photography",
        "nightlife",
        "wildlife",
        "museums",
        "festivals",
        "shopping",
        "water_sports",
        "winter_sports",
        "camping",
        "yoga",
        "diving",
        "road_trips",
    }
)


def normalize_place(text: str) -> str:
    """Normalized matching key for a destination or region name.

    Lowercases, trims, and collapses internal whitespace so "  New
    YORK " and "new york" compare equal. This is TEXT NORMALIZATION, not
    verification: matching two plans that name the same place says
    nothing about whether that place is safe, and the API never claims a
    destination was checked against any external gazetteer.
    """
    return " ".join(text.split()).casefold()


def plan_matches_window(
    plan_start: date,
    plan_end: date,
    window_start: date | None,
    window_end: date | None,
    flexible: bool,
) -> str | None:
    """Classify a plan's date overlap with the searcher's window.

    Returns one of:
      "strict"   - real calendar overlap with the requested window
      "flexible" - no strict overlap, but the plan is marked flexible
                   and comes within FLEXIBLE_DATE_GRACE_DAYS of the
                   window on either side
      None       - no overlap at all (excluded from results)

    A None window bound means the searcher did not filter on that side
    (e.g. only "from March 1" was given), so only the provided bound is
    enforced. A plan is eligible through its END date inclusive.
    """
    strict = True
    if window_start is not None and plan_end < window_start:
        strict = False
    if window_end is not None and plan_start > window_end:
        strict = False
    if strict:
        return "strict"

    if not flexible:
        return None

    grace = timedelta(days=FLEXIBLE_DATE_GRACE_DAYS)
    loose_ok = True
    if window_start is not None and plan_end + grace < window_start:
        loose_ok = False
    if window_end is not None and plan_start - grace > window_end:
        loose_ok = False
    return "flexible" if loose_ok else None


@dataclass(frozen=True)
class ScoreBreakdown:
    """Per-candidate score parts. `total` is capped at SCORE_MAX."""

    destination: int = 0
    dates: int = 0
    interests: int = 0
    travel_style: int = 0
    language: int = 0

    @property
    def total(self) -> int:
        raw = self.destination + self.dates + self.interests + self.travel_style + self.language
        return min(raw, SCORE_MAX)


@dataclass(frozen=True)
class PlanFacts:
    """The candidate plan's facts relevant to scoring."""

    destination_normalized: str
    region_normalized: str | None
    start_date: date
    end_date: date
    flexible: bool


@dataclass(frozen=True)
class ProfileFacts:
    """The candidate's declared preferences (already validated upstream)."""

    interests: frozenset[str]
    travel_styles: frozenset[str]
    languages: frozenset[str]


@dataclass(frozen=True)
class QueryFacts:
    """The searcher's filters and their own declared preferences.

    Secondary signals score SHARED preferences (searcher profile
    INTERSECT candidate profile); filter fields narrow the candidate
    set and are only scored when they reflect a shared attribute.
    """

    destination_normalized: str | None = None
    region_normalized: str | None = None
    window_start: date | None = None
    window_end: date | None = None
    filter_interests: frozenset[str] = frozenset()
    filter_style: str | None = None
    filter_language: str | None = None
    my_interests: frozenset[str] = frozenset()
    my_styles: frozenset[str] = frozenset()
    my_languages: frozenset[str] = frozenset()


def score_candidate(plan: PlanFacts, profile: ProfileFacts, query: QueryFacts) -> ScoreBreakdown:
    """Compute the compatibility breakdown for one (plan, profile) pair.

    Rules, in full:
    1. Destination: exact normalized match with the queried destination
       -> 40. Otherwise, a region match (queried region, or the
       candidate's region equals the candidate of a destination-less
       region filter) -> 20. When the query carries no destination or
       region filter (broad feed), both are 0 - the score then ranks
       only preferences and dates.
    2. Dates: when the query defines a window, a strict calendar
       overlap -> 30; an overlap that only holds thanks to the plan's
       flexible-date grace -> 15. No window -> 0.
    3. Interests: +5 per interest shared between the searcher's and the
       candidate's profiles, capped at 15.
    4. Travel styles: +5 per shared style, capped at 10.
    5. Language: +5 if the two profiles share at least one language.

    Deterministic and total: the same inputs always produce the same
    breakdown. Components the query did not exercise contribute 0, so
    `min_score` should be interpreted relative to the filters used.
    """
    destination = 0
    region = 0
    if query.destination_normalized is not None:
        if plan.destination_normalized == query.destination_normalized:
            destination = SCORE_DESTINATION_EXACT
    elif query.region_normalized is not None:
        if plan.region_normalized is not None and plan.region_normalized == query.region_normalized:
            region = SCORE_REGION_MATCH
    # No place filter at all (broad feed): both are 0 - the score then
    # ranks only dates and preferences. Destination and region credit
    # never stack; the larger single signal is used.
    destination_or_region = destination if destination else region

    dates = 0
    if query.window_start is not None or query.window_end is not None:
        kind = plan_matches_window(
            plan.start_date, plan.end_date, query.window_start, query.window_end, plan.flexible
        )
        if kind == "strict":
            dates = SCORE_DATE_STRICT
        elif kind == "flexible":
            dates = SCORE_DATE_FLEXIBLE

    shared_interests = query.my_interests & profile.interests
    interests = min(len(shared_interests) * SCORE_PER_SHARED_INTEREST, SCORE_INTEREST_CAP)

    shared_styles = query.my_styles & profile.travel_styles
    travel_style = min(len(shared_styles) * SCORE_PER_SHARED_STYLE, SCORE_STYLE_CAP)

    language = SCORE_SHARED_LANGUAGE if (query.my_languages & profile.languages) else 0

    return ScoreBreakdown(
        destination=destination_or_region,
        dates=dates,
        interests=interests,
        travel_style=travel_style,
        language=language,
    )


def normalize_str_set(values: list[str] | None) -> frozenset[str]:
    """Normalized frozenset for preference lists (already schema-validated)."""
    if not values:
        return frozenset()
    return frozenset(normalize_place(v).replace(" ", "_") for v in values)
