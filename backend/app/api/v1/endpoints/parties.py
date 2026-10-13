"""Private house-party endpoints (Phase 10, invitation-only).

Plain language: parties share the meetup TABLE and lifecycle (one
foundation - kind `house_party`), but the access rules are a different,
stricter world: nothing is publicly discoverable, joining happens ONLY
through a host invitation the invitee accepts, and the exact venue is
visible ONLY to the host and approved participants.

Privacy rules enforced here (brief item 10):
- POST /parties forces kind=house_party + visibility=private
  server-side (the client cannot opt a party into being public).
- GET /parties/{id} 404s for everyone except host / approved /
  pending-invited users - private events cannot be enumerated by
  guessing ids, and they never appear in meetup discovery, public
  profiles, or general search.
- `venue_details` follows the shared `can_see_venue` rule (host +
  approved only); pending invitees see everything EXCEPT the venue, so
  they can decide on the invitation without learning the address.
- Invites check recipient eligibility (exists + verified-if-policy) and
  blocks (either direction) with the same 404-collapse as travel/chat
  requests; the host cannot invite themselves (422); duplicate pending
  invites are 409 (UNIQUE pair + pre-check).
"""

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

from app.api.v1.deps import DbSession, SocialUser
from app.api.v1.endpoints.meetups import (
    _lock_event_row,
    _membership_read,
    _require_host,
)
from app.api.v1.schemas.meetup import (
    InvitationCreate,
    InvitationList,
    InvitationRead,
    MeetupCreate,
    MeetupPatch,
    MeetupRead,
    MembershipRead,
)
from app.core.blocks import blocked_user_ids
from app.core.policy import get_policy
from app.core.rate_limit import check_rate_limit
from app.models.enums import InvitationStatus, MeetupKind, MeetupStatus, MembershipStatus
from app.models.event_invitation import EventInvitation
from app.models.meetup import Meetup
from app.models.meetup_membership import MeetupMembership
from app.models.user import User
from app.services import events as event_svc
from app.services.billing import (
    PaymentRequiredError,
    authorize_post,
    consume_payment,
    raise_payment_required,
)
from app.services.notifications import record_notification

router = APIRouter(prefix="/parties", tags=["house-parties"])
invitations_router = APIRouter(prefix="/invitations", tags=["house-parties"])

# Shared abuse-control bucket with meetup creation (one host, one limit
# for both event families).
_CREATE_LIMIT_PER_HOUR = 20


def _invitation_read(db, row: EventInvitation) -> InvitationRead:
    """One invitation with event + invitee names resolved."""
    return InvitationRead(
        id=row.id,
        meetup_id=row.meetup_id,
        event_title=row.meetup.title,
        inviter_id=row.inviter_id,
        invitee_id=row.invitee_id,
        invitee_display_name=row.invitee.display_name,
        status=row.status,
        responded_at=row.responded_at,
        created_at=row.created_at,
    )


def _load_party(db, party_id: UUID) -> Meetup:
    """Fetch a HOUSE PARTY row (404 for missing rows AND for meetups -
    the two surfaces never cross: party ids work here, meetup ids do
    not, and vice versa)."""
    event = event_svc.load_event(db, party_id)
    if event.kind != MeetupKind.HOUSE_PARTY:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found.",
        )
    return event


