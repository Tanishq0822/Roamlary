"""Service layer for travel-buddy discovery (Phase 7).

Plain language: this module turns "find me compatible travel companions"
into ONE database query plus a small, deterministic ranking step. It sits
between the HTTP endpoints (which only parse/validate/serialize) and the
pure rules in `app/core/matching.py` (which know nothing about SQL).

The split exists so the matching RULES are unit-testable without a
database and the QUERY is written once and reused by both discovery
endpoints (`/travel-buddies/discover` and the Phase 6 route
`/social/discovery`, which the UI already calls).

QUERY DISCIPLINE (required by the phase brief): every mandatory
eligibility/privacy condition - active status, discoverable visibility,
non-expired dates, discoverable profile, verification policy, exclusion
of self and of people the searcher already has an accepted request with
- runs INSIDE the SQL statement against indexed columns. The database
never hands the application "all users"; only the pre-filtered
destination cohort (typically a few rows) is ranked and paginated in
Python. One extra query fetches existing request states for the page.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.core.matching import (
    FLEXIBLE_DATE_GRACE_DAYS,
    PlanFacts,
    ProfileFacts,
    QueryFacts,
    ScoreBreakdown,
    normalize_place,
    plan_matches_window,
    score_candidate,
)
from app.models.enums import (
    BuddyRequestStatus,
    PlanVisibility,
    TravelPlanStatus,
    VerificationStatus,
)
from app.models.travel_partner_request import TravelPartnerRequest
from app.models.travel_plan import TravelPlan
from app.models.travel_profile import TravelProfile
from app.models.user import User

# Hard ceiling on rows pulled from the database for one request. The
# SQL is already filtered to one destination/date cohort over indexed
# columns; this bound is a second belt against unbounded memory use and
# is part of the documented behaviour (report.md).
MAX_CANDIDATE_ROWS = 500


def today_utc() -> date:
    """Server's notion of 'today' for expiry checks (UTC, not local)."""
    return datetime.now(UTC).date()


@dataclass(frozen=True)
class DiscoveryFilters:
    """Validized filter inputs for one discovery request.

    All strings arrive already length-bounded and normalized by the
    endpoint; `None` means "not filtered".
    """

    destination: str | None = None
    region: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    interests: tuple[str, ...] = ()
    travel_style: str | None = None
    language: str | None = None
    min_score: int = 0


@dataclass
class Candidate:
    """One discovery result row: public profile + best plan + score."""

    user_id: UUID
    display_name: str
    bio: str | None
    home_region: str | None
    languages: list[str] | None
    travel_styles: list[str] | None
    interests: list[str] | None
    group_size_pref: int | None
    plan_id: UUID
    plan_destination: str
    plan_region: str | None
    plan_start: date
    plan_end: date
    plan_flexible: bool
    breakdown: ScoreBreakdown
    existing_request: str = "none"  # none | pending_sent | pending_received | accepted
    # Internal ranking keys (not serialized).
    _plan_start_key: date = field(default_factory=date.min, repr=False)

    @property
    def score(self) -> int:
        return self.breakdown.total


def _eligible_plan_conditions(today: date):
    """Mandatory plan/profile eligibility predicates (shared by queries)."""
    return (
        TravelPlan.status == TravelPlanStatus.ACTIVE,
        TravelPlan.visibility == PlanVisibility.DISCOVERABLE,
        TravelPlan.end_date >= today,
        TravelProfile.discoverable.is_(True),
    )


def _verification_condition(requires_verification: bool):
    """Candidate-side verification filter (policy applied live)."""
    if requires_verification:
        return User.verification_status == VerificationStatus.VERIFIED
    return None


def _existing_partner_ids(db: Session, searcher_id: UUID) -> set[UUID]:
    """User IDs the searcher already has an ACCEPTED request with (either direction)."""
    rows = db.execute(
        select(TravelPartnerRequest.requester_id, TravelPartnerRequest.recipient_id).where(
            TravelPartnerRequest.status == BuddyRequestStatus.ACCEPTED,
            or_(
                TravelPartnerRequest.requester_id == searcher_id,
                TravelPartnerRequest.recipient_id == searcher_id,
            ),
        )
    ).all()
    partners: set[UUID] = set()
    for requester_id, recipient_id in rows:
        partners.add(recipient_id if requester_id == searcher_id else requester_id)
    return partners


