"""Travel-buddy discovery and travel-partner requests (Phase 7).

Plain language: this module is the social heart of Phase 7 - "find
people travelling where and when I am" and "ask them to travel
together". It exposes three groups of routes:

1. DISCOVERY:  GET /travel-buddies/discover (filtered, paginated) and
   GET /travel-buddies/{user_id} (one limited public profile). Both
   reuse the Phase 6 identity-verification gate UNCHANGED
   (`require_verified_user`) and additionally filter candidate ACCOUNTS
   by verification status while the policy is on - the dependency rule
   from the phase brief, satisfied by reuse, not reinvention.
2. REQUESTS: send, list incoming/outgoing, fetch one, accept, reject,
   cancel - a strict `pending -> accepted | rejected | cancelled`
   state machine.
3. Nothing else: no chat, no messaging, no blocking, no groups - those
   belong to later phases and are deliberately absent here.

HONEST SCORING: `compatibility_score` is deterministic arithmetic over
destination, dates, and declared preferences (see app/core/matching.py).
It is NOT a safety or personality guarantee, and API responses say so.

READING vs ACTING (the gate is applied asymmetrically on purpose):
- Acting socially (sending a request, accepting, rejecting, discovering
  other people) requires passing the verification gate - SocialUser.
- Reading or WITHDRAWING your own data (listing your requests, fetching
  one you belong to, cancelling your own pending request) uses plain
  authentication - an account whose verification lapsed must still be
  able to see and retract what it sent. This mirrors the Phase 6b rule
  that verification gates social ACCESS, never the ability to manage
  your own records.

ELIGIBILITY RECHECKS (brief section 8.9):
- At SEND: the recipient must exist, be discoverable, and satisfy the
  live verification policy - otherwise a privacy-preserving 404 (the
  same response as a nonexistent user, so eligibility cannot be probed).
- At ACCEPT: the requester's verification eligibility is rechecked; if
  it lapsed while the policy requires it, the accept fails with 409 and
  the request stays pending for the recipient to reject instead.
"""

from datetime import UTC
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

from app.api.v1.deps import CurrentUser, DbSession, SocialUser
from app.api.v1.schemas.travel import (
    BuddyRequestCreate,
    BuddyRequestList,
    BuddyRequestRead,
    DiscoveryCandidateRead,
    DiscoveryPage,
    PublicTravelProfileRead,
    TravelPlanRead,
)
from app.core.blocks import blocked_user_ids
from app.core.pairing import canonical_pair
from app.core.policy import get_policy
from app.core.rate_limit import check_rate_limit
from app.db.base_class import utc_now
from app.models.enums import BuddyRequestStatus
from app.models.travel_partner_request import TravelPartnerRequest
from app.models.travel_plan import TravelPlan
from app.models.travel_profile import TravelProfile
from app.models.user import User
from app.services.discovery import (
    Candidate,
    DiscoveryFilters,
    discover,
    public_profile_for,
    today_utc,
)

router = APIRouter(prefix="/travel-buddies", tags=["travel-buddies"])

# Abuse control for request SENDING, reusing the Phase 6b in-process
# limiter (same documented single-process limitation). Reads and state
# transitions are not limited: they are bounded by the request rows the
# user already owns.
_SEND_LIMIT_PER_HOUR = 30

_DISCOVERY_NOTE = (
    "Compatibility scores are a deterministic ranking of travel logistics "
    "and stated preferences - not a guarantee that anyone is safe or that "
    "two people will get along. Always meet in public and tell a trusted "
    "contact your plans."
)


def _iso(value) -> str | None:
    """Timestamp to UTC ISO-8601 (same normalization as other endpoints)."""
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()


def _candidate_read(candidate: Candidate) -> DiscoveryCandidateRead:
    return DiscoveryCandidateRead(
        user_id=candidate.user_id,
        display_name=candidate.display_name,
        bio=candidate.bio,
        home_region=candidate.home_region,
        languages=candidate.languages,
        travel_styles=candidate.travel_styles,
        interests=candidate.interests,
        group_size_pref=candidate.group_size_pref,
        plan=TravelPlanRead(
            id=candidate.plan_id,
            destination=candidate.plan_destination,
            region=candidate.plan_region,
            start_date=candidate.plan_start,
            end_date=candidate.plan_end,
            flexible_dates=candidate.plan_flexible,
            status="active",
            visibility="discoverable",
        ),
        compatibility_score=candidate.score,
        match_breakdown={
            "destination": candidate.breakdown.destination,
            "dates": candidate.breakdown.dates,
            "interests": candidate.breakdown.interests,
            "travel_style": candidate.breakdown.travel_style,
            "language": candidate.breakdown.language,
        },
        existing_request=candidate.existing_request,
    )