@router.post(
    "",
    response_model=MeetupRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a private house party (invitation-only)",
)
def create_party(body: MeetupCreate, current_user: SocialUser, db: DbSession) -> MeetupRead:
    """Host a new house party. Kind and visibility are FORCED
    server-side (house_party + private) no matter what the body says -
    a party can never be created public, and can never be patched public
    later. Give at most an AREA in `location_text`; the exact address
    goes in `venue_details` (visible to host + approved only)."""
    check_rate_limit(
        f"meetup-create:{current_user.id}",
        limit=_CREATE_LIMIT_PER_HOUR,
        window_seconds=3600,
    )
    # Phase 14 pay-per-post gate (category house_party): same rule as
    # meetups - free grant, verified payment, or 402 with the charge.
    try:
        funding = authorize_post(
            db,
            user=current_user,
            category="house_party",
            payment_id=body.payment_id,
            idempotency_key=body.idempotency_key,
        )
    except PaymentRequiredError as exc:
        # Persist ONLY the PENDING payment row (the flush added nothing
        # else at this point); the party itself is never created here.
        db.commit()
        raise_payment_required(exc)

    event = Meetup(
        host_id=current_user.id,
        kind=MeetupKind.HOUSE_PARTY,
        title=body.title,
        description=body.description,
        category=body.category,
        start_at=body.start_at,
        end_at=body.end_at,
        timezone=body.timezone,
        capacity=body.capacity,
        visibility="private",
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
            detail="Could not save the house party.",
        ) from exc
    db.refresh(event)
    event = event_svc.load_event(db, event.id)
    # Link the funding (free grant or paid payment) to THIS party,
    # exactly once.
    consume_payment(db, payment=funding, subject_type="meetup", subject_id=event.id)
    db.commit()
    return MeetupRead.model_validate(event_svc.to_meetup_read(db, event, current_user))


@router.get(
    "/{party_id}",
    response_model=MeetupRead,
    summary="Read one house party I am entitled to see",
)
def get_party(party_id: UUID, current_user: SocialUser, db: DbSession) -> MeetupRead:
    """Host, approved participants, and pending invitees may read (the
    last group WITHOUT the venue - they decide first, learn the address
    after accepting). Everyone else gets the identical 404."""
    event = _load_party(db, party_id)
    event_svc.refuse_if_blocked_with_host(db, current_user.id, event.host_id)
    if not event_svc.can_see_event(db, event, current_user):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found.",
        )
    return MeetupRead.model_validate(event_svc.to_meetup_read(db, event, current_user))


@router.patch(
    "/{party_id}",
    response_model=MeetupRead,
    summary="Edit my house party (host only)",
)
def patch_party(
    party_id: UUID, body: MeetupPatch, current_user: SocialUser, db: DbSession
) -> MeetupRead:
    """Host edits (same rules as meetups: frozen when not active,
    capacity floor = approved headcount, dates re-validated together).
    Kind and visibility are immutable - a party stays private forever."""
    event = _load_party(db, party_id)
    _require_host(event, current_user.id)
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
    # Belt-and-braces: even a crafted direct call cannot flip these.
    event.kind = MeetupKind.HOUSE_PARTY
    event.visibility = "private"
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Could not save the house party.",
        ) from exc
    db.refresh(event)
    return MeetupRead.model_validate(event_svc.to_meetup_read(db, event, current_user))


@router.post(
    "/{party_id}/cancel",
    response_model=MeetupRead,
    summary="Cancel my house party (host only)",
)
def cancel_party(party_id: UUID, current_user: SocialUser, db: DbSession) -> MeetupRead:
    """Host cancels -> `cancelled` (terminal). Approved participants are
    notified in-app."""
    event = _load_party(db, party_id)
    _require_host(event, current_user.id)
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
    "/{party_id}/complete",
    response_model=MeetupRead,
    summary="Mark my house party completed (host only)",
)
def complete_party(party_id: UUID, current_user: SocialUser, db: DbSession) -> MeetupRead:
    """Host marks an active party `completed` (terminal)."""
    event = _load_party(db, party_id)
    _require_host(event, current_user.id)
    event_svc.require_active(event)
    event.status = MeetupStatus.COMPLETED
    db.commit()
    db.refresh(event)
    return MeetupRead.model_validate(event_svc.to_meetup_read(db, event, current_user))


