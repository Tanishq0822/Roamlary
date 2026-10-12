"""Social surface (Phase 6b gate + Phase 7 real discovery).

Plain language: Phase 6 shipped ONE route here - GET /social/discovery -
as an honest empty placeholder, purely so the identity-verification
gate had a real endpoint to protect (and real API tests to prove
denial). Phase 7 keeps that route and its gate EXACTLY as before (same
path, same `require_verified_user` dependency, same `{profiles, message}`
JSON contract the existing UI already parses) but now fills `profiles`
with the real travel-buddy discovery results from Phase 7's matching
service.

The richer, filterable, paginated endpoint is
GET /api/v1/travel-buddies/discover; this route stays as a compatibility
"broad feed" (no filters, top results only) because it predates the
filterable one and the committed UI calls it bare. Nothing here
re-implements authorization - the gate lives in `app/api/v1/deps.py`.
"""

from fastapi import APIRouter
from sqlalchemy import select

from app.api.v1.deps import DbSession, SocialUser
from app.api.v1.endpoints.travel_buddies import _candidate_read
from app.api.v1.schemas.social import DiscoveryResponse
from app.core.policy import get_policy
from app.models.travel_profile import TravelProfile
from app.services.discovery import broad_feed

router = APIRouter(prefix="/social", tags=["social"])

# How many broad-feed results this compatibility route returns. The
# filterable endpoint accepts offset/limit up to 100; this one is a
# fixed-size "who's out there" peek.
_BROAD_FEED_LIMIT = 10

# Honest message - the UI displays it verbatim next to the count.
_DISCOVERY_MESSAGE = (
    "Showing travellers with active, discoverable plans. Compatibility "
    "scores are a deterministic ranking of travel logistics and stated "
    "preferences - not a guarantee that anyone is safe or compatible. "
    "Use GET /api/v1/travel-buddies/discover for filtered, paginated "
    "matching."
)


@router.get(
    "/discovery",
    response_model=DiscoveryResponse,
    summary="Broad discovery feed (gated by identity verification)",
)
def get_discovery(current_user: SocialUser, db: DbSession) -> DiscoveryResponse:
    """Gate check + real (unfiltered) discovery results.

    `current_user` is the `require_verified_user` dependency, unchanged
    from Phase 6b: while the policy requires verification, an
    unverified/pending/rejected account gets the same 403 as before; a
    verified account (or any account while the owner has turned the
    policy off) gets the top eligible candidates. The JSON shape is
    unchanged from Phase 6: `profiles` (now populated) plus an honest
    `message`.
    """
    profile = db.scalar(select(TravelProfile).where(TravelProfile.user_id == current_user.id))
    rows = broad_feed(
        db,
        searcher=current_user,
        searcher_profile=profile,
        requires_verification=get_policy(db),
        limit=_BROAD_FEED_LIMIT,
    )
    return DiscoveryResponse(
        profiles=[_candidate_read(c).model_dump(mode="json") for c in rows],
        message=_DISCOVERY_MESSAGE,
    )
