"""Shared meetup/house-party helpers: loading, authorization, serialization (Phases 9-10).

Plain language: both endpoint modules (`meetups.py`, `parties.py`) work
on the SAME table, so the rules live here once: who may SEE an event,
who may see its EXACT venue, how the public read shape is built, and
the capacity/ended guards. The venue rule is the privacy heart of Phase
10: `venue_details` is populated ONLY for the host and approved
participants of private events - EVERYWHERE else the field is None by
construction (the serializer takes an explicit flag; there is no code
path that serves the raw row).
"""

from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.core.blocks import blocked_user_ids
from app.models.enums import MeetupKind, MeetupStatus, MembershipStatus
from app.models.meetup import Meetup
from app.models.meetup_membership import MeetupMembership
from app.models.user import User


def now_utc() -> datetime:
    """Server clock (aware UTC) for lifecycle comparisons and stamps."""
    return datetime.now(UTC)


def approved_count(db: Session, meetup_id: UUID) -> int:
    """Number of approved participants (host excluded; capacity counts
    guests, not the host who is always present)."""
    return (
        db.scalar(
            select(func.count())
            .select_from(MeetupMembership)
            .where(
                MeetupMembership.meetup_id == meetup_id,
                MeetupMembership.status == MembershipStatus.APPROVED,
            )
        )
        or 0
    )


def my_membership_status(db: Session, meetup_id: UUID, user_id: UUID) -> str:
    """The caller's own membership state, or 'none' (never 404s)."""
    row = db.scalar(
        select(MeetupMembership).where(
            MeetupMembership.meetup_id == meetup_id,
            MeetupMembership.user_id == user_id,
        )
    )
    return row.status if row is not None else "none"


def is_approved(db: Session, meetup_id: UUID, user_id: UUID) -> bool:
    """Whether the user is an approved participant (host handled apart)."""
    return (
        db.scalar(
            select(MeetupMembership.id).where(
                MeetupMembership.meetup_id == meetup_id,
                MeetupMembership.user_id == user_id,
                MeetupMembership.status == MembershipStatus.APPROVED,
            )
        )
        is not None
    )


def load_event(db: Session, meetup_id: UUID) -> Meetup:
    """Fetch an event with its host, or privacy-404 (never 404-vs-known)."""
    row = db.scalar(select(Meetup).options(joinedload(Meetup.host)).where(Meetup.id == meetup_id))
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found.",
        )
    return row


def can_see_event(db: Session, event: Meetup, user: User) -> bool:
    """Visibility rule shared by every read path.

    - active public MEETUPS: anyone (social gate already passed).
    - private meetups / ALL house parties: host, approved participants,
      and pending invitees/requesters only (they were explicitly let
      in). Everyone else gets the identical 404 - private events cannot
      be enumerated by guessing ids.
    - cancelled/completed events: host + approved participants only
      (history stays readable to insiders; outsiders see 404).
    """
    if user.id == event.host_id:
        return True
    if event.status != MeetupStatus.ACTIVE:
        return is_approved(db, event.id, user.id)
    if event.kind == MeetupKind.MEETUP and event.visibility == "public":
        return True
    if is_approved(db, event.id, user.id):
        return True
    # Pending invitees/requesters were explicitly let in far enough to
    # read the listing (but never the venue - see can_see_venue).
    pending = db.scalar(
        select(MeetupMembership.id).where(
            MeetupMembership.meetup_id == event.id,
            MeetupMembership.user_id == user.id,
            MeetupMembership.status == MembershipStatus.REQUESTED,
        )
    )
    if pending is not None:
        return True
    from app.models.enums import InvitationStatus
    from app.models.event_invitation import EventInvitation

    invited = db.scalar(
        select(EventInvitation.id).where(
            EventInvitation.meetup_id == event.id,
            EventInvitation.invitee_id == user.id,
            EventInvitation.status == InvitationStatus.PENDING,
        )
    )
    return invited is not None


def can_see_venue(db: Session, event: Meetup, user: User) -> bool:
    """Exact-venue rule: host + approved participants of PRIVATE events.

    Public meetups meet at public places (`location_text` carries that);
    their `venue_details`, if the host set any, follows the same strict
    rule - exact addresses are never public, no exceptions.
    """
    if user.id == event.host_id:
        return True
    return is_approved(db, event.id, user.id)


def require_active(event: Meetup) -> None:
    """409 unless the event is active (cancelled/completed freeze joins,
    invites, announcements, and edits)."""
    if event.status != MeetupStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"This event is '{event.status}' and no longer accepts changes.",
        )


def require_not_ended(event: Meetup) -> None:
    """409 when the event's end time has passed (read-time expiry - no
    background job rewrites rows; the host completes explicitly)."""
    end = event.end_at
    if end.tzinfo is None:
        end = end.replace(tzinfo=UTC)
    if end <= now_utc():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This event has ended and no longer accepts joins or invitations.",
        )


def refuse_if_blocked_with_host(db: Session, me: UUID, host_id: UUID) -> None:
    """404-collapse when a block stands between the caller and the host
    (blocks must never leak through event errors, brief item 10)."""
    if host_id in blocked_user_ids(db, me):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found.",
        )


def to_meetup_read(db: Session, event: Meetup, user: User) -> dict:
    """Build the MeetupRead payload with venue gating applied.

    Returns a plain dict for the response model (keeps the endpoint
    thin and the rule in one place).
    """
    show_venue = can_see_venue(db, event, user)
    return {
        "id": event.id,
        "host_id": event.host_id,
        "host_display_name": event.host.display_name,
        "kind": event.kind,
        "title": event.title,
        "description": event.description,
        "category": event.category,
        "start_at": event.start_at,
        "end_at": event.end_at,
        "timezone": event.timezone,
        "capacity": event.capacity,
        "approved_count": approved_count(db, event.id),
        "visibility": event.visibility,
        "participation": event.participation,
        "status": event.status,
        "location_text": event.location_text,
        "venue_details": event.venue_details if show_venue else None,
        "my_membership": (
            "host" if user.id == event.host_id else my_membership_status(db, event.id, user.id)
        ),
        "created_at": event.created_at,
        "updated_at": event.updated_at,
    }