def _request_states(db: Session, searcher_id: UUID, candidate_ids: list[UUID]) -> dict[UUID, str]:
    """Map candidate user_id -> pending/accepted request state vs searcher.

    One query for the whole page (no N+1). 'accepted' should not normally
    appear because accepted partners are excluded from the SQL query, but
    it is reported defensively if data changes mid-request.
    """
    if not candidate_ids:
        return {}
    rows = db.execute(
        select(TravelPartnerRequest).where(
            or_(
                and_(
                    TravelPartnerRequest.requester_id == searcher_id,
                    TravelPartnerRequest.recipient_id.in_(candidate_ids),
                ),
                and_(
                    TravelPartnerRequest.recipient_id == searcher_id,
                    TravelPartnerRequest.requester_id.in_(candidate_ids),
                ),
            )
        )
    ).scalars()
    states: dict[UUID, str] = {}
    for req in rows:
        other_id = req.recipient_id if req.requester_id == searcher_id else req.requester_id
        if req.status == BuddyRequestStatus.ACCEPTED:
            states[other_id] = "accepted"
        elif req.status == BuddyRequestStatus.PENDING:
            sent = req.requester_id == searcher_id
            states.setdefault(other_id, "pending_sent" if sent else "pending_received")
    return states


def discover(
    db: Session,
    *,
    searcher: User,
    searcher_profile: TravelProfile | None,
    filters: DiscoveryFilters,
    requires_verification: bool,
    offset: int,
    limit: int,
) -> tuple[int, list[Candidate]]:
    """Ranked, deduplicated, paginated discovery for one searcher.

    Steps:
    1. SQL: eligible plans joined with their discoverable profiles and
       eligible accounts, excluding self, accepted partners, and
       applying destination/region/date filters on indexed columns.
       Rows are capped at a hard ceiling (MAX_CANDIDATE_ROWS) so a
       pathological filter cannot stream an unbounded set into memory.
    2. Python: score each row with the pure rules, deduplicate users
       (keep their single best-scoring plan; ties -> earliest start),
       drop rows failing secondary filters or min_score.
    3. Deterministic sort: score DESC, then earliest plan start, then
       user_id string - stable across pages.
    4. Paginate with the validated offset/limit and annotate each row
       with the searcher's existing request state.

    Returns (total_distinct_candidates, page_rows). `total` counts
    AFTER dedupe and secondary filters, so clients can page honestly.
    """
    today = today_utc()
    dest_norm = normalize_place(filters.destination) if filters.destination else None
    region_norm = normalize_place(filters.region) if filters.region else None

    conds = list(_eligible_plan_conditions(today))
    ver = _verification_condition(requires_verification)
    if ver is not None:
        conds.append(ver)
    conds.append(TravelPlan.user_id != searcher.id)

    if dest_norm is not None:
        conds.append(TravelPlan.destination_normalized == dest_norm)
    if region_norm is not None:
        conds.append(TravelPlan.region_normalized == region_norm)
    if filters.start_date is not None:
        # Window pre-filter is WIDENED by the flexible grace on both
        # sides so flexible plans are not lost before scoring; the
        # Python step then classifies strict vs flexible vs no-overlap
        # (and drops the last kind). This SQL window is a documented
        # superset of the final date rule.
        conds.append(
            TravelPlan.end_date >= filters.start_date - timedelta(days=FLEXIBLE_DATE_GRACE_DAYS)
        )
    if filters.end_date is not None:
        conds.append(
            TravelPlan.start_date <= filters.end_date + timedelta(days=FLEXIBLE_DATE_GRACE_DAYS)
        )

    partners = _existing_partner_ids(db, searcher.id)
    if partners:
        conds.append(TravelPlan.user_id.not_in(partners))

    stmt = (
        select(TravelPlan, TravelProfile, User)
        .join(TravelProfile, TravelProfile.user_id == TravelPlan.user_id)
        .join(User, User.id == TravelPlan.user_id)
        .where(*conds)
        .order_by(TravelPlan.start_date.asc(), TravelPlan.id.asc())
        .limit(MAX_CANDIDATE_ROWS)
    )
    rows = db.execute(stmt).all()

    my_interests = _norm_set(searcher_profile.interests if searcher_profile else None)
    my_styles = _norm_set(searcher_profile.travel_styles if searcher_profile else None)
    my_languages = _norm_set(searcher_profile.languages if searcher_profile else None)
    filter_interests = _norm_set(list(filters.interests) if filters.interests else None)

    query_facts = QueryFacts(
        destination_normalized=dest_norm,
        region_normalized=region_norm,
        window_start=filters.start_date,
        window_end=filters.end_date,
        filter_interests=filter_interests,
        filter_style=filters.travel_style,
        filter_language=filters.language,
        my_interests=my_interests,
        my_styles=my_styles,
        my_languages=my_languages,
    )

    best: dict[UUID, Candidate] = {}
    for plan, profile, user in rows:
        cand_interests = _norm_set(profile.interests)
        cand_styles = _norm_set(profile.travel_styles)
        cand_languages = _norm_set(profile.languages)

        # Secondary filters narrow the cohort (documented: applied after
        # the SQL-pre-filtered destination set, never over all users).
        if filter_interests and not (filter_interests & cand_interests):
            continue
        if filters.travel_style and filters.travel_style not in cand_styles:
            continue
        if filters.language and filters.language not in cand_languages:
            continue

        # The SQL window is widened by the flexible grace, so a genuine
        # no-overlap row can reach here; drop it now. A plan with no
        # overlap (strictly or via its own flexibility) never matches a
        # date-filtered search.
        if (filters.start_date is not None or filters.end_date is not None) and (
            plan_matches_window(
                plan.start_date,
                plan.end_date,
                filters.start_date,
                filters.end_date,
                plan.flexible_dates,
            )
            is None
        ):
            continue

        breakdown = score_candidate(
            PlanFacts(
                destination_normalized=plan.destination_normalized,
                region_normalized=plan.region_normalized,
                start_date=plan.start_date,
                end_date=plan.end_date,
                flexible=plan.flexible_dates,
            ),
            ProfileFacts(
                interests=cand_interests, travel_styles=cand_styles, languages=cand_languages
            ),
            query_facts,
        )
        if breakdown.total < filters.min_score:
            continue

        candidate = Candidate(
            user_id=user.id,
            display_name=profile.travel_nickname or user.display_name,
            bio=profile.bio,
            home_region=profile.home_region,
            languages=profile.languages,
            travel_styles=profile.travel_styles,
            interests=profile.interests,
            group_size_pref=profile.group_size_pref,
            plan_id=plan.id,
            plan_destination=plan.destination,
            plan_region=plan.region,
            plan_start=plan.start_date,
            plan_end=plan.end_date,
            plan_flexible=plan.flexible_dates,
            breakdown=breakdown,
            _plan_start_key=plan.start_date,
        )

        # One row per user: keep the best-scoring plan; ties break to
        # the earliest start, then lowest plan id (fully deterministic).
        existing = best.get(user.id)
        if existing is None or (candidate.score, -candidate._plan_start_key.toordinal()) > (
            existing.score,
            -existing._plan_start_key.toordinal(),
        ):
            best[user.id] = candidate

    ranked = sorted(
        best.values(),
        key=lambda c: (-c.score, c._plan_start_key.toordinal(), str(c.user_id)),
    )

    total = len(ranked)
    page = ranked[offset : offset + limit]
    states = _request_states(db, searcher.id, [c.user_id for c in page])
    for cand in page:
        cand.existing_request = states.get(cand.user_id, "none")
    return total, page


