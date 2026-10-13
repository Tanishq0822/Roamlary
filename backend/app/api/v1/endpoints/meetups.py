"""Meetup (public group activity) endpoints (Phase 9).

Plain language: meetups are the PUBLIC half of the shared event
foundation - discoverable, joinable under the host's policy (open or
approval), with a host-managed guest list and host-only bulletins.
House parties reuse the same table and lifecycle via `parties.py`;
this module refuses to serve them (404 - private events are invisible
here by construction, not by filter).

Gate choice: every route needs SocialUser (the unchanged verification
gate). Discovery of strangers, joining, and guest lists are social
actions; nothing here is a safety tool that must stay open while
unverified.
"""

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

from app.api.v1.deps import DbSession, SocialUser
from app.api.v1.schemas.meetup import (
    AnnouncementCreate,
    AnnouncementRead,
    MeetupCreate,
    MeetupPatch,
    MeetupRead,
    MembershipRead,
)
from app.core.blocks import blocked_user_ids
from app.core.rate_limit import check_rate_limit
from app.models import MeetupCategory
from app.models.enums import MeetupKind, MeetupStatus, MembershipStatus
from app.models.meetup import Meetup
from app.models.meetup_announcement import MeetupAnnouncement
from app.models.meetup_membership import MeetupMembership
from app.models.user import User
from app.services import events as event_svc
from app.services.notifications import record_notification

router = APIRouter(prefix="/meetups", tags=["meetups"])

# Abuse controls (shared in-process limiter, same documented caveat).
_CREATE_LIMIT_PER_HOUR = 20
_JOIN_LIMIT_PER_HOUR = 30


def _lock_event_row(db, meetup_id: UUID) -> None:
    """Serialize concurrent capacity decisions on PostgreSQL.

    Approving two join requests at once must not overbook: taking a row
    lock on the event serializes approvers, so the capacity recheck
    inside the same transaction sees every committed approval. SQLite is
    single-writer already, so the lock is PostgreSQL-only (its dialect
    does not support FOR UPDATE).
    """
    bind = db.get_bind()
    if bind is not None and bind.dialect.name == "postgresql":
        db.execute(select(Meetup.id).where(Meetup.id == meetup_id).with_for_update())


def _membership_read(row: MeetupMembership) -> MembershipRead:
    """One guest-list row (display name for management; nothing private)."""
    return MembershipRead(
        user_id=row.user_id,
        display_name=row.user.display_name,
        status=row.status,
        decided_at=row.decided_at,
    )


def _require_host(event: Meetup, me: UUID) -> None:
    """404 unless the caller hosts this event (host powers are never
    distinguishable from 'no such event' for outsiders)."""
    if event.host_id != me:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found.",
        )


def _participant_or_host(db, event: Meetup, me: UUID) -> bool:
    """Whether the caller may read participant-gated content."""
    return event.host_id == me or event_svc.is_approved(db, event.id, me)


@router.post(
    "",
    response_model=MeetupRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a public meetup (verified users only)",
)
def create_meetup(body: MeetupCreate, current_user: SocialUser, db: DbSession) -> MeetupRead:
    """Host a new public meetup (kind is always `meetup` here; house
    parties are created via POST /parties, which forces the private
    invitation-only shape server-side)."""
    check_rate_limit(
        f"meetup-create:{current_user.id}",
        limit=_CREATE_LIMIT_PER_HOUR,
        window_seconds=3600,
    )
    event = Meetup(
        host_id=current_user.id,
        kind=MeetupKind.MEETUP,
        title=body.title,
        description=body.description,
        category=body.category,
        start_at=body.start_at,
        end_at=body.end_at,
        timezone=body.timezone,
        capacity=body.capacity,
        visibility=body.visibility,
        participation=body.participation,
        location_text=body.location_text,
        venue_details=body.venue_details,
        status=MeetupStatus.ACTIVE,
    )
    db.add(event)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Could not save the meetup.",
        ) from exc
    db.refresh(event)
    event = event_svc.load_event(db, event.id)
    return MeetupRead.model_validate(event_svc.to_meetup_read(db, event, current_user))