# --- Discovery ------------------------------------------------------------


@router.get(
    "/discover",
    response_model=DiscoveryPage,
    summary="Discover compatible travel companions (verified users only)",
)
def discover_buddies(
    current_user: SocialUser,
    db: DbSession,
    destination: Annotated[
        str | None,
        Query(max_length=80, description="Destination name to match (normalized text)."),
    ] = None,
    region: Annotated[
        str | None,
        Query(max_length=80, description="Broad region/country match when no destination given."),
    ] = None,
    start_date: Annotated[
        str | None, Query(description="ISO date; plans must overlap on/after this day.")
    ] = None,
    end_date: Annotated[
        str | None, Query(description="ISO date; plans must overlap on/before this day.")
    ] = None,
    interests: Annotated[
        list[str] | None,
        Query(description="Repeatable; candidates must list at least one of these."),
    ] = None,
    travel_style: Annotated[
        str | None, Query(max_length=24, description="Exact travel-style membership filter.")
    ] = None,
    language: Annotated[
        str | None, Query(max_length=24, description="Candidates must list this language.")
    ] = None,
    min_score: Annotated[
        int, Query(ge=0, le=100, description="Drop candidates scoring below this (0-100).")
    ] = 0,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> DiscoveryPage:
    """Ranked, deduplicated discovery over eligible accounts.

    Mandatory eligibility/privacy filters (active + discoverable +
    non-expired plans, discoverable profiles, verification policy,
    excluding self and accepted partners) run in SQL. Secondary
    preference filters, scoring, dedupe, and pagination run over that
    pre-filtered destination cohort - never over all users.

    `start_date`/`end_date` are ISO dates (YYYY-MM-DD); an inverted
    range is 422. A plan marked flexible may overlap the window by up to
    7 grace days and scores lower than a strict overlap.
    """
    from datetime import date as _date

    try:
        win_start = _date.fromisoformat(start_date) if start_date else None
        win_end = _date.fromisoformat(end_date) if end_date else None
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="start_date and end_date must be ISO dates (YYYY-MM-DD).",
        ) from exc
    if win_start is not None and win_end is not None and win_end < win_start:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="end_date must not precede start_date.",
        )

    profile = db.scalar(select(TravelProfile).where(TravelProfile.user_id == current_user.id))
    filters = DiscoveryFilters(
        destination=destination,
        region=region,
        start_date=win_start,
        end_date=win_end,
        interests=tuple(interests) if interests else (),
        travel_style=travel_style,
        language=language,
        min_score=min_score,
    )
    total, rows = discover(
        db,
        searcher=current_user,
        searcher_profile=profile,
        filters=filters,
        requires_verification=get_policy(db),
        offset=offset,
        limit=limit,
    )
    return DiscoveryPage(
        total=total,
        offset=offset,
        limit=limit,
        results=[_candidate_read(c) for c in rows],
        note=_DISCOVERY_NOTE,
    )


# NOTE: /requests routes are declared BEFORE /{user_id} on purpose -
# FastAPI matches paths in declaration order, and "requests" would
# otherwise be captured by the {user_id} path parameter.