def _norm_set(values: list[str] | None) -> frozenset[str]:
    """Normalized frozenset from a stored JSON list (schema-validated)."""
    if not values:
        return frozenset()
    return frozenset(normalize_place(v).replace(" ", "_") for v in values)


def public_profile_for(
    db: Session,
    *,
    searcher: User,
    target_id: UUID,
    requires_verification: bool,
) -> Candidate | None:
    """Limited public travel profile for ONE eligible user, or None.

    Returns None (-> identical privacy-preserving 404) when the target
    does not exist, has no profile, is not discoverable, is ineligible
    under the verification policy, has no eligible plan, or is the
    searcher themselves. The caller must not distinguish these cases in
    the response.
    """
    today = today_utc()
    conds = list(_eligible_plan_conditions(today)) + [User.id == target_id]
    ver = _verification_condition(requires_verification)
    if ver is not None:
        conds.append(ver)

    stmt = (
        select(TravelPlan, TravelProfile, User)
        .join(TravelProfile, TravelProfile.user_id == TravelPlan.user_id)
        .join(User, User.id == TravelPlan.user_id)
        .where(*conds)
        .order_by(TravelPlan.start_date.asc(), TravelPlan.id.asc())
        .limit(1)
    )
    row = db.execute(stmt).one_or_none()
    if row is None:
        return None
    plan, profile, user = row
    return Candidate(
        user_id=user.id,
        display_name=profile.travel_nickname or user.display_name,
        bio=profile.bio,
        home_region=profile.home_region,
        languages=profile.languages,
        travel_styles=profile.travel_styles,
        interests=profile.interests,
        group_size_pref=profile.group_size_pref,
        plan_id=plan.id,
        plan_destination=plan.destination,
        plan_region=plan.region,
        plan_start=plan.start_date,
        plan_end=plan.end_date,
        plan_flexible=plan.flexible_dates,
        breakdown=ScoreBreakdown(),
        _plan_start_key=plan.start_date,
    )


def broad_feed(
    db: Session,
    *,
    searcher: User,
    searcher_profile: TravelProfile | None,
    requires_verification: bool,
    limit: int,
) -> list[Candidate]:
    """Unfiltered eligible cohort for the Phase 6 `/social/discovery` route.

    No destination or date filter is applied (that route predates the
    filterable endpoint and the UI calls it bare). Ranking therefore
    uses only preference signals; ordering stays deterministic. Same
    mandatory eligibility/privacy SQL as `discover`.
    """
    _, page = discover(
        db,
        searcher=searcher,
        searcher_profile=searcher_profile,
        filters=DiscoveryFilters(),
        requires_verification=requires_verification,
        offset=0,
        limit=limit,
    )
    return page
