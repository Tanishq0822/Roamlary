"""Authentication endpoints: registration and login (Phase 3).

Plain language: this router creates accounts and hands out access tokens.
The heavy lifting (hashing, token signing) lives in app/core/security.py,
so these handlers stay short and readable. Registration auto-logs-in the
new user by returning a token, which is the common pattern for a mobile
app (register -> immediately signed in).
"""

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.v1.deps import DbSession
from app.api.v1.schemas.auth import LoginRequest, RegisterRequest, TokenResponse
from app.core.security import (
    create_access_token,
    ensure_auth_configured,
    hash_password,
    verify_password,
)
from app.models.user import User

router = APIRouter(prefix="/auth", tags=["auth"])

# A throwaway hash used ONLY to equalize login timing: when the email is
# unknown we still run one real Argon2 verification against this value, so
# an unknown-email 401 takes about as long as a wrong-password 401.
# Without it, response time would reveal whether an account exists.
# Generated once at import (one-time ~0.1s cost at startup).
_DUMMY_PASSWORD_HASH = hash_password("timing-equalization-only-not-a-real-password")


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new account and return an access token",
)
def register(body: RegisterRequest, db: DbSession) -> TokenResponse:
    """Register a new local account.

    Steps:
    1. Email is already normalized (trimmed + lowercased) by the schema.
    2. Check the email is not already taken -> 409 Conflict if it is.
    3. Hash the password with Argon2id (the plaintext is never stored).
    4. Create the user row.
    5. Return a signed access token so the app is logged in immediately.

    The password hash is never returned.
    """
    # Fail closed BEFORE any database write: if no signing secret is
    # configured we must not create an account the client could never use.
    ensure_auth_configured()

    existing = db.scalar(select(User).where(User.email == body.email))
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    user = User(
        display_name=body.display_name,
        email=body.email,
        password_hash=hash_password(body.password),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        # Two requests raced to register the same email; the unique
        # constraint caught it. Roll back and report the same 409.
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        ) from None
    db.refresh(user)

    return TokenResponse(access_token=create_access_token(user.id))


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate with email + password, return an access token",
)
def login(body: LoginRequest, db: DbSession) -> TokenResponse:
    """Log in and return an access token.

    The error message is IDENTICAL for "unknown email" and "wrong
    password" so an attacker cannot discover which emails are registered
    by watching error responses. The work done is also kept comparable:
    an unknown email still runs one Argon2 verification (against a dummy
    hash) so response TIME does not reveal whether the account exists.
    """
    user = db.scalar(select(User).where(User.email == body.email))

    if user is None:
        # Equalize timing, then fail with the same generic error.
        verify_password(body.password, _DUMMY_PASSWORD_HASH)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    # verify_password also returns False for a user with no local password
    # (a future Firebase-only account).
    if not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    return TokenResponse(access_token=create_access_token(user.id))
