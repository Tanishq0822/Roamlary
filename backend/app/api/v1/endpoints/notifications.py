"""Notification inbox endpoints (Phase 12).

Plain language: this is the READ side of the notification service. Rows
are created by events (SOS, invitations, approvals, cancellations,
shares) through `app/services/notifications.py` - never by clients, so
there is no POST route here. Listing, reading, and retrying are all
scoped to the token's user: nobody sees or touches anyone else's inbox
(the identical 404 covers missing and foreign ids).

Delivery honesty (repeated from the service): `delivered` + `in_app`
means visible here; `unavailable` means no provider is configured and
nothing was sent; `unknown` means handed off without a receipt.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from app.api.v1.deps import CurrentUser, DbSession
from app.api.v1.schemas.sharing import NotificationList, NotificationRead
from app.models.notification import Notification
from app.services.notifications import reattempt

router = APIRouter(prefix="/notifications", tags=["notifications"])


def _notification_read(row: Notification) -> NotificationRead:
    """One inbox row as its recipient sees it (state, never secrets)."""
    return NotificationRead(
        id=row.id,
        kind=row.kind,
        title=row.title,
        body=row.body,
        channel=row.channel,
        status=row.status,
        attempts=row.attempts or 0,
        last_error=row.last_error,
        read_at=row.read_at,
        created_at=row.created_at,
    )


@router.get(
    "",
    response_model=NotificationList,
    summary="List my notifications (newest first)",
)
def list_notifications(
    current_user: CurrentUser,
    db: DbSession,
    unread_only: Annotated[bool, Query(description="Only rows never marked read.")] = False,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> NotificationList:
    """The caller's OWN inbox only - user id always comes from the
    token, so inboxes cannot leak across accounts."""
    conds = [Notification.user_id == current_user.id]
    if unread_only:
        conds.append(Notification.read_at.is_(None))
    total = db.scalar(select(func.count()).select_from(Notification).where(*conds)) or 0
    rows = db.scalars(
        select(Notification)
        .where(*conds)
        .order_by(Notification.created_at.desc(), Notification.id.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return NotificationList(
        total=total,
        offset=offset,
        limit=limit,
        results=[_notification_read(r) for r in rows],
    )


@router.post(
    "/{notification_id}/read",
    response_model=NotificationRead,
    summary="Mark one of my notifications read",
)
def mark_notification_read(
    notification_id: UUID, current_user: CurrentUser, db: DbSession
) -> NotificationRead:
    """Stamp `read_at` with the server clock (idempotent - re-reading
    keeps the first stamp). Foreign or missing ids are the same 404."""
    from datetime import UTC, datetime

    row = db.scalar(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == current_user.id,
        )
    )
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found.",
        )
    if row.read_at is None:
        row.read_at = datetime.now(UTC)
        db.commit()
        db.refresh(row)
    return _notification_read(row)


@router.post(
    "/{notification_id}/retry",
    response_model=NotificationRead,
    summary="Retry a failed/unavailable notification of mine",
)
def retry_notification(
    notification_id: UUID, current_user: CurrentUser, db: DbSession
) -> NotificationRead:
    """Re-attempt delivery IN PLACE (same row, attempts + 1 - retries
    never duplicate alerts, brief 12.D). Only `failed`/`unavailable`/
    `unknown` rows retry; `delivered`/`queued`/`attempted` rows return
    409 (nothing to retry). Without a provider the row returns to
    `unavailable` with a fresh honest error - a recorded failure, never
    a silent drop or a faked success."""
    from app.models.enums import NotificationStatus

    row = db.scalar(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == current_user.id,
        )
    )
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found.",
        )
    if row.status not in (
        NotificationStatus.FAILED,
        NotificationStatus.UNAVAILABLE,
        NotificationStatus.UNKNOWN,
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Only failed/unavailable/unknown notifications can be "
                f"retried (current: '{row.status}')."
            ),
        )
    return _notification_read(reattempt(db, row))