@router.post(
    "/{party_id}/invite",
    response_model=InvitationRead,
    status_code=status.HTTP_201_CREATED,
    summary="Invite a user to my house party (host only)",
)
def invite_to_party(
    party_id: UUID, body: InvitationCreate, current_user: SocialUser, db: DbSession
) -> InvitationRead:
    """Host invites one eligible user. Eligibility (exists +
    verified-if-policy + unblocked either direction) collapses to one
    404; self-invites are 422; a pending invite is 409. A declined /
    revoked / expired invite is REOPENED to pending by an explicit new
    invite (same row - invitation replay of an old accept is impossible
    because accepts only move pending rows). The invitee is notified
    in-app."""
    event = _load_party(db, party_id)
    _require_host(event, current_user.id)
    event_svc.require_active(event)
    event_svc.require_not_ended(event)

    if body.invitee_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Hosts cannot invite themselves.",
        )
    requires_verification = get_policy(db)
    invitee = db.scalar(select(User).where(User.id == body.invitee_id))
    if invitee is None or (requires_verification and invitee.verification_status != "verified"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )
    if body.invitee_id in blocked_user_ids(db, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    existing = db.scalar(
        select(EventInvitation)
        .options(
            joinedload(EventInvitation.meetup),
            joinedload(EventInvitation.invitee),
        )
        .where(
            EventInvitation.meetup_id == event.id,
            EventInvitation.invitee_id == body.invitee_id,
        )
    )
    if existing is not None:
        if existing.status == InvitationStatus.PENDING:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="That user already has a pending invitation to this party.",
            )
        existing.status = InvitationStatus.PENDING
        existing.inviter_id = current_user.id
        existing.responded_at = None
        db.commit()
        db.refresh(existing)
        row = existing
    else:
        row = EventInvitation(
            meetup_id=event.id,
            inviter_id=current_user.id,
            invitee_id=body.invitee_id,
            status=InvitationStatus.PENDING,
        )
        db.add(row)
        try:
            db.commit()
        except IntegrityError as exc:
            # Racing duplicate invites: the UNIQUE pair index kept one.
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="That user already has a pending invitation to this party.",
            ) from exc
        db.refresh(row)
        row = db.scalar(
            select(EventInvitation)
            .options(
                joinedload(EventInvitation.meetup),
                joinedload(EventInvitation.invitee),
            )
            .where(EventInvitation.id == row.id)
        )
    record_notification(
        db,
        user_id=body.invitee_id,
        kind="meetup_invite",
        title=f"Invited: {event.title}",
        body=f"{current_user.display_name} invited you to '{event.title}'.",
        idempotency_key=f"meetup-invite:{row.id}:{row.status}",
    )
    return _invitation_read(db, row)


@router.delete(
    "/{party_id}/invite/{invitee_id}",
    response_model=InvitationRead,
    summary="Withdraw an invitation (host only)",
)
def revoke_invitation(
    party_id: UUID, invitee_id: UUID, current_user: SocialUser, db: DbSession
) -> InvitationRead:
    """Host withdraws a pending invitation -> `revoked` (the invitee's
    accept window closes; they may be invited again later)."""
    event = _load_party(db, party_id)
    _require_host(event, current_user.id)
    row = db.scalar(
        select(EventInvitation)
        .options(
            joinedload(EventInvitation.meetup),
            joinedload(EventInvitation.invitee),
        )
        .where(
            EventInvitation.meetup_id == event.id,
            EventInvitation.invitee_id == invitee_id,
        )
    )
    if row is None or row.status != InvitationStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="There is no pending invitation for that user.",
        )
    row.status = InvitationStatus.REVOKED
    row.responded_at = datetime.now(UTC)
    db.commit()
    db.refresh(row)
    return _invitation_read(db, row)


@router.get(
    "/{party_id}/participants",
    response_model=list[MembershipRead],
    summary="Party guest list (host sees all; members see approved)",
)
def list_party_participants(
    party_id: UUID, current_user: SocialUser, db: DbSession
) -> list[MembershipRead]:
    """Same insider rule as meetups, minus the exact venue (which never
    travels in a list): display names only, never private account data."""
    event = _load_party(db, party_id)
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
    "/{party_id}/leave",
    response_model=MembershipRead,
    summary="Leave a party I participate in",
)
def leave_party(party_id: UUID, current_user: SocialUser, db: DbSession) -> MembershipRead:
    """Approved participant leaves -> `left`. Hosts cancel instead."""
    event = _load_party(db, party_id)
    if event.host_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Hosts cannot leave their own party - cancel it instead.",
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
            detail="You are not an approved participant of this party.",
        )
    row.status = MembershipStatus.LEFT
    row.decided_at = datetime.now(UTC)
    db.commit()
    db.refresh(row)
    return _membership_read(row)