@router.get(
    "",
    response_model=list[MeetupRead],
    summary="Discover public meetups (upcoming, filterable)",
)
def discover_meetups(
    current_user: SocialUser,
    db: DbSession,
    category: Annotated[
        MeetupCategory | None, Query(description="Only this activity category.")
    ] = None,
    start_from: Annotated[
        str | None, Query(description="Only events starting at/after this ISO datetime.")
    ] = None,
    start_to: Annotated[
        str | None, Query(description="Only events starting at/before this ISO datetime.")
    ] = None,
    available_only: Annotated[bool, Query(description="Only events with free capacity.")] = False,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[MeetupRead]:
    """Public, active, upcoming MEETUPS only: house parties and private
    events never appear here (kind-filtered in SQL, not in Python), and
    neither do events hosted by blocked users (either direction) or
    events that already ended (read-time expiry)."""

    def _aware(value: str | None, name: str):
        if value is None:
            return None
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"{name} must be an ISO 8601 datetime.",
            ) from None
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"{name} must carry a timezone (ISO 8601 with Z/offset).",
            )
        return parsed

    conds = [
        Meetup.kind == MeetupKind.MEETUP,
        Meetup.visibility == "public",
        Meetup.status == MeetupStatus.ACTIVE,
        Meetup.end_at >= event_svc.now_utc(),
    ]
    if category is not None:
        conds.append(Meetup.category == category)
    start_from_dt = _aware(start_from, "start_from")
    if start_from_dt is not None:
        conds.append(Meetup.start_at >= start_from_dt)
    start_to_dt = _aware(start_to, "start_to")
    if start_to_dt is not None:
        conds.append(Meetup.start_at <= start_to_dt)
    blocked_hosts = blocked_user_ids(db, current_user.id)
    if blocked_hosts:
        conds.append(Meetup.host_id.not_in(blocked_hosts))

    stmt = (
        select(Meetup)
        .options(joinedload(Meetup.host))
        .where(*conds)
        .order_by(Meetup.start_at.asc(), Meetup.id.asc())
        .offset(offset)
        .limit(limit if not available_only else min(limit * 5, 500))
    )
    rows = db.scalars(stmt).unique().all()
    results = []
    for event in rows:
        if available_only and event_svc.approved_count(db, event.id) >= (event.capacity or 0):
            continue
        results.append(MeetupRead.model_validate(event_svc.to_meetup_read(db, event, current_user)))
        if len(results) >= limit:
            break
    return results


@router.get(
    "/{meetup_id}",
    response_model=MeetupRead,
    summary="Read one public meetup",
)
def get_meetup(meetup_id: UUID, current_user: SocialUser, db: DbSession) -> MeetupRead:
    """One public meetup (404 for missing rows, private events, house
    parties, blocked hosts, and outsiders of ended events alike)."""
    event = event_svc.load_event(db, meetup_id)
    if event.kind != MeetupKind.MEETUP:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found.",
        )
    event_svc.refuse_if_blocked_with_host(db, current_user.id, event.host_id)
    if not event_svc.can_see_event(db, event, current_user):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found.",
        )
    return MeetupRead.model_validate(event_svc.to_meetup_read(db, event, current_user))


@router.patch(
    "/{meetup_id}",
    response_model=MeetupRead,
    summary="Edit my meetup (host only)",
)
def patch_meetup(
    meetup_id: UUID, body: MeetupPatch, current_user: SocialUser, db: DbSession
) -> MeetupRead:
    """Host edits title/description/category/times/capacity/visibility/
    participation/location. Cancelled/completed events are frozen (409);
    capacity cannot drop below the approved headcount; date edits are
    re-validated together against stored values (the Phase 7 plan
    convention). Kind is immutable."""
    event = event_svc.load_event(db, meetup_id)
    _require_host(event, current_user.id)
    if event.kind != MeetupKind.MEETUP:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found.",
        )
    event_svc.require_active(event)

    data = body.model_dump(exclude_unset=True)
    start = data.get("start_at", event.start_at)
    end = data.get("end_at", event.end_at)
    if end <= start:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="end_at must be after start_at.",
        )
    if "capacity" in data:
        approved = event_svc.approved_count(db, event.id)
        if data["capacity"] < approved:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Capacity cannot drop below the {approved} approved participant(s).",
            )
    for field, value in data.items():
        setattr(event, field, value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Could not save the meetup.",
        ) from exc
    db.refresh(event)
    return MeetupRead.model_validate(event_svc.to_meetup_read(db, event, current_user))


