"""Social surface (Phase 6b placeholder route).

Plain language: travel-buddy discovery, messaging, and events do not
exist yet - they are Phase 7+ work. This phase still needs a REAL
endpoint that the identity-verification gate protects, otherwise
"unverified users are denied social access" could only be tested
theoretically. So Phase 6 ships exactly one route:

    GET /social/discovery   (requires verification while the policy says so)

It returns an empty `profiles` list with an honest message - no invented
users, no fabricated matches. Phase 7 replaces this with the actual
discovery implementation, keeping the same gate.

The gate itself lives in `app/api/v1/deps.py` (`require_verified_user`);
nothing in this file re-implements authorization.
"""

from fastapi import APIRouter

from app.api.v1.deps import SocialUser
from app.api.v1.schemas.social import DiscoveryResponse

router = APIRouter(prefix="/social", tags=["social"])

# Honest placeholder message - never claim features that do not exist.
_DISCOVERY_MESSAGE = (
    "Travel-buddy discovery is not implemented yet (planned for Phase 7+). "
    "This endpoint exists in Phase 6 only to enforce the identity-"
    "verification gate; you have passed it, but there is nothing to "
    "discover here yet."
)


@router.get(
    "/discovery",
    response_model=DiscoveryResponse,
    summary="Discovery (gated placeholder)",
)
def get_discovery(current_user: SocialUser) -> DiscoveryResponse:
    """Gate check + placeholder payload.

    `current_user` is the require_verified_user dependency: without a
    token -> 401; with an unverified/pending/rejected account while the
    policy requires verification -> 403; otherwise the route runs and
    returns an empty list (nothing is implemented yet).
    """
    return DiscoveryResponse(profiles=[], message=_DISCOVERY_MESSAGE)
