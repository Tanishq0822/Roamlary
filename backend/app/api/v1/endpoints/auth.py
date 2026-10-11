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
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User

router = APIRouter(prefix="/auth", tags=["auth"])


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
    by watching error responses.
    """
    user = db.scalar(select(User).where(User.email == body.email))

    # verify_password returns False for a wrong password OR a user with no
    # local password (a future Firebase-only account).
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    return TokenResponse(access_token=create_access_token(user.id))