@router.post(
    "/{meetup_id}/cancel",
    response_model=MeetupRead,
    summary="Cancel my meetup (host only; approved members are notified)",
)
def cancel_meetup(meetup_id: UUID, current_user: SocialUser, db: DbSession) -> MeetupRead:
    """Host cancels an active meetup -> `cancelled` + server timestamp
    (terminal). Every approved participant gets an in-app notification
    (the only channel that exists - honestly `delivered` in-app)."""
    event = event_svc.load_event(db, meetup_id)
    _require_host(event, current_user.id)
    if event.kind != MeetupKind.MEETUP:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found.",
        )
    event_svc.require_active(event)
    event.status = MeetupStatus.CANCELLED
    event.cancelled_at = datetime.now(UTC)
    db.commit()
    member_ids = db.scalars(
        select(MeetupMembership.user_id).where(
            MeetupMembership.meetup_id == event.id,
            MeetupMembership.status == MembershipStatus.APPROVED,
        )
    ).all()
    for member_id in member_ids:
        record_notification(
            db,
            user_id=member_id,
            kind="event_cancelled",
            title=f"Cancelled: {event.title}",
            body=f"The host cancelled '{event.title}'.",
            idempotency_key=f"event-cancel:{event.id}:{member_id}",
        )
    db.refresh(event)
    return MeetupRead.model_validate(event_svc.to_meetup_read(db, event, current_user))


@router.post(
    "/{meetup_id}/complete",
    response_model=MeetupRead,
    summary="Mark my meetup completed (host only)",
)
def complete_meetup(meetup_id: UUID, current_user: SocialUser, db: DbSession) -> MeetupRead:
    """Host marks an active meetup `completed` (terminal; history stays
    readable to insiders)."""
    event = event_svc.load_event(db, meetup_id)
    _require_host(event, current_user.id)
    if event.kind != MeetupKind.MEETUP:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found.",
        )
    event_svc.require_active(event)
    event.status = MeetupStatus.COMPLETED
    db.commit()
    db.refresh(event)
    return MeetupRead.model_validate(event_svc.to_meetup_read(db, event, current_user))


@router.post(
    "/{meetup_id}/join",
    response_model=MembershipRead,
    status_code=status.HTTP_201_CREATED,
    summary="Join a meetup (open approves at once; approval asks first)",
)
def join_meetup(meetup_id: UUID, current_user: SocialUser, db: DbSession) -> MembershipRead:
    """Join under the event's policy: `open` creates an approved
    membership (capacity-checked, overbooking refused with 409);
    `approval` creates a `requested` row for the host. Duplicate active
    asks/memberships are 409; declined/removed/left rows reopen by an
    explicit new join (never silently). Ended/cancelled/completed events
    refuse (409); blocked hosts collapse to 404; hosts cannot join
    their own event (422)."""
    check_rate_limit(
        f"meetup-join:{current_user.id}",
        limit=_JOIN_LIMIT_PER_HOUR,
        window_seconds=3600,
    )
    event = event_svc.load_event(db, meetup_id)
    if event.kind != MeetupKind.MEETUP:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found.",
        )
    if event.host_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Hosts cannot join their own event.",
        )
    event_svc.refuse_if_blocked_with_host(db, current_user.id, event.host_id)
    if event.visibility != "public" or not event_svc.can_see_event(db, event, current_user):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found.",
        )
    event_svc.require_active(event)
    event_svc.require_not_ended(event)

    _lock_event_row(db, event.id)
    existing = db.scalar(
        select(MeetupMembership).where(
            MeetupMembership.meetup_id == event.id,
            MeetupMembership.user_id == current_user.id,
        )
    )
    if existing is not None and existing.status in (
        MembershipStatus.APPROVED,
        MembershipStatus.REQUESTED,
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You already have an active membership or pending request for this event.",
        )
    target = (
        MembershipStatus.APPROVED if event.participation == "open" else MembershipStatus.REQUESTED
    )
    if target == MembershipStatus.APPROVED and event_svc.approved_count(db, event.id) >= (
        event.capacity or 0
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This event is full.",
        )
    if existing is None:
        row = MeetupMembership(meetup_id=event.id, user_id=current_user.id, status=target)
        db.add(row)
    else:
        existing.status = target
        existing.decided_at = None
        existing.decided_by = None
        row = existing
    try:
        db.commit()
    except IntegrityError as exc:
        # Racing duplicate joins: the UNIQUE pair index kept exactly one.
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You already have an active membership or pending request for this event.",
        ) from exc
    db.refresh(row)
    row = db.scalar(
        select(MeetupMembership)
        .options(joinedload(MeetupMembership.user))
        .where(MeetupMembership.id == row.id)
    )
    return _membership_read(row)


