"""Server-side owner provisioning CLI (Phase 6b).

Plain language: exactly ONE supported way to grant the `owner` role -
a human with shell access to the machine holding the database
credentials runs this command:

    cd backend
    .venv\\Scripts\\python -m app.cli make-owner someone@example.com

WHY A CLI AND NOT AN API: every HTTP path that could grant privileges
would be an attack surface (stolen token, forged header, confused
deputy). This command lives behind the strongest boundary the project
has - you must already be able to run code on the server - so:

  * registration NEVER grants owner (default role is 'user'),
  * owning an email address, signing up first, or knowing public
    project details grants NOTHING,
  * no endpoint, body field, or header can change a role.

SECURITY PROPERTIES:
  * prints only the account email + role result; never the DATABASE_URL,
    passwords, or tokens,
  * idempotent: promoting an existing owner succeeds without changes,
  * exit code 0 on success, 1 on failure (script-friendly).

This is the "smallest safe foundation" the phase allows: no secret
answers, no hardcoded credentials, no email-list bootstrap. Re-running
with a different email TRANSFERS nothing automatically - each account
keeps its role until deliberately changed (revoke via SQL on the server
if ever needed; no API path exists either way).
"""

from __future__ import annotations

import argparse
import sys

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import UserRole
from app.models.user import User


def normalize_email(email: str) -> str:
    """Same normalization the auth layer uses: trim + lowercase."""
    return email.strip().lower()


def promote_to_owner(db: Session, email: str) -> User:
    """Grant `owner` to the account with this email (commit included).

    Raises LookupError when no account matches - the caller reports it
    without echoing anything sensitive.
    """
    user = db.scalar(select(User).where(User.email == normalize_email(email)))
    if user is None:
        raise LookupError("no account with that email")
    if user.role == UserRole.OWNER:
        return user  # already an owner: nothing to change
    user.role = UserRole.OWNER
    db.commit()
    return user


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns a process exit code (0 = success)."""
    parser = argparse.ArgumentParser(
        prog="python -m app.cli",
        description="Roamlary server-side administration (owner provisioning).",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    make_owner = subparsers.add_parser(
        "make-owner",
        help="Grant the owner role to an account (server access required).",
    )
    make_owner.add_argument("email", help="Email address of the existing account.")
    args = parser.parse_args(argv)

    # Import lazily so `--help` works even without database configuration,
    # and so the engine is only created when a command actually runs.
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        user = promote_to_owner(db, args.email)
    except LookupError as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()

    print(f"OK: {normalize_email(args.email)} now has role={user.role}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
