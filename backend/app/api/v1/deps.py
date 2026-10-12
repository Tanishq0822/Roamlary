"""Reusable FastAPI dependencies for authentication and authorization.

Plain language: a dependency is a small function FastAPI runs BEFORE a
route handler.

- `get_current_user` (Phase 3) is the gatekeeper for protected routes: it
  reads the bearer token, verifies it, loads the user from the database,
  and hands the route the actual user object. If anything is wrong
  (missing token, bad token, deleted user) it raises 401 and the route
  never runs.
- `require_owner` (Phase 6b) is the AUTHORIZATION layer: routes that
  manage policy or review verification requests demand the `owner` role
  and raise 403 otherwise. Fail-closed: any role value that is not
  exactly `owner` (including a corrupt value) is denied.
- `require_verified_user` (Phase 6b) is the social-access gate: it applies
  the database-stored verification policy on every request and raises 403
  for unverified/pending/rejected accounts when the policy requires
  verification. The policy is read live from the database per request, so
  a policy flip takes effect immediately and no JWT claim can go stale.

Crucially, the user's identity ALWAYS comes from the verified token's `sub`
claim - never from a user ID supplied in the request body or URL. This is
what stops one user from acting as another.
"""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.policy import get_policy
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.enums import UserRole, VerificationStatus
from app.models.user import User

# OAuth2PasswordBearer extracts the "Authorization: Bearer <token>" header.
# tokenUrl documents where a token can be obtained (for the /docs UI).
# If the header is missing entirely, FastAPI returns 401 automatically.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    """Return the authenticated User for this request, or raise 401.

    Steps:
    1. Decode + validate the token (signature, HS256, expiry). A bad or
       expired token raises 401 inside decode_access_token.
    2. The token's `sub` claim is the user's UUID.
    3. Look that user up in the database.
    4. A validly signed token whose user no longer exists still gets 401 -
       the account was deleted, so the token must stop working.
    """
    user_id = decode_access_token(token)
    user = db.scalar(select(User).where(User.id == user_id))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token.",
        )
    return user


# Type-hint aliases so route handlers stay short and readable.
# Defined here (before the gatekeepers below) because parameter annotations
# are evaluated when the function is defined.
CurrentUser = Annotated[User, Depends(get_current_user)]
DbSession = Annotated[Session, Depends(get_db)]


def require_owner(user: CurrentUser) -> User:
    """Owner-only gate for policy management and verification review.

    Fail-closed by construction: the check is an exact match against the
    `owner` role, so an unknown/corrupt role value (anything the CHECK
    constraint somehow allowed through) is DENIED, never elevated. Roles
    are only ever granted by the server-side CLI - no request can set one.
    """
    if user.role != UserRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Owner privileges required for this action.",
        )
    return user


# Actionable, status-specific 403 details: tell the caller WHERE they are
# and WHAT to do next, without leaking anything about other users.
_SOCIAL_403_DETAILS: dict[str, str] = {
    VerificationStatus.UNVERIFIED: (
        "Identity verification is required for social features. "
        "Your status is 'unverified': submit a verification request first "
        "(POST /api/v1/verification/requests)."
    ),
    VerificationStatus.PENDING: (
        "Identity verification is required for social features. "
        "Your status is 'pending': your request is under review."
    ),
    VerificationStatus.REJECTED: (
        "Identity verification is required for social features. "
        "Your status is 'rejected': your latest request was declined; "
        "you may submit a new one."
    ),
}


def require_verified_user(
    user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> User:
    """Social-access gate: allow only verified accounts when policy says so.

    Order matters and is intentional:
    1. Authentication first (CurrentUser -> 401 if no valid token).
    2. Read the LIVE policy from the database (fail-closed: a missing or
       corrupt policy row counts as "verification required").
    3. Policy off  -> every authenticated account passes (the owner can
       temporarily open social features during development).
    4. Policy on   -> only verification_status == 'verified' passes;
       unverified/pending/rejected get 403 with an actionable message.

    Safety workflows (trusted contacts, check-ins, SOS, reports) and
    account/verification routes deliberately do NOT use this dependency -
    incomplete verification must never lock anyone out of safety tools.
    """
    if not get_policy(db):
        return user
    if user.verification_status != VerificationStatus.VERIFIED:
        detail = _SOCIAL_403_DETAILS.get(
            user.verification_status,
            # Corrupt/unknown status fails closed with a generic message.
            "Identity verification is required for social features.",
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)
    return user


# Gatekeeper aliases for route handlers (CurrentUser/DbSession above).
OwnerUser = Annotated[User, Depends(require_owner)]
SocialUser = Annotated[User, Depends(require_verified_user)]