@router.get(
    "/{meetup_id}/participants",
    response_model=list[MembershipRead],
    summary="Guest list (host sees all states; members see approved)",
)
def list_participants(
    meetup_id: UUID, current_user: SocialUser, db: DbSession
) -> list[MembershipRead]:
    """Host sees every membership state (to manage asks); approved
    members see approved participants only. Everyone else 404s -
    guest lists are insider content, like conversation history."""
    event = event_svc.load_event(db, meetup_id)
    if event.kind != MeetupKind.MEETUP:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found.",
        )
    is_host = event.host_id == current_user.id
    if not is_host and not event_svc.is_approved(db, event.id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found.",
        )
    conds = [MeetupMembership.meetup_id == event.id]
    if not is_host:
        conds.append(MeetupMembership.status == MembershipStatus.APPROVED)
    rows = (
        db.scalars(
            select(MeetupMembership)
            .options(joinedload(MeetupMembership.user))
            .where(*conds)
            .order_by(MeetupMembership.created_at.asc(), MeetupMembership.id.asc())
        )
        .unique()
        .all()
    )
    return [_membership_read(r) for r in rows]


@router.post(
    "/{meetup_id}/requests/{user_id}/approve",
    response_model=MembershipRead,
    summary="Approve a join request (host only)",
)
def approve_join_request(
    meetup_id: UUID, user_id: UUID, current_user: SocialUser, db: DbSession
) -> MembershipRead:
    """Host moves `requested` -> `approved` (capacity rechecked under a
    row lock, so concurrent approvals cannot overbook). The member gets
    an in-app notification of the decision."""
    return _decide_join_request(db, meetup_id, user_id, current_user, approve=True)


@router.post(
    "/{meetup_id}/requests/{user_id}/reject",
    response_model=MembershipRead,
    summary="Decline a join request (host only)",
)
def reject_join_request(
    meetup_id: UUID, user_id: UUID, current_user: SocialUser, db: DbSession
) -> MembershipRead:
    """Host moves `requested` -> `declined` (terminal for this ask; the
    user may ask again explicitly). The member is notified."""
    return _decide_join_request(db, meetup_id, user_id, current_user, approve=False)


def _decide_join_request(
    db, meetup_id: UUID, user_id: UUID, current_user: User, *, approve: bool
) -> MembershipRead:
    """Shared approve/reject: host-only, requested-only, capacity-safe."""
    event = event_svc.load_event(db, meetup_id)
    _require_host(event, current_user.id)
    if event.kind != MeetupKind.MEETUP:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found.",
        )
    event_svc.require_active(event)
    _lock_event_row(db, event.id)
    row = db.scalar(
        select(MeetupMembership)
        .options(joinedload(MeetupMembership.user))
        .where(
            MeetupMembership.meetup_id == event.id,
            MeetupMembership.user_id == user_id,
        )
    )
    if row is None or row.status != MembershipStatus.REQUESTED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="There is no pending join request from this user.",
        )
    if approve and event_svc.approved_count(db, event.id) >= (event.capacity or 0):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This event is full.",
        )
    row.status = MembershipStatus.APPROVED if approve else MembershipStatus.DECLINED
    row.decided_at = datetime.now(UTC)
    row.decided_by = current_user.id
    db.commit()
    record_notification(
        db,
        user_id=user_id,
        kind="join_decision",
        title=f"{'Approved' if approve else 'Declined'}: {event.title}",
        body=(
            f"The host {'approved' if approve else 'declined'} your request "
            f"to join '{event.title}'."
        ),
        idempotency_key=f"join-decision:{row.id}:{row.status}",
    )
    db.refresh(row)
    return _membership_read(row)


