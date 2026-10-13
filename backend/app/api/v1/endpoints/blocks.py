"""Person-to-person blocking endpoints (Phase 8).

Plain language: blocking is the safety switch. "I block them" means
neither of us can message, request, discover, or travel-request the
other anymore - while history both of us already have stays readable
(nothing is silently deleted). Unblocking restores the possibility of
contact; it never resurrects anything (nothing was destroyed).

Gate choice is deliberate: blocking stays on PLAIN authentication
(CurrentUser), like cancelling your own request. A user being harassed
must be able to block WHILE unverified - the social gate must never
lock anyone out of a safety tool. What the block AFFECTS (discovery,
sending, accepting) is still gated normally at those endpoints.
"""

from datetime import UTC
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

from app.api.v1.deps import CurrentUser, DbSession
from app.api.v1.schemas.blocks import BlockCreate, BlockList, BlockRead
from app.models.user import User
from app.models.user_block import UserBlock

router = APIRouter(prefix="/blocks", tags=["blocks"])


def _iso(value) -> str:
    """Timestamp to UTC ISO-8601 (same normalization as other endpoints)."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()


def _block_read(row: UserBlock) -> BlockRead:
    """One block row as the blocker sees it (display name for management)."""
    return BlockRead(
        id=row.id,
        blocked_id=row.blocked_id,
        blocked_display_name=row.blocked.display_name,
        created_at=_iso(row.created_at),
    )


@router.post(
    "",
    response_model=BlockRead,
    status_code=status.HTTP_201_CREATED,
    summary="Block another user (stops both directions)",
)
def block_user(body: BlockCreate, current_user: CurrentUser, db: DbSession) -> BlockRead:
    """Block `blocked_id`: from now on neither direction of the pair may
    message, request, discover, or travel-request the other.

    Rejected with:
    - 422 when blocking yourself (structurally impossible: schema +
      database CHECK);
    - 404 when the account does not exist (blocks reference real users
      only, so the list can never accumulate junk);
    - 409 when you already blocked them (pre-check for a friendly
      message; the UNIQUE pair index is the race-proof source of truth).
    """
    if body.blocked_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="You cannot block yourself.",
        )
    target = db.scalar(select(User).where(User.id == body.blocked_id))
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )
    existing = db.scalar(
        select(UserBlock).where(
            UserBlock.blocker_id == current_user.id,
            UserBlock.blocked_id == body.blocked_id,
        )
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You have already blocked this user.",
        )
    row = UserBlock(blocker_id=current_user.id, blocked_id=body.blocked_id)
    db.add(row)
    try:
        db.commit()
    except IntegrityError as exc:
        # Two racing block calls: the UNIQUE pair index kept exactly one.
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You have already blocked this user.",
        ) from exc
    db.refresh(row)
    row = db.scalar(
        select(UserBlock).options(joinedload(UserBlock.blocked)).where(UserBlock.id == row.id)
    )
    return _block_read(row)


@router.get(
    "",
    response_model=BlockList,
    summary="List the users I blocked (newest first)",
)
def list_blocks(current_user: CurrentUser, db: DbSession) -> BlockList:
    """The caller's OWN block list only - blocker is always the token's
    account, so nobody can read, enumerate, or manage anyone else's."""
    rows = (
        db.scalars(
            select(UserBlock)
            .options(joinedload(UserBlock.blocked))
            .where(UserBlock.blocker_id == current_user.id)
            .order_by(UserBlock.created_at.desc(), UserBlock.id.desc())
        )
        .unique()
        .all()
    )
    return BlockList(total=len(rows), blocks=[_block_read(row) for row in rows])


@router.delete(
    "/{blocked_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Unblock a user I previously blocked",
)
def unblock_user(blocked_id: UUID, current_user: CurrentUser, db: DbSession) -> None:
    """Remove MY block of `blocked_id` (204, no body).

    Only the blocker can remove it: the lookup is scoped to
    (blocker == me, blocked == id), so unblocking someone else's block -
    or a block that never existed - returns the identical 404.
    Unblocking restores the possibility of contact; it deletes nothing
    (nothing was ever deleted by blocking).
    """
    row = db.scalar(
        select(UserBlock).where(
            UserBlock.blocker_id == current_user.id,
            UserBlock.blocked_id == blocked_id,
        )
    )
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Block not found.",
        )
    db.delete(row)
    db.commit()
