"""Reusable FastAPI dependencies for authentication (Phase 3).

Plain language: a dependency is a small function FastAPI runs BEFORE a
route handler. `get_current_user` is the gatekeeper for protected routes:
it reads the bearer token, verifies it, loads the user from the database,
and hands the route the actual user object. If anything is wrong (missing
token, bad token, deleted user) it raises 401 and the route never runs.

Crucially, the user's identity ALWAYS comes from the verified token's `sub`
claim - never from a user ID supplied in the request body or URL. This is
what stops one user from acting as another.
"""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.session import get_db
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
CurrentUser = Annotated[User, Depends(get_current_user)]
DbSession = Annotated[Session, Depends(get_db)]
