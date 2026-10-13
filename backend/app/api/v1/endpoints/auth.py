"""Authentication endpoints: registration and login (Phase 3).

Plain language: this router creates accounts and hands out access tokens.
The heavy lifting (hashing, token signing) lives in app/core/security.py,
so these handlers stay short and readable. Registration auto-logs-in the
new user by returning a token, which is the common pattern for a mobile
app (register -> immediately signed in).
"""

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.v1.deps import CurrentSession, DbSession
from app.api.v1.schemas.auth import (
    AuthSessionList,
    AuthSessionRead,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
)
from app.core.security import (
    create_access_token,
    ensure_auth_configured,
    hash_password,
    verify_password,
)
from app.models.auth_session import AuthSession
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

    return TokenResponse(access_token=_mint_session_token(db, user, body.device_label))


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

    return TokenResponse(access_token=_mint_session_token(db, user, body.device_label))


def _mint_session_token(db, user: User, label: str | None) -> str:
    """Create a login-session row and a token pointing at it (Phase 8).

    Every login/register mints exactly one session row; the token carries
    its id (`sid`) plus the user's current `token_version` (`tv`), so a
    later logout/revoke-all makes THIS token stop working on next use.
    """
    session = AuthSession(user_id=user.id, label=label)
    db.add(session)
    db.commit()
    db.refresh(session)
    return create_access_token(
        user.id, session_id=session.id, token_version=user.token_version or 0
    )


def _iso(value) -> str | None:
    """Timestamp to UTC ISO-8601 (same normalization as other endpoints)."""
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()


def _session_read(row: AuthSession, current_id: UUID | None) -> AuthSessionRead:
    """One session row as its owner sees it (never another user's)."""
    return AuthSessionRead(
        id=row.id,
        label=row.label,
        created_at=_iso(row.created_at),
        revoked_at=_iso(row.revoked_at),
        current=current_id is not None and row.id == current_id,
    )


def _require_tracked_session(current_id: UUID | None):
    """404 for legacy (pre-Phase-8) tokens on endpoints that act on the
    current session row: there is no row to act on. Revoke-all still
    covers legacy tokens (it bumps the version they are checked by)."""
    if current_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="This token has no trackable session (legacy token). "
            "Use POST /api/v1/auth/revoke-all to revoke it.",
        )


@router.get(
    "/sessions",
    response_model=AuthSessionList,
    summary="List my login sessions (newest first)",
)
def list_sessions(session: CurrentSession, db: DbSession) -> AuthSessionList:
    """The caller's OWN sessions only - user id always comes from the
    token, never from a parameter, so nobody can list anyone else's."""
    user, current_id = session
    rows = db.scalars(
        select(AuthSession)
        .where(AuthSession.user_id == user.id)
        .order_by(AuthSession.created_at.desc(), AuthSession.id.desc())
    ).all()
    return AuthSessionList(
        total=len(rows),
        sessions=[_session_read(row, current_id) for row in rows],
    )


@router.post(
    "/logout",
    response_model=AuthSessionRead,
    summary="Log out this session (the calling token stops working)",
)
def logout(session: CurrentSession, db: DbSession) -> AuthSessionRead:
    """Revoke the CURRENT session row: the calling token gets 401 on its
    next use (revocation is enforced on every request, not at expiry).
    Other sessions are untouched - use revoke-others/revoke-all for
    those. Raw tokens are never stored or logged; only the row id the
    token already carried is stamped."""
    user, current_id = session
    _require_tracked_session(current_id)
    row = db.scalar(
        select(AuthSession).where(
            AuthSession.id == current_id,
            AuthSession.user_id == user.id,
        )
    )
    if row is None or row.revoked_at is not None:
        # Already gone (or never existed for this user): the token is
        # still valid for nothing - report Gone, not success.
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="This session is already revoked.",
        )
    row.revoked_at = datetime.now(UTC)
    db.commit()
    db.refresh(row)
    return _session_read(row, current_id)


@router.post(
    "/sessions/{session_id}/revoke",
    response_model=AuthSessionRead,
    summary="Revoke one of my sessions by id",
)
def revoke_session(session_id: UUID, session: CurrentSession, db: DbSession) -> AuthSessionRead:
    """Revoke a selected OWN session. A session id that does not exist
    or belongs to another account returns the identical 404, so session
    ids cannot be used to probe other users. Revoking an already-revoked
    row is idempotent (200 with the unchanged row)."""
    user, current_id = session
    row = db.scalar(
        select(AuthSession).where(
            AuthSession.id == session_id,
            AuthSession.user_id == user.id,
        )
    )
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found.",
        )
    if row.revoked_at is None:
        row.revoked_at = datetime.now(UTC)
        db.commit()
        db.refresh(row)
    return _session_read(row, current_id)


@router.post(
    "/sessions/revoke-others",
    response_model=AuthSessionList,
    summary="Revoke all my sessions except the current one",
)
def revoke_other_sessions(session: CurrentSession, db: DbSession) -> AuthSessionList:
    """Keep exactly the calling session; kill every other OWN session.
    The current token keeps working (that is the documented point of
    this operation); everything else gets 401 on next use."""
    user, current_id = session
    _require_tracked_session(current_id)
    rows = db.scalars(
        select(AuthSession).where(
            AuthSession.user_id == user.id,
            AuthSession.revoked_at.is_(None),
            AuthSession.id != current_id,
        )
    ).all()
    now = datetime.now(UTC)
    for row in rows:
        row.revoked_at = now
    db.commit()
    return list_sessions(session, db)


@router.post(
    "/revoke-all",
    response_model=AuthSessionList,
    summary="Revoke ALL my sessions including the current one",
)
def revoke_all_sessions(session: CurrentSession, db: DbSession) -> AuthSessionList:
    """Account-wide revocation: stamp every OWN session row AND bump
    users.token_version, which additionally kills pre-Phase-8 legacy
    tokens (they carry no session id and are governed by the version
    check alone). The calling token stops working too - the client must
    log in again. Only ever touches the caller's rows: the WHERE clause
    is user-scoped, so no unrelated account can be affected."""
    user, _current_id = session
    now = datetime.now(UTC)
    rows = db.scalars(
        select(AuthSession).where(
            AuthSession.user_id == user.id,
            AuthSession.revoked_at.is_(None),
        )
    ).all()
    for row in rows:
        row.revoked_at = now
    user.token_version = (user.token_version or 0) + 1
    db.commit()
    # The full list (all rows now show revoked_at, including the
    # caller's just-killed current session) - honest state, no hiding.
    return list_sessions(session, db)
