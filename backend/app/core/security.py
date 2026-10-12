"""Password hashing and JWT helpers (Phase 3).

Plain language: this module holds the two "security verbs" of the app -
turning a password into a one-way hash (and checking a password against a
hash), and creating/validating the signed access tokens that let a request
say "I am this user".

Two decisions worth understanding:
1. Argon2id is the hashing algorithm. It is a modern, memory-hard
   algorithm recommended by OWASP. It is deliberately SLOW and memory
   intensive on purpose: if a database of hashes ever leaks, an attacker
   cannot brute-force many passwords per second.
2. JWTs are signed with HS256 using a server-side secret. The algorithm is
   a CONSTANT in this file - we never trust an algorithm sent by the client
   (that is the classic "algorithm confusion" vulnerability).
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from fastapi import HTTPException, status

from app.core.config import settings

# Fixed signing algorithm. Never accept an algorithm from the token itself.
ALGORITHM = "HS256"

# Argon2id parameters. `time_cost` (iterations), `memory_cost` (KiB),
# `parallelism` (threads). These are OWASP's 2024 "second recommended"
# settings - a good balance of security and speed for a web login.
_hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4)


def hash_password(password: str) -> str:
    """Return a one-way Argon2id hash of the password.

    The original password cannot be recovered from this string. A fresh
    random salt is baked into every hash, so two identical passwords
    produce different hashes.
    """
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    """Check a plain password against a stored hash, in constant time.

    Returns False (never raises) for a wrong password, a missing hash, or a
    corrupt hash. Argon2's verify handles the constant-time comparison.
    """
    if not password_hash:
        return False
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def _require_secret() -> str:
    """Return the signing secret, or fail CLOSED if it is not configured.

    Fail-closed means: no secret -> refuse to issue or check tokens (503),
    rather than silently signing with a weak/default value. This keeps a
    usable signing key out of the source code.
    """
    if not settings.jwt_secret_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is not configured on this server.",
        )
    return settings.jwt_secret_key


def ensure_auth_configured() -> None:
    """Raise 503 if no signing secret is configured; otherwise do nothing.

    Public precheck so endpoints can FAIL CLOSED before doing any work
    (for example before creating a database row), without needing a token
    to exist yet.
    """
    _require_secret()


def create_access_token(user_id: UUID) -> str:
    """Create a signed HS256 access token for a user.

    Claims (the token's data fields):
    - sub: the user's UUID as a string (who this token represents)
    - iat: issued-at time
    - exp: expiry, now + ACCESS_TOKEN_EXPIRE_MINUTES

    No password, hash, or other personal data is put inside the token.
    """
    secret = _require_secret()
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(payload, secret, algorithm=ALGORITHM)


def decode_access_token(token: str) -> UUID:
    """Validate a token and return the user's UUID, or raise 401.

    Checks performed by PyJWT:
    - signature matches our secret (HS256)
    - the algorithm is exactly HS256 (rejects "none" / other algorithms)
    - the token is not expired (exp in the past -> rejection)
    - required claims (sub, exp) are present

    A validly signed token that references a deleted user is still returned
    here; the caller must then confirm the user still exists.
    """
    secret = _require_secret()
    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=[ALGORITHM],
            options={"require": ["sub", "exp"]},
        )
        return UUID(payload["sub"])
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired.",
        ) from exc
    except (jwt.InvalidTokenError, ValueError, KeyError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token.",
        ) from exc