@router.get(
    "/requests",
    response_model=BuddyRequestList,
    summary="List my incoming or outgoing travel-partner requests",
)
def list_my_requests(
    current_user: CurrentUser,
    db: DbSession,
    direction: Annotated[
        str,
        Query(
            pattern="^(incoming|outgoing)$", description="incoming (to me) or outgoing (from me)."
        ),
    ] = "incoming",
    request_status: Annotated[
        BuddyRequestStatus | None,
        Query(description="Optional status filter (default: all statuses)."),
    ] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> BuddyRequestList:
    """Requests where the caller is the recipient (incoming) or requester (outgoing).

    Plain authentication (not the social gate): seeing and managing your
    own request history is always allowed, even if verification lapsed.
    """
    column = (
        TravelPartnerRequest.recipient_id
        if direction == "incoming"
        else TravelPartnerRequest.requester_id
    )
    conds = [column == current_user.id]
    if request_status is not None:
        conds.append(TravelPartnerRequest.status == request_status)

    total = db.scalar(select(func.count()).select_from(TravelPartnerRequest).where(*conds)) or 0
    stmt = (
        select(TravelPartnerRequest)
        .options(
            joinedload(TravelPartnerRequest.requester).joinedload(User.travel_profile),
            joinedload(TravelPartnerRequest.recipient).joinedload(User.travel_profile),
            joinedload(TravelPartnerRequest.plan),
        )
        .where(*conds)
        .order_by(TravelPartnerRequest.created_at.desc(), TravelPartnerRequest.id.desc())
        .offset(offset)
        .limit(limit)
    )
    rows = db.scalars(stmt).unique().all()
    return BuddyRequestList(
        total=total,
        offset=offset,
        limit=limit,
        results=[_request_read(r) for r in rows],
    )


@router.post(
    "/requests",
    response_model=BuddyRequestRead,
    status_code=status.HTTP_201_CREATED,
    summary="Send a travel-partner request (verified users only)",
)
def send_request(
    body: BuddyRequestCreate,
    current_user: SocialUser,
    db: DbSession,
) -> BuddyRequestRead:
    """Send a pending travel-partner request to another traveller.

    Rejected with:
    - 422 when targeting yourself;
    - 404 (privacy-preserving, identical to "unknown user") when the
      recipient does not exist, has no discoverable profile, fails
      the live verification policy, or is blocked in either direction;
      likewise when a supplied plan_id is not the recipient's eligible
      (discoverable/active/unexpired) plan;
    - 409 when a pending request already exists in EITHER direction, or
      the pair already has an accepted relationship;
    - 429 when the per-user hourly send limit is exceeded.

    The duplicate guard is enforced twice: a pre-check for a friendly
    message and UNIQUE indexes as the race-proof source of truth
    (concurrent duplicate submissions lose at the database - including
    simultaneous opposite-direction sends, via the canonical-pair
    pending index from Phase 8).
    """
    if body.recipient_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="You cannot send a travel-partner request to yourself.",
        )

    check_rate_limit(
        f"buddy-request:{current_user.id}",
        limit=_SEND_LIMIT_PER_HOUR,
        window_seconds=3600,
    )

    requires_verification = get_policy(db)

    # Recipient must exist, be discoverable, pass the live policy, and
    # be unblocked in either direction - all collapses to one generic
    # 404 so eligibility cannot be probed (Phase 8: blocks join the
    # same collapse; the blocker's list must never leak via an error).
    recipient = db.scalar(
        select(User)
        .join(TravelProfile, TravelProfile.user_id == User.id)
        .where(
            User.id == body.recipient_id,
            TravelProfile.discoverable.is_(True),
        )
    )
    if recipient is None or (requires_verification and recipient.verification_status != "verified"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recipient not found.",
        )
    if body.recipient_id in blocked_user_ids(db, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recipient not found.",
        )

    if body.plan_id is not None:
        plan = db.scalar(
            select(TravelPlan).where(
                TravelPlan.id == body.plan_id,
                TravelPlan.user_id == body.recipient_id,
                TravelPlan.visibility == "discoverable",
                TravelPlan.status == "active",
                TravelPlan.end_date >= today_utc(),
            )
        )
        if plan is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Recipient not found.",
            )

    # Either-direction duplicates (pending or accepted) are conflicts.
    existing = db.scalar(
        select(TravelPartnerRequest).where(
            TravelPartnerRequest.status.in_(
                [BuddyRequestStatus.PENDING, BuddyRequestStatus.ACCEPTED]
            ),
            or_(
                (
                    (TravelPartnerRequest.requester_id == current_user.id)
                    & (TravelPartnerRequest.recipient_id == body.recipient_id)
                ),
                (
                    (TravelPartnerRequest.requester_id == body.recipient_id)
                    & (TravelPartnerRequest.recipient_id == current_user.id)
                ),
            ),
        )
    )
    if existing is not None:
        if existing.status == BuddyRequestStatus.ACCEPTED:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="You are already travel partners with this user.",
            )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A pending travel-partner request already exists between you two.",
        )

    # Canonical pair for the Phase 8 cross-direction race fix: two
    # simultaneous opposite-direction sends cannot both land (the
    # pending-only UNIQUE index on the pair rejects the loser).
    pair_low_id, pair_high_id = canonical_pair(current_user.id, body.recipient_id)
    request_row = TravelPartnerRequest(
        requester_id=current_user.id,
        recipient_id=body.recipient_id,
        plan_id=body.plan_id,
        status=BuddyRequestStatus.PENDING,
        pair_low_id=pair_low_id,
        pair_high_id=pair_high_id,
    )
    db.add(request_row)
    try:
        db.commit()
    except IntegrityError as exc:
        # Race-proof path: the partial UNIQUE index rejected a duplicate
        # that appeared between our pre-check and this insert.
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A pending travel-partner request already exists between you two.",
        ) from exc
    db.refresh(request_row)
    return _request_read(_load_request(db, request_row.id))