@router.post(
    "/{meetup_id}/leave",
    response_model=MembershipRead,
    summary="Leave an event I participate in",
)
def leave_meetup(meetup_id: UUID, current_user: SocialUser, db: DbSession) -> MembershipRead:
    """Approved member leaves -> `left` (rejoin allowed later as a fresh
    ask). Hosts cannot leave their own event (cancel it instead)."""
    event = event_svc.load_event(db, meetup_id)
    if event.kind != MeetupKind.MEETUP:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found.",
        )
    if event.host_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Hosts cannot leave their own event - cancel it instead.",
        )
    row = db.scalar(
        select(MeetupMembership)
        .options(joinedload(MeetupMembership.user))
        .where(
            MeetupMembership.meetup_id == event.id,
            MeetupMembership.user_id == current_user.id,
        )
    )
    if row is None or row.status != MembershipStatus.APPROVED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You are not an approved participant of this event.",
        )
    row.status = MembershipStatus.LEFT
    row.decided_at = datetime.now(UTC)
    db.commit()
    db.refresh(row)
    return _membership_read(row)


@router.delete(
    "/{meetup_id}/participants/{user_id}",
    response_model=MembershipRead,
    summary="Remove a participant (host only)",
)
def remove_participant(
    meetup_id: UUID, user_id: UUID, current_user: SocialUser, db: DbSession
) -> MembershipRead:
    """Host removes an approved participant -> `removed` (they may ask
    again later). The host cannot remove themselves."""
    event = event_svc.load_event(db, meetup_id)
    _require_host(event, current_user.id)
    if event.kind != MeetupKind.MEETUP:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found.",
        )
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Hosts cannot remove themselves - cancel the event instead.",
        )
    row = db.scalar(
        select(MeetupMembership)
        .options(joinedload(MeetupMembership.user))
        .where(
            MeetupMembership.meetup_id == event.id,
            MeetupMembership.user_id == user_id,
        )
    )
    if row is None or row.status != MembershipStatus.APPROVED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That user is not an approved participant of this event.",
        )
    row.status = MembershipStatus.REMOVED
    row.decided_at = datetime.now(UTC)
    row.decided_by = current_user.id
    db.commit()
    db.refresh(row)
    return _membership_read(row)


@router.post(
    "/{meetup_id}/announcements",
    response_model=AnnouncementRead,
    status_code=status.HTTP_201_CREATED,
    summary="Post a host bulletin (host only, active events)",
)
def post_announcement(
    meetup_id: UUID, body: AnnouncementCreate, current_user: SocialUser, db: DbSession
) -> AnnouncementRead:
    """Host-only one-way bulletin (no replies - group chat is out of
    scope by design). Frozen with cancelled/completed events."""
    event = event_svc.load_event(db, meetup_id)
    _require_host(event, current_user.id)
    if event.kind != MeetupKind.MEETUP:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found.",
        )
    event_svc.require_active(event)
    row = MeetupAnnouncement(meetup_id=event.id, author_id=current_user.id, body=body.body)
    db.add(row)
    db.commit()
    db.refresh(row)
    return AnnouncementRead(
        id=row.id,
        meetup_id=event.id,
        author_display_name=current_user.display_name,
        body=row.body,
        created_at=row.created_at,
    )


@router.get(
    "/{meetup_id}/announcements",
    response_model=list[AnnouncementRead],
    summary="Read event bulletins (host + approved participants)",
)
def list_announcements(
    meetup_id: UUID, current_user: SocialUser, db: DbSession
) -> list[AnnouncementRead]:
    """Bulletins are insider content: host + approved participants only
    (requested users wait for approval first)."""
    event = event_svc.load_event(db, meetup_id)
    if event.kind != MeetupKind.MEETUP:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found.",
        )
    if not _participant_or_host(db, event, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found.",
        )
    rows = (
        db.scalars(
            select(MeetupAnnouncement)
            .options(joinedload(MeetupAnnouncement.author))
            .where(MeetupAnnouncement.meetup_id == event.id)
            .order_by(MeetupAnnouncement.created_at.asc(), MeetupAnnouncement.id.asc())
        )
        .unique()
        .all()
    )
    return [
        AnnouncementRead(
            id=r.id,
            meetup_id=event.id,
            author_display_name=r.author.display_name,
            body=r.body,
            created_at=r.created_at,
        )
        for r in rows
    ]


def _participant_or_host(db, event: Meetup, me: UUID) -> bool:
    """Whether the caller may read participant-gated content."""
    return event.host_id == me or event_svc.is_approved(db, event.id, me)
