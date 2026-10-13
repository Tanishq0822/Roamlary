"""Trip-sharing endpoints (Phase 12).

Plain language: an owner opens a bounded window ("my accepted travel
partners may see this trip until Friday") and can close it any time.
Viewers are exactly the owner's ACCEPTED travel-partner counterparts -
the only pre-verified social relationship, so no new identity system,
no contact-list syncing, and no live-location infrastructure (which
does not exist - the share honestly carries plan facts + check-in
states, never GPS).

Expiry and revocation are enforced on the SERVER at every read
(expired or revoked shares read as gone); the UI cannot override them.
Shares live at most 90 days.
"""

from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

from app.api.v1.deps import CurrentUser, DbSession
from app.api.v1.schemas.sharing import (
    SharedItineraryRead,
    TripShareCreate,
    TripShareList,
    TripShareRead,
)
from app.models.enums import BuddyRequestStatus
from app.models.travel_partner_request import TravelPartnerRequest
from app.models.travel_plan import TravelPlan
from app.models.trip_share import TripShare

router = APIRouter(prefix="/trip-shares", tags=["trip-sharing"])

# A share is a bounded grant, not a standing permission.
_MAX_SHARE_DAYS = 90


def _now() -> datetime:
    return datetime.now(UTC)


def _as_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _partner_ids(db, user_id: UUID) -> set[UUID]:
    """User ids with an ACCEPTED travel-partner relationship (either
    direction) - the only viewers a share ever has."""
    rows = db.execute(
        select(TravelPartnerRequest.requester_id, TravelPartnerRequest.recipient_id).where(
            TravelPartnerRequest.status == BuddyRequestStatus.ACCEPTED,
            or_(
                TravelPartnerRequest.requester_id == user_id,
                TravelPartnerRequest.recipient_id == user_id,
            ),
        )
    ).all()
    partners: set[UUID] = set()
    for requester_id, recipient_id in rows:
        partners.add(recipient_id if requester_id == user_id else requester_id)
    return partners


def _share_read(db, row: TripShare) -> TripShareRead:
    """One share grant as its owner sees it."""
    destination = None
    if row.plan_id is not None:
        plan = db.get(TravelPlan, row.plan_id)
        destination = plan.destination if plan is not None else None
    return TripShareRead(
        id=row.id,
        plan_id=row.plan_id,
        plan_destination=destination,
        expires_at=row.expires_at,
        revoked_at=row.revoked_at,
        created_at=row.created_at,
    )


def _live_share(db, share_id: UUID) -> TripShare | None:
    """A share row that is unrevoked AND unexpired, or None (expired or
    revoked shares read as gone - enforced here, not in the UI)."""
    row = db.scalar(select(TripShare).where(TripShare.id == share_id))
    if row is None or row.revoked_at is not None:
        return None
    if _as_aware(row.expires_at) <= _now():
        return None
    return row


@router.post(
    "",
    response_model=TripShareRead,
    status_code=status.HTTP_201_CREATED,
    summary="Share a trip with my accepted travel partners",
)
def create_trip_share(
    body: TripShareCreate, current_user: CurrentUser, db: DbSession
) -> TripShareRead:
    """Open a bounded sharing window: optional own plan + a future
    expiry at most 90 days out. The plan (when given) must be the
    caller's own (foreign plans 404 - no probing). Viewers are the
    caller's accepted travel partners, resolved live at READ time (a
    partnership formed later sees the share; one that ended... cannot
    end - accepted is terminal - so the set only grows)."""
    if body.expires_at.tzinfo is None or body.expires_at.utcoffset() is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="expires_at must carry a timezone (ISO 8601 with Z/offset).",
        )
    expires = _as_aware(body.expires_at)
    if expires <= _now():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="expires_at must be in the future.",
        )
    if expires - _now() > timedelta(days=_MAX_SHARE_DAYS):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Shares live at most 90 days.",
        )
    if body.plan_id is not None:
        plan = db.scalar(
            select(TravelPlan).where(
                TravelPlan.id == body.plan_id,
                TravelPlan.user_id == current_user.id,
            )
        )
        if plan is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Travel plan not found.",
            )
    row = TripShare(owner_id=current_user.id, plan_id=body.plan_id, expires_at=expires)
    db.add(row)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Could not save the trip share.",
        ) from exc
    db.refresh(row)
    return _share_read(db, row)