def _load_request(db, request_id: UUID) -> TravelPartnerRequest:
    row = db.scalar(
        select(TravelPartnerRequest)
        .options(
            joinedload(TravelPartnerRequest.requester).joinedload(User.travel_profile),
            joinedload(TravelPartnerRequest.recipient).joinedload(User.travel_profile),
            joinedload(TravelPartnerRequest.plan),
        )
        .where(TravelPartnerRequest.id == request_id)
    )
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Travel-partner request not found.",
        )
    return row


def _request_read(row: TravelPartnerRequest) -> BuddyRequestRead:
    requester_name = (
        row.requester.travel_profile.travel_nickname
        if row.requester.travel_profile is not None
        else None
    ) or row.requester.display_name
    recipient_name = (
        row.recipient.travel_profile.travel_nickname
        if row.recipient.travel_profile is not None
        else None
    ) or row.recipient.display_name
    plan = row.plan
    return BuddyRequestRead(
        id=row.id,
        requester_id=row.requester_id,
        requester_display_name=requester_name,
        recipient_id=row.recipient_id,
        recipient_display_name=recipient_name,
        plan_id=row.plan_id,
        plan_destination=plan.destination if plan is not None else None,
        plan_start_date=plan.start_date if plan is not None else None,
        plan_end_date=plan.end_date if plan is not None else None,
        status=row.status,
        created_at=_iso(row.created_at),
        updated_at=_iso(row.updated_at),
        responded_at=_iso(row.responded_at),
    )


def _authorize_party(row: TravelPartnerRequest, user) -> None:
    """Only the two parties may read a request; everyone else gets 404.

    404 (not 403) so the existence of a request ID cannot be probed.
    """
    if user.id not in (row.requester_id, row.recipient_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Travel-partner request not found.",
        )


@router.get(
    "/requests/{request_id}",
    response_model=BuddyRequestRead,
    summary="Inspect one travel-partner request (parties only)",
)
def get_request(
    request_id: UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> BuddyRequestRead:
    """Fetch one request; 404 for non-parties and unknown IDs alike."""
    row = _load_request(db, request_id)
    _authorize_party(row, current_user)
    return _request_read(row)


def _transition(
    db,
    request_id: UUID,
    user,
    *,
    expected_party: str,
    expected_status: BuddyRequestStatus,
    new_status: BuddyRequestStatus,
) -> TravelPartnerRequest:
    """Shared pending-only state machine for accept/reject/cancel.

    `expected_party` is 'recipient' (accept/reject) or 'requester'
    (cancel). A wrong party gets 404 (existence privacy), a non-pending
    row gets 409 with its current status named.
    """
    row = _load_request(db, request_id)
    party_id = row.recipient_id if expected_party == "recipient" else row.requester_id
    if user.id != party_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Travel-partner request not found.",
        )
    if row.status != expected_status:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Only pending requests can be moved to '{new_status}' (current: '{row.status}')."
            ),
        )
    row.status = new_status
    row.responded_at = utc_now()
    row.updated_at = utc_now()
    db.add(row)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The request changed concurrently; reload and retry.",
        ) from exc
    db.refresh(row)
    return row