@invitations_router.get(
    "",
    response_model=InvitationList,
    summary="My incoming party invitations (newest first)",
)
def list_my_invitations(
    current_user: SocialUser,
    db: DbSession,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> InvitationList:
    """Invitations addressed to ME (any status; pending ones are
    actionable). Nobody else's invitations are reachable here."""
    conds = [EventInvitation.invitee_id == current_user.id]
    total = db.scalar(select(func.count()).select_from(EventInvitation).where(*conds)) or 0
    rows = (
        db.scalars(
            select(EventInvitation)
            .options(
                joinedload(EventInvitation.meetup),
                joinedload(EventInvitation.invitee),
            )
            .where(*conds)
            .order_by(EventInvitation.created_at.desc(), EventInvitation.id.desc())
            .offset(offset)
            .limit(limit)
        )
        .unique()
        .all()
    )
    return InvitationList(
        total=total,
        offset=offset,
        limit=limit,
        results=[_invitation_read(db, r) for r in rows],
    )


@invitations_router.post(
    "/{invitation_id}/accept",
    response_model=InvitationRead,
    summary="Accept a party invitation (invitee only)",
)
def accept_invitation(
    invitation_id: UUID, current_user: SocialUser, db: DbSession
) -> InvitationRead:
    """Invitee accepts a pending invitation -> `accepted` AND an approved
    membership in one transaction (the invitation IS the host's vetting;
    capacity rechecked under the event row lock). Refused when the party
    ended/was cancelled, when full (409, invite stays pending), or when
    a block stands (409 - accepts never bypass blocks)."""
    return _answer_invitation(db, invitation_id, current_user, accept=True)


@invitations_router.post(
    "/{invitation_id}/decline",
    response_model=InvitationRead,
    summary="Decline a party invitation (invitee only)",
)
def decline_invitation(
    invitation_id: UUID, current_user: SocialUser, db: DbSession
) -> InvitationRead:
    """Invitee declines -> `declined` (the host may invite again later)."""
    return _answer_invitation(db, invitation_id, current_user, accept=False)


def _answer_invitation(
    db, invitation_id: UUID, current_user: User, *, accept: bool
) -> InvitationRead:
    """Shared accept/decline: invitee-only, pending-only, event-live."""
    row = db.scalar(
        select(EventInvitation)
        .options(
            joinedload(EventInvitation.meetup).joinedload(Meetup.host),
            joinedload(EventInvitation.invitee),
        )
        .where(EventInvitation.id == invitation_id)
    )
    if row is None or row.invitee_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invitation not found.",
        )
    if row.status != InvitationStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Only pending invitations can be answered (current: '{row.status}').",
        )
    event = row.meetup
    event_svc.require_active(event)
    event_svc.require_not_ended(event)
    if row.invitee_id in blocked_user_ids(db, event.host_id) or event.host_id in blocked_user_ids(
        db, row.invitee_id
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This invitation can no longer be accepted while the pair is blocked.",
        )
    if not accept:
        row.status = InvitationStatus.DECLINED
        row.responded_at = datetime.now(UTC)
        db.commit()
        db.refresh(row)
        return _invitation_read(db, row)

    _lock_event_row(db, event.id)
    if event_svc.approved_count(db, event.id) >= (event.capacity or 0):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This party is full - your invitation stays pending.",
        )
    membership = db.scalar(
        select(MeetupMembership).where(
            MeetupMembership.meetup_id == event.id,
            MeetupMembership.user_id == current_user.id,
        )
    )
    if membership is None:
        membership = MeetupMembership(
            meetup_id=event.id, user_id=current_user.id, status=MembershipStatus.APPROVED
        )
        db.add(membership)
    else:
        membership.status = MembershipStatus.APPROVED
        membership.decided_at = datetime.now(UTC)
        membership.decided_by = event.host_id
    row.status = InvitationStatus.ACCEPTED
    row.responded_at = datetime.now(UTC)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Could not accept the invitation.",
        ) from exc
    db.refresh(row)
    return _invitation_read(db, row)
