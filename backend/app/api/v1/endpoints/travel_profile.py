"""Travel-profile endpoints (Phase 7).

Plain language: a travel profile is the traveller-facing identity a user
CHOSES to publish for travel-buddy discovery - nickname, bio, broad
home region, languages, interests, styles, group-size preference, and a
discoverability switch. It is separate from the account (`/users/me`):
these routes can never read or write email, password, role, or
verification status, because those fields do not exist in this module's
schemas.

OWNERSHIP: there is exactly one profile per account (UNIQUE user_id in
the database). Every route here operates on the TOKEN's user only - the
API deliberately offers no way to fetch or edit another user's private
profile row; the limited PUBLIC view lives at GET /travel-buddies/{id}
and passes the same eligibility rules as discovery.

VISIBILITY: profiles are created hidden (`discoverable=false`). A
profile becomes eligible for discovery only when its owner flips the
switch AND the live verification policy is satisfied AND the account
has at least one eligible plan. Turning discoverable off hides the
profile immediately - the next query simply no longer matches.
"""

from datetime import UTC

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.v1.deps import CurrentUser, DbSession
from app.api.v1.schemas.travel import TravelProfileCreate, TravelProfilePatch, TravelProfileRead
from app.db.base_class import utc_now
from app.models.travel_profile import TravelProfile

router = APIRouter(prefix="/travel-profile", tags=["travel-profile"])

# Fields whose absence is reported in `completion`. Completion is
# guidance for the traveller, never an identity signal - a completed
# profile does NOT verify an account (that stays a separate state).
_RECOMMENDED_FIELDS = ("travel_nickname", "bio", "languages", "travel_styles", "interests")


def _iso(value) -> str:
    """Timestamp to the API's UTC ISO-8601 wire format.

    Mirrors the Phase 4 convention: SQLite returns naive datetimes and
    PostgreSQL aware ones, so every outgoing timestamp is normalized to
    UTC here rather than letting the wire format depend on the database.
    """
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()


def _read_model(profile: TravelProfile) -> TravelProfileRead:
    completion = [name for name in _RECOMMENDED_FIELDS if getattr(profile, name) in (None, [])]
    return TravelProfileRead(
        user_id=profile.user_id,
        travel_nickname=profile.travel_nickname,
        bio=profile.bio,
        home_region=profile.home_region,
        languages=profile.languages,
        travel_styles=profile.travel_styles,
        interests=profile.interests,
        group_size_pref=profile.group_size_pref,
        discoverable=profile.discoverable,
        completion=completion,
        created_at=_iso(profile.created_at),
        updated_at=_iso(profile.updated_at),
    )


def _get_own_profile(db: DbSession, user_id) -> TravelProfile | None:
    return db.scalar(select(TravelProfile).where(TravelProfile.user_id == user_id))


@router.get(
    "/me",
    response_model=TravelProfileRead,
    summary="Get my travel profile",
)
def get_my_profile(current_user: CurrentUser, db: DbSession) -> TravelProfileRead:
    """Return the authenticated user's own travel profile.

    404 when none exists yet (create it with POST). Only the caller's
    own row is ever readable here.
    """
    profile = _get_own_profile(db, current_user.id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No travel profile yet. Create one with POST /api/v1/travel-profile.",
        )
    return _read_model(profile)


@router.post(
    "/me",
    response_model=TravelProfileRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create my travel profile",
)
def create_my_profile(
    body: TravelProfileCreate,
    current_user: CurrentUser,
    db: DbSession,
) -> TravelProfileRead:
    """Initialize the caller's travel profile (one per account).

    Duplicate creation returns 409 (the UNIQUE constraint is the real
    guard; the pre-check only improves the error message). The profile
    starts with whatever visibility the body asked for - default hidden.
    """
    if _get_own_profile(db, current_user.id) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Travel profile already exists. Update it with PATCH.",
        )
    profile = TravelProfile(
        user_id=current_user.id,
        travel_nickname=body.travel_nickname,
        bio=body.bio,
        home_region=body.home_region,
        languages=body.languages,
        travel_styles=body.travel_styles,
        interests=body.interests,
        group_size_pref=body.group_size_pref,
        discoverable=body.discoverable,
    )
    db.add(profile)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Travel profile already exists.",
        ) from exc
    db.refresh(profile)
    return _read_model(profile)


@router.patch(
    "/me",
    response_model=TravelProfileRead,
    summary="Update my travel profile (partial)",
)
def patch_my_profile(
    body: TravelProfilePatch,
    current_user: CurrentUser,
    db: DbSession,
) -> TravelProfileRead:
    """Partial update of the caller's own profile, including visibility.

    Omitted fields keep their value; explicit nulls/empties clear.
    404 when no profile exists yet. Nothing here can touch account-level
    fields (they are not in the schema).
    """
    profile = _get_own_profile(db, current_user.id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No travel profile yet. Create one with POST /api/v1/travel-profile.",
        )

    # `model_dump(exclude_unset=True)` distinguishes "omitted" from
    # "explicitly null", which is what makes partial semantics honest.
    changes = body.model_dump(exclude_unset=True)
    for field_name, value in changes.items():
        setattr(profile, field_name, value)
    profile.updated_at = utc_now()
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return _read_model(profile)
