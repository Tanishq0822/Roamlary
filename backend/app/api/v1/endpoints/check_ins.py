"""Safety check-in endpoints (Phase 4).

Plain language: a check-in is a promise - "I'll be back by <due_at>."
These routes create, list, edit, and complete those promises. The same
two ideas from trusted contacts apply here: ownership comes only from
the token, and a not-yours contact and a nonexistent one return the
identical 404.

STATUS LIFECYCLE (enforced in this module):

    pending ──▶ safe          (PATCH status, or POST /complete)
          ├──▶ needs_help     (PATCH status)
          └──▶ cancelled      (PATCH status)

    safe / needs_help / expired / cancelled are TERMINAL. A terminal
    check-in can never go back to pending or move to another status -
    completed records are not silently reactivated. There is no
    "reactivate" transition by design; if the user wants a new
    check-in, they create a new one.

`completed_at` is set by the SERVER clock the first time a check-in
reaches `safe` or `needs_help` (i.e. when the user answers it), and is
never taken from client data. `cancelled` leaves it NULL because nothing
was ever completed.

SAFETY BOUNDARY: an overdue check-in is NOT proof of danger. Phase 4
stores data only - it never contacts emergency services, never notifies
anyone, and never triggers an SOS. Those behaviours belong to later
phases and need explicit design and safeguards first.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.v1.deps import CurrentUser, DbSession
from app.api.v1.schemas.check_in import CheckInCreate, CheckInRead, CheckInUpdate
from app.db.base_class import utc_now
from app.models.check_in import CheckIn
from app.models.enums import CheckInStatus

router = APIRouter(prefix="/check-ins", tags=["check-ins"])

# Statuses a PENDING check-in may move to. Anything else (including
# moving between two terminal states, or back to pending) is refused.
ALLOWED_TRANSITIONS: dict[CheckInStatus, set[CheckInStatus]] = {
    CheckInStatus.PENDING: {
        CheckInStatus.SAFE,
        CheckInStatus.NEEDS_HELP,
        CheckInStatus.CANCELLED,
    },
    # Terminal states map to an empty set: no exits.
    CheckInStatus.SAFE: set(),
    CheckInStatus.NEEDS_HELP: set(),
    CheckInStatus.EXPIRED: set(),
    CheckInStatus.CANCELLED: set(),
}


def _get_owned_checkin(checkin_id: UUID, current_user, db) -> CheckIn:
    """Load a check-in by ID only if it belongs to the current user.

    404 for both "not yours" and "does not exist", identically, so
    ownership cannot be probed by guessing IDs.
    """
    checkin = db.scalar(
        select(CheckIn).where(
            CheckIn.id == checkin_id,
            CheckIn.user_id == current_user.id,
        )
    )
    if checkin is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Check-in not found.",
        )
    return checkin


@router.post(
    "/",
    response_model=CheckInRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new safety check-in for the authenticated user",
)
def create_checkin(
    body: CheckInCreate,
    current_user: CurrentUser,
    db: DbSession,
) -> CheckInRead:
    """Create a check-in, starting life in the `pending` status.

    The owner is the token's user; the status is chosen by the server.
    `due_at` (if given) was already validated as future and
    timezone-aware by the schema. Nothing is sent to anyone.
    """
    checkin = CheckIn(
        user_id=current_user.id,
        status=CheckInStatus.PENDING,
        note=body.note,
        due_at=body.due_at,
    )
    db.add(checkin)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Could not save the check-in.",
        ) from exc
    db.refresh(checkin)
    return CheckInRead.model_validate(checkin)


@router.get(
    "/",
    response_model=list[CheckInRead],
    summary="List the authenticated user's check-ins (newest first)",
)
def list_checkins(
    current_user: CurrentUser,
    db: DbSession,
    checkin_status: Annotated[
        CheckInStatus | None,
        Query(
            alias="status",
            description="Optional filter: return only check-ins in this status.",
        ),
    ] = None,
) -> list[CheckInRead]:
    """Return ONLY the caller's check-ins, newest first (stable order).

    Pass ?status=pending (or safe/needs_help/expired/cancelled) to filter
    by status; an unknown status value is rejected with 422 by the query
    validator. No pagination yet (documented limitation).
    """
    stmt = select(CheckIn).where(CheckIn.user_id == current_user.id)
    if checkin_status is not None:
        stmt = stmt.where(CheckIn.status == checkin_status)
    stmt = stmt.order_by(CheckIn.created_at.desc(), CheckIn.id.desc())
    checkins = db.scalars(stmt).all()
    return [CheckInRead.model_validate(c) for c in checkins]


@router.get(
    "/overdue",
    response_model=list[CheckInRead],
    summary="List my overdue check-ins (pending and past due)",
)
def list_overdue_checkins(
    current_user: CurrentUser,
    db: DbSession,
) -> list[CheckInRead]:
    """My `pending` check-ins whose `due_at` has passed, oldest-due
    first. Read-time evaluation ONLY (brief 12.D): no background job
    exists, nothing auto-transitions rows, and this endpoint makes no
    delivery or alerting claim - it simply surfaces what needs
    attention. Rows without a `due_at` are never overdue."""
    from datetime import UTC, datetime

    now = datetime.now(UTC)
    stmt = (
        select(CheckIn)
        .where(
            CheckIn.user_id == current_user.id,
            CheckIn.status == CheckInStatus.PENDING,
            CheckIn.due_at.is_not(None),
            CheckIn.due_at < now,
        )
        .order_by(CheckIn.due_at.asc(), CheckIn.id.asc())
    )
    checkins = db.scalars(stmt).all()
    return [CheckInRead.model_validate(c) for c in checkins]


@router.get(
    "/{checkin_id}",
    response_model=CheckInRead,
    summary="Return one of the authenticated user's check-ins",
)
def get_checkin(
    checkin_id: UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> CheckInRead:
    """Fetch a single check-in. 404 if it is missing OR not yours."""
    checkin = _get_owned_checkin(checkin_id, current_user, db)
    return CheckInRead.model_validate(checkin)


@router.patch(
    "/{checkin_id}",
    response_model=CheckInRead,
    summary="Update a check-in's note, deadline, or status",
)
def update_checkin(
    checkin_id: UUID,
    body: CheckInUpdate,
    current_user: CurrentUser,
    db: DbSession,
) -> CheckInRead:
    """Edit a check-in's note, deadline, or status.

    Rules:
    - `note` and `due_at` may only be edited while the check-in is
      `pending`. A terminal check-in is a closed record; its story is
      not rewritten after the fact.
    - `status` must follow ALLOWED_TRANSITIONS: only a pending check-in
      may move, and only to safe/needs_help/cancelled. Moving to `safe`
      or `needs_help` stamps `completed_at` with the server clock.
    - `id`, `user_id`, `created_at`, `completed_at`, and `updated_at`
      cannot be sent at all (422 via extra="forbid").
    - An empty body is a valid no-op and does not touch `updated_at`.
    """
    checkin = _get_owned_checkin(checkin_id, current_user, db)
    sent = body.model_fields_set
    if not sent:
        return CheckInRead.model_validate(checkin)

    current = CheckInStatus(checkin.status)
    target = body.status

    # 1. Validate any requested status transition BEFORE touching fields.
    #    A uniform rule: a status value is only honored if it is a valid
    #    transition from the current state. Setting the same value again
    #    (safe -> safe) is NOT a transition, so terminal statuses stay
    #    fully locked - no silent no-ops that look like edits.
    if target is not None:
        allowed = ALLOWED_TRANSITIONS.get(current, set())
        if target not in allowed:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Invalid status transition: a {current.value} check-in "
                    f"cannot become {target.value}."
                ),
            )

    # 2. Note/deadline edits are only allowed while still pending.
    if ("note" in sent or "due_at" in sent) and current != CheckInStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(f"Only a pending check-in can be edited; this one is {current.value}."),
        )

    # 3. Apply changes.
    if "note" in sent:
        checkin.note = body.note
    if "due_at" in sent:
        checkin.due_at = body.due_at
    if target is not None and target != current:
        checkin.status = target
        # First answer to the check-in stamps the server completion
        # clock. cancelled does not: nothing was ever completed.
        if target in (CheckInStatus.SAFE, CheckInStatus.NEEDS_HELP):
            checkin.completed_at = utc_now()

    checkin.updated_at = utc_now()
    db.add(checkin)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Could not save the check-in.",
        ) from exc
    db.refresh(checkin)
    return CheckInRead.model_validate(checkin)


@router.post(
    "/{checkin_id}/complete",
    response_model=CheckInRead,
    summary="Mark a pending check-in as safe",
)
def complete_checkin(
    checkin_id: UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> CheckInRead:
    """Mark an eligible check-in `safe` using the SERVER's clock.

    IDEMPOTENT: completing an already-`safe` check-in succeeds (200) and
    returns it unchanged - crucially, `completed_at` keeps the time of
    the FIRST completion, so network retries cannot rewrite history.

    - pending  -> safe, `completed_at` = now (server clock).
    - safe     -> 200, no change (idempotent no-op).
    - needs_help / expired / cancelled -> 409. `safe` means "I'm fine",
      which must never overwrite a needs_help answer, and a cancelled
      check-in is closed.

    The client cannot supply a completion timestamp; there is no field
    for it. No SOS or notification is triggered - this only writes a row.
    """
    checkin = _get_owned_checkin(checkin_id, current_user, db)
    current = CheckInStatus(checkin.status)

    if current == CheckInStatus.SAFE:
        # Idempotent no-op: return the already-completed record as-is.
        return CheckInRead.model_validate(checkin)

    if current != CheckInStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(f"Only a pending check-in can be completed; this one is {current.value}."),
        )

    checkin.status = CheckInStatus.SAFE
    checkin.completed_at = utc_now()  # server clock, never client data
    checkin.updated_at = utc_now()
    db.add(checkin)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Could not save the check-in.",
        ) from exc
    db.refresh(checkin)
    return CheckInRead.model_validate(checkin)
