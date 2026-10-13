"""SOS incident endpoints (Phase 5).

Plain language: an SOS incident is the user's "help me" record. These
routes activate one, list the user's own, and let the owner cancel or
resolve it. The same two ideas from trusted contacts and check-ins apply
here: ownership comes only from the token, and a not-yours incident and
a nonexistent one return the identical 404.

STATUS LIFECYCLE (enforced in this module):

    active ──▶ cancelled     (POST /{sos_id}/cancel)
          └──▶ resolved      (POST /{sos_id}/resolve)

    cancelled and resolved are TERMINAL - a closed incident can never
    move again, not even back to active. Repeats and contradictions
    (resolving a cancelled incident, cancelling twice, ...) return 409.

`cancelled_at` / `resolved_at` are stamped with the SERVER clock when
the transition happens and are never taken from client data. There is
no body on the cancel/resolve routes at all, so no client-controlled
timestamp can even be expressed.

CONCURRENCY: cancel/resolve use a conditional UPDATE (compare-and-set
on `status='active'`) rather than a read-then-write, so two racing
requests can never both win - exactly one succeeds, the loser gets 409.

SAFETY BOUNDARY: this phase only WRITES A ROW. Activating an SOS does
not contact police, ambulance, emergency numbers, trusted contacts, or
nearby users; it sends nothing, calls nobody, and shares no location.
Those behaviours need real integrations and safeguards in later phases
and must never be assumed from this prototype.
"""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from app.api.v1.deps import CurrentUser, DbSession
from app.api.v1.schemas.sos_event import SosEventCreate, SosEventRead
from app.db.base_class import utc_now
from app.models.enums import SosStatus
from app.models.sos_event import SosEvent

router = APIRouter(prefix="/sos", tags=["sos"])


def _get_owned_sos(sos_id: UUID, current_user, db) -> SosEvent:
    """Load an SOS incident by ID only if it belongs to the current user.

    404 for both "not yours" and "does not exist", identically, so
    ownership cannot be probed by guessing IDs.
    """
    sos = db.scalar(
        select(SosEvent).where(
            SosEvent.id == sos_id,
            SosEvent.user_id == current_user.id,
        )
    )
    if sos is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="SOS incident not found.",
        )
    return sos


@router.post(
    "",
    response_model=SosEventRead,
    status_code=status.HTTP_201_CREATED,
    summary="Activate an SOS incident for the authenticated user",
)
def create_sos(
    body: SosEventCreate,
    current_user: CurrentUser,
    db: DbSession,
) -> SosEventRead:
    """Activate an incident, starting life in the `active` status.

    The owner is the token's user; the status is chosen by the server.
    Coordinates (if given) were already validated as a pair and in
    range by the schema, and `location_recorded_at` is stamped with the
    server's clock. Nothing is sent to anyone.
    """
    sos = SosEvent(
        user_id=current_user.id,
        status=SosStatus.ACTIVE,
        description=body.description,
        latitude=body.latitude,
        longitude=body.longitude,
        location_recorded_at=utc_now() if body.latitude is not None else None,
    )
    db.add(sos)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Could not save the SOS incident.",
        ) from exc
    db.refresh(sos)
    # Notification attempts are recorded AFTER the incident persists and
    # never gate it: an SOS is saved even when every channel is
    # unavailable (brief 12.C). One row per trusted contact, idempotent.
    _record_contact_attempts(db, sos, current_user.display_name)
    return SosEventRead.model_validate(sos)


@router.get(
    "",
    response_model=list[SosEventRead],
    summary="List the authenticated user's SOS incidents (newest first)",
)
def list_sos_events(
    current_user: CurrentUser,
    db: DbSession,
) -> list[SosEventRead]:
    """Return ONLY the caller's SOS incidents, newest first (stable order).

    Ownership is enforced in the query itself, so no listing can ever
    contain another user's incident. No pagination yet (documented
    limitation).
    """
    stmt = (
        select(SosEvent)
        .where(SosEvent.user_id == current_user.id)
        .order_by(SosEvent.created_at.desc(), SosEvent.id.desc())
    )
    events = db.scalars(stmt).all()
    return [SosEventRead.model_validate(e) for e in events]