@router.post(
    "/requests/{request_id}/accept",
    response_model=BuddyRequestRead,
    summary="Accept a pending incoming request (recipient only)",
)
def accept_request(
    request_id: UUID,
    current_user: SocialUser,
    db: DbSession,
) -> BuddyRequestRead:
    """Recipient accepts a pending request -> `accepted`.

    The requester's verification eligibility is RECHECKED here (brief
    8.9): if it lapsed while the policy requires verification, the
    accept fails 409 and the request stays pending (the recipient may
    still reject it). An accepted relationship never bypasses future
    blocking, restrictions, or privacy controls.
    """
    row = _load_request(db, request_id)
    if row.recipient_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Travel-partner request not found.",
        )
    if row.status != BuddyRequestStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Only pending requests can be accepted (current: '{row.status}').",
        )
    if get_policy(db):
        requester = db.get(User, row.requester_id)
        if requester is None or requester.verification_status != "verified":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "The requester is no longer eligible for social features; "
                    "this request cannot be accepted. You may reject it instead."
                ),
            )
    # Phase 8: accepting an older ask must never bypass a block that
    # landed afterwards (brief item 4.12) - 409, row stays pending.
    if row.requester_id in blocked_user_ids(db, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This request can no longer be accepted while the pair is "
                "blocked. You may reject it instead."
            ),
        )
    return _request_read(
        _transition(
            db,
            request_id,
            current_user,
            expected_party="recipient",
            expected_status=BuddyRequestStatus.PENDING,
            new_status=BuddyRequestStatus.ACCEPTED,
        )
    )


@router.post(
    "/requests/{request_id}/reject",
    response_model=BuddyRequestRead,
    summary="Reject a pending incoming request (recipient only)",
)
def reject_request(
    request_id: UUID,
    current_user: SocialUser,
    db: DbSession,
) -> BuddyRequestRead:
    """Recipient rejects a pending request -> `rejected` (terminal)."""
    return _request_read(
        _transition(
            db,
            request_id,
            current_user,
            expected_party="recipient",
            expected_status=BuddyRequestStatus.PENDING,
            new_status=BuddyRequestStatus.REJECTED,
        )
    )


@router.post(
    "/requests/{request_id}/cancel",
    response_model=BuddyRequestRead,
    summary="Cancel my own pending outgoing request (requester only)",
)
def cancel_request(
    request_id: UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> BuddyRequestRead:
    """Requester withdraws their own pending request -> `cancelled`.

    Plain authentication on purpose: retracting what you sent is
    managing your own record, never a social action against someone
    else.
    """
    return _request_read(
        _transition(
            db,
            request_id,
            current_user,
            expected_party="requester",
            expected_status=BuddyRequestStatus.PENDING,
            new_status=BuddyRequestStatus.CANCELLED,
        )
    )


@router.get(
    "/{user_id}",
    response_model=PublicTravelProfileRead,
    summary="Limited public travel profile of one eligible user",
)
def get_public_profile(
    user_id: UUID,
    current_user: SocialUser,
    db: DbSession,
) -> PublicTravelProfileRead:
    """One traveller's LIMITED public profile, if they are eligible.

    Returns the same privacy-preserving 404 for: unknown user, hidden or
    missing profile, verification-policy ineligibility, and users with
    no eligible (discoverable/active/unexpired) plan. Only that single
    best plan is summarized - never private plans, account data, or
    verification state.
    """
    candidate = public_profile_for(
        db,
        searcher=current_user,
        target_id=user_id,
        requires_verification=get_policy(db),
    )
    if candidate is None or candidate.user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Traveller not found.",
        )
    return PublicTravelProfileRead(
        user_id=candidate.user_id,
        display_name=candidate.display_name,
        bio=candidate.bio,
        home_region=candidate.home_region,
        languages=candidate.languages,
        travel_styles=candidate.travel_styles,
        interests=candidate.interests,
        group_size_pref=candidate.group_size_pref,
        plan=TravelPlanRead(
            id=candidate.plan_id,
            destination=candidate.plan_destination,
            region=candidate.plan_region,
            start_date=candidate.plan_start,
            end_date=candidate.plan_end,
            flexible_dates=candidate.plan_flexible,
            status="active",
            visibility="discoverable",
        ),
    )