@router.get(
    "",
    response_model=TripShareList,
    summary="List my trip shares (newest first)",
)
def list_trip_shares(
    current_user: CurrentUser,
    db: DbSession,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> TripShareList:
    """My own share grants (live, expired, and revoked - the owner sees
    the full history of what they opened and closed)."""
    conds = [TripShare.owner_id == current_user.id]
    total = db.scalar(select(func.count()).select_from(TripShare).where(*conds)) or 0
    rows = db.scalars(
        select(TripShare)
        .where(*conds)
        .order_by(TripShare.created_at.desc(), TripShare.id.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return TripShareList(
        total=total,
        offset=offset,
        limit=limit,
        results=[_share_read(db, r) for r in rows],
    )


@router.get(
    "/shared-with-me",
    response_model=TripShareList,
    summary="Trip shares I may currently view",
)
def list_shared_with_me(
    current_user: CurrentUser,
    db: DbSession,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> TripShareList:
    """Live shares from owners I am an accepted travel partner of.
    Expired/revoked shares are excluded HERE (server-side)."""
    partners = _partner_ids(db, current_user.id)
    if not partners:
        return TripShareList(total=0, offset=offset, limit=limit, results=[])
    rows = db.scalars(
        select(TripShare)
        .where(
            TripShare.owner_id.in_(partners),
            TripShare.revoked_at.is_(None),
            TripShare.expires_at > _now(),
        )
        .order_by(TripShare.created_at.desc(), TripShare.id.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return TripShareList(
        total=len(rows),
        offset=offset,
        limit=limit,
        results=[_share_read(db, r) for r in rows],
    )


@router.get(
    "/{share_id}",
    response_model=SharedItineraryRead,
    summary="Read a shared itinerary I am entitled to see",
)
def get_shared_itinerary(
    share_id: UUID, current_user: CurrentUser, db: DbSession
) -> SharedItineraryRead:
    """The plan facts of a live share: owner display name, destination,
    dates, grant window. 404 unless I am the owner or a currently
    accepted partner AND the share is live (unrevoked, unexpired).
    Never messages, SOS records, or anyone else's data - and never live
    GPS (no such infrastructure exists; the shape carries no location
    beyond the plan's own destination/dates)."""
    row = db.scalar(
        select(TripShare).options(joinedload(TripShare.owner)).where(TripShare.id == share_id)
    )
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trip share not found.",
        )
    live = _live_share(db, row.id)
    if live is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trip share not found.",
        )
    if current_user.id != row.owner_id and current_user.id not in _partner_ids(db, row.owner_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trip share not found.",
        )
    plan = db.get(TravelPlan, row.plan_id) if row.plan_id is not None else None
    return SharedItineraryRead(
        share_id=row.id,
        owner_display_name=row.owner.display_name,
        plan_destination=plan.destination if plan is not None else None,
        plan_start_date=plan.start_date.isoformat() if plan is not None else None,
        plan_end_date=plan.end_date.isoformat() if plan is not None else None,
        expires_at=row.expires_at,
    )


@router.delete(
    "/{share_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Stop sharing (revoke my share)",
)
def revoke_trip_share(share_id: UUID, current_user: CurrentUser, db: DbSession) -> None:
    """Owner revokes a share -> `revoked_at` stamped (viewers lose
    access immediately; the row stays as history). Only the owner;
    anyone else's id is the identical 404."""
    row = db.scalar(
        select(TripShare).where(
            TripShare.id == share_id,
            TripShare.owner_id == current_user.id,
        )
    )
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trip share not found.",
        )
    if row.revoked_at is None:
        row.revoked_at = _now()
        db.commit()