@router.get(
    "/{sos_id}",
    response_model=SosEventRead,
    summary="Return one of the authenticated user's SOS incidents",
)
def get_sos_event(
    sos_id: UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> SosEventRead:
    """Fetch a single incident. 404 if it is missing OR not yours."""
    sos = _get_owned_sos(sos_id, current_user, db)
    return SosEventRead.model_validate(sos)


def _record_contact_attempts(db, sos, owner_display_name: str) -> list:
    """Record one notification row per trusted contact for an SOS.

    Idempotent by construction: the key sos:{sos}:contact:{contact} is
    UNIQUE, so creating twice (activation + retry) returns the SAME row
    instead of duplicating alerts. Contacts are not app users, so rows
    belong to the SOS owner's inbox (the only account entitled to see
    them) with channel sms (contacts always have a phone) and an honest
    outcome: `unavailable` until a real provider exists. Persistence of
    the SOS never waits for these rows (brief 12.C).
    """
    from app.models.trusted_contact import TrustedContact
    from app.services.notifications import record_notification

    contacts = db.scalars(select(TrustedContact).where(TrustedContact.user_id == sos.user_id)).all()
    rows = []
    for contact in contacts:
        rows.append(
            record_notification(
                db,
                user_id=sos.user_id,
                kind="sos_created",
                title=f"SOS alert: {owner_display_name}",
                body=(
                    f"SOS {sos.id} activated. Attempt to reach {contact.name} "
                    f"by SMS to {contact.phone}: no messaging provider is "
                    "configured, so nothing was sent (recorded as unavailable)."
                ),
                channel="sms",
                idempotency_key=f"sos:{sos.id}:contact:{contact.id}",
            )
        )
    return rows


@router.post(
    "/{sos_id}/cancel",
    response_model=SosEventRead,
    summary="Cancel an active SOS incident (retract it)",
)
def cancel_sos_event(
    sos_id: UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> SosEventRead:
    """Retract an `active` incident using the SERVER's clock.

    - active/acknowledged -> cancelled, `cancelled_at` = now (server clock).
    - cancelled -> 409 (already closed; the first cancellation time is
      never rewritten).
    - resolved  -> 409 (a resolved incident's story is not rewritten).

    There is no request body, so a cancellation timestamp cannot be
    supplied by the client. Nothing is notified or dispatched - this
    only writes a row.
    """
    _get_owned_sos(sos_id, current_user, db)

    # Conditional UPDATE (compare-and-set): the status check happens
    # INSIDE the statement, so a racing transition on another request
    # makes exactly one of them lose (rowcount 0 -> 409) instead of
    # both overwriting each other.
    result = db.execute(
        update(SosEvent)
        .where(
            SosEvent.id == sos_id,
            SosEvent.status.in_([SosStatus.ACTIVE, SosStatus.ACKNOWLEDGED]),
        )
        .values(
            status=SosStatus.CANCELLED,
            cancelled_at=utc_now(),  # server clock, never client data
            updated_at=utc_now(),
        )
    )
    if result.rowcount == 0:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only an active or acknowledged SOS incident can be cancelled.",
        )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Could not save the SOS incident.",
        ) from exc
    sos = _get_owned_sos(sos_id, current_user, db)
    return SosEventRead.model_validate(sos)


