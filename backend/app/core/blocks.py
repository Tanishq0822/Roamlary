"""Blocking lookups shared by every surface (Phase 8).

Plain language: a block stops BOTH directions. If A blocks B, then for
ANY messaging/discovery/travel-request decision about the pair (A, B)
the answer is "no" - no matter who is asking about whom. This module is
the single place that rule lives, so discovery, travel requests, and
chat cannot drift apart.

Kept independent from discoverability switches and identity
verification on purpose: blocking is its own layer (brief item 6).
"""

from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.user_block import UserBlock


def blocked_user_ids(db: Session, user_id: UUID) -> set[UUID]:
    """Every user id blocked-BY or blocking the given user.

    One query for both directions: rows where I am the blocker contribute
    the blocked id; rows where I am blocked contribute the blocker id.
    Either membership excludes the pair from messaging, discovery, and
    new travel-partner requests.
    """
    rows = db.execute(
        select(UserBlock.blocker_id, UserBlock.blocked_id).where(
            or_(
                UserBlock.blocker_id == user_id,
                UserBlock.blocked_id == user_id,
            )
        )
    ).all()
    others: set[UUID] = set()
    for blocker_id, blocked_id in rows:
        others.add(blocked_id if blocker_id == user_id else blocker_id)
    return others
