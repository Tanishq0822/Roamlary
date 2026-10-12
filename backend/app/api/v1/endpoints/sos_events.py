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

    - active    -> cancelled, `cancelled_at` = now (server clock).
    - cancelled -> 409 (already closed; the first cancellation time is
      never rewritten).
    - resolved  -> 409 (a resolved incident's story is not rewritten).

    There is no request body, so a cancellation timestamp cannot be
    supplied by the client. Nothing is notified or dispatched - this
    only writes a row.
    """
    _get_owned_sos(sos_id, current_user, db)

    # Conditional UPDATE (compare-and-set): the status='active' check
    # happens INSIDE the statement, so a racing transition on another
    # request makes exactly one of them lose (rowcount 0 -> 409) instead
    # of both overwriting each other.
    result = db.execute(
        update(SosEvent)
        .where(SosEvent.id == sos_id, SosEvent.status == SosStatus.ACTIVE)
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
            detail="Only an active SOS incident can be cancelled.",
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
    """Close an `active` incident as resolved, SERVER's clock.

    - active    -> resolved, `resolved_at` = now (server clock).
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
        .where(SosEvent.id == sos_id, SosEvent.status == SosStatus.ACTIVE)
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
            detail="Only an active SOS incident can be resolved.",
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