@router.post(
    "/{sos_id}/resolve",
    response_model=SosEventRead,
    summary="Mark an active SOS incident as resolved",
)
def resolve_sos_event(
    sos_id: UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> SosEventRead:
    """Close an incident as resolved, SERVER's clock.

    - active/acknowledged -> resolved, `resolved_at` = now (server clock).
    - resolved  -> 409 (already closed; the first resolution time is
      never rewritten).
    - cancelled -> 409 (a cancelled incident's story is not rewritten).

    There is no request body, so a resolution timestamp cannot be
    supplied by the client. Nothing is notified or dispatched - this
    only writes a row.
    """
    _get_owned_sos(sos_id, current_user, db)

    # Same compare-and-set strategy as cancel (see there).
    result = db.execute(
        update(SosEvent)
        .where(
            SosEvent.id == sos_id,
            SosEvent.status.in_([SosStatus.ACTIVE, SosStatus.ACKNOWLEDGED]),
        )
        .values(
            status=SosStatus.RESOLVED,
            resolved_at=utc_now(),  # server clock, never client data
            updated_at=utc_now(),
        )
    )
    if result.rowcount == 0:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only an active or acknowledged SOS incident can be resolved.",
        )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Could not save the SOS incident.",
        ) from exc
    sos = _get_owned_sos(sos_id, current_user, db)
    return SosEventRead.model_validate(sos)


@router.post(
    "/{sos_id}/acknowledge",
    response_model=SosEventRead,
    summary="Acknowledge an active SOS incident (owner)",
)
def acknowledge_sos_event(
    sos_id: UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> SosEventRead:
    """Mark an `active` incident `acknowledged`: someone responsible has
    seen it and is handling it. Same compare-and-set strategy as
    cancel/resolve (exactly one concurrent transition wins, loser 409).
    acknowledged -> resolved/cancelled stays allowed; nothing else moves
    out of acknowledged. Server clock, no body. This is the OWNER
    recording handling - it is not a claim that help arrived."""
    _get_owned_sos(sos_id, current_user, db)

    result = db.execute(
        update(SosEvent)
        .where(SosEvent.id == sos_id, SosEvent.status == SosStatus.ACTIVE)
        .values(
            status=SosStatus.ACKNOWLEDGED,
            acknowledged_at=utc_now(),
            updated_at=utc_now(),
        )
    )
    if result.rowcount == 0:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only an active SOS incident can be acknowledged.",
        )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Could not save the SOS incident.",
        ) from exc
    sos = _get_owned_sos(sos_id, current_user, db)
    return SosEventRead.model_validate(sos)


@router.post(
    "/{sos_id}/notify-retry",
    response_model=list[dict],
    summary="Retry contact notifications for an active SOS (owner)",
)
def retry_sos_notifications(
    sos_id: UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> list[dict]:
    """Re-attempt the SOS contact notifications IN PLACE (same rows,
    attempts + 1 - retries never duplicate alerts). Only `active`
    incidents retry (a closed incident's story is not rewritten - 409).
    Each row keeps its honest outcome (`unavailable` until a provider
    exists); the response is the attempt rows. Nothing is dispatched
    anywhere by this prototype."""
    from app.api.v1.schemas.sharing import NotificationRead
    from app.services.notifications import reattempt

    sos = _get_owned_sos(sos_id, current_user, db)
    if sos.status != SosStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only an active SOS incident can retry notifications.",
        )
    rows = _record_contact_attempts(db, sos, current_user.display_name)
    retried = []
    for row in rows:
        if row.status in ("failed", "unavailable", "unknown"):
            row = reattempt(db, row)
        retried.append(NotificationRead.model_validate(row).model_dump(mode="json"))
    return retried


@router.get(
    "/{sos_id}/notifications",
    response_model=list[dict],
    summary="List contact-notification attempts for my SOS",
)
def list_sos_notifications(
    sos_id: UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> list[dict]:
    """Every recorded contact attempt for one OWN incident (404 for
    foreign or missing ids, identically). Makes delivery outcomes
    observable: each row shows its honest status, attempts, and error."""
    from app.api.v1.schemas.sharing import NotificationRead
    from app.models.notification import Notification

    sos = _get_owned_sos(sos_id, current_user, db)
    rows = db.scalars(
        select(Notification)
        .where(
            Notification.user_id == current_user.id,
            Notification.kind == "sos_created",
            Notification.idempotency_key.like(f"sos:{sos.id}:%"),
        )
        .order_by(Notification.created_at.asc(), Notification.id.asc())
    ).all()
    return [NotificationRead.model_validate(r).model_dump(mode="json") for r in rows]
