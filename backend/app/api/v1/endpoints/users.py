"""User-profile endpoints: GET/PATCH /users/me (Phase 3).

Plain language: these routes let a logged-in user read and edit their OWN
profile. The caller's identity ALWAYS comes from the verified token (via
the get_current_user dependency) - the client never sends "which user am
I", so one user cannot read or edit another user's profile by guessing an
ID. Only `display_name` is editable; identity fields like `id`, `email`,
`password_hash`, and `firebase_uid` are protected and cannot be changed
here.
"""

from fastapi import APIRouter, HTTPException, status
from sqlalchemy.exc import IntegrityError

from app.api.v1.deps import CurrentUser, DbSession
from app.api.v1.schemas.auth import UserProfile, UserProfileUpdate
from app.db.base_class import utc_now

router = APIRouter(prefix="/users", tags=["users"])


@router.get(
    "/me",
    response_model=UserProfile,
    summary="Return the authenticated user's public profile",
)
def read_me(current_user: CurrentUser) -> UserProfile:
    """Return the caller's own public profile.

    `current_user` is resolved from the bearer token. There is no user ID
    in the path or body, so this can only ever be the caller's own profile.
    The `UserProfile` schema omits password_hash, so it cannot leak.
    """
    return UserProfile.model_validate(current_user)


@router.patch(
    "/me",
    response_model=UserProfile,
    summary="Update the authenticated user's display name",
)
def update_me(
    body: UserProfileUpdate,
    current_user: CurrentUser,
    db: DbSession,
) -> UserProfile:
    """Update permitted fields on the caller's own profile.

    Only `display_name` is accepted. The request schema is configured with
    `extra="forbid"`, so attempting to send `id`, `email`, `password_hash`,
    or `firebase_uid` is rejected with a 422 validation error rather than
    being silently dropped - protected fields cannot be smuggled in.

    A body with no editable field (for example `{}`) is a valid no-op:
    the profile is returned unchanged and `updated_at` is NOT touched,
    so the timestamp always means "last real change".
    """
    if body.display_name is not None:
        current_user.display_name = body.display_name

        # Bump updated_at explicitly so the change is reflected even though
        # we are mutating an already-loaded object.
        current_user.updated_at = utc_now()

        db.add(current_user)
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Could not save profile changes.",
            ) from exc
        db.refresh(current_user)

    return UserProfile.model_validate(current_user)
