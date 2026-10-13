"""Travel-plan endpoints (Phase 7).

Plain language: a travel plan is one intended trip - "Goa, 2026-12-20
to 2027-01-02, flexible". Owners CRUD their own plans here. Discovery
never reads another user's plan row directly; it selects only plans
that are ACTIVE, DISCOVERABLE, and non-expired.

PRIVACY & OWNERSHIP: every route below resolves the plan with the
caller's user_id IN the query, so a plan that belongs to someone else
and a plan that does not exist return the identical 404 - ownership
cannot be probed by guessing IDs. There is intentionally no endpoint to
list or fetch arbitrary users' plans; the public summary appears only
inside discovery results and GET /travel-buddies/{user_id}.

DATES: end_date >= start_date is enforced at the schema (422). Plans
whose end_date has passed are not deleted by any job (there are no
background jobs in this project) - they are simply excluded from
discovery at READ time and flagged `expired` in their own listing.

VISIBILITY/STATUS: `visibility` starts private (secure default) and can
be flipped to discoverable by the owner; `status` moves among
active/paused/completed by explicit PATCH. Completed/paused plans never
enter discovery.
"""

from datetime import UTC
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.v1.deps import CurrentUser, DbSession
from app.api.v1.schemas.travel import TravelPlanCreate, TravelPlanPatch, TravelPlanRead
from app.core.matching import normalize_place
from app.db.base_class import utc_now
from app.models.travel_plan import TravelPlan
from app.services.discovery import today_utc

router = APIRouter(prefix="/travel-plans", tags=["travel-plans"])


def _iso(value) -> str:
    """Timestamp to UTC ISO-8601 (same normalization as other endpoints)."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()


def _read_model(plan: TravelPlan) -> TravelPlanRead:
    return TravelPlanRead(
        id=plan.id,
        destination=plan.destination,
        region=plan.region,
        start_date=plan.start_date,
        end_date=plan.end_date,
        flexible_dates=plan.flexible_dates,
        status=plan.status,
        visibility=plan.visibility,
        created_at=_iso(plan.created_at),
        updated_at=_iso(plan.updated_at),
    )


def _get_owned_plan(plan_id: UUID, current_user, db) -> TravelPlan:
    """Load a plan only if it belongs to the caller; 404 otherwise.

    The 404 covers both "not yours" and "does not exist", identically.
    """
    plan = db.scalar(
        select(TravelPlan).where(
            TravelPlan.id == plan_id,
            TravelPlan.user_id == current_user.id,
        )
    )
    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Travel plan not found.",
        )
    return plan


@router.post(
    "/",
    response_model=TravelPlanRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a travel plan for the authenticated user",
)
def create_plan(
    body: TravelPlanCreate,
    current_user: CurrentUser,
    db: DbSession,
) -> TravelPlanRead:
    """Create one plan owned by the token's user.

    The normalized destination key is derived server-side from the
    display text (trimmed + lowercased) for matching; it is never
    presented as externally verified. Visibility defaults to private.
    """
    plan = TravelPlan(
        user_id=current_user.id,
        destination=body.destination,
        destination_normalized=normalize_place(body.destination),
        region=body.region,
        region_normalized=normalize_place(body.region) if body.region else None,
        start_date=body.start_date,
        end_date=body.end_date,
        flexible_dates=body.flexible_dates,
        visibility=body.visibility,
    )
    db.add(plan)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Could not save the travel plan.",
        ) from exc
    db.refresh(plan)
    return _read_model(plan)


@router.get(
    "/",
    response_model=list[TravelPlanRead],
    summary="List my own travel plans",
)
def list_my_plans(
    current_user: CurrentUser,
    db: DbSession,
    include_expired: Annotated[
        bool,
        Query(description="Include plans whose end_date has already passed (default true)."),
    ] = True,
) -> list[TravelPlanRead]:
    """List the caller's OWN plans, newest start date first.

    There is deliberately no query for other users' plans - that data
    reaches strangers only through discovery's limited projection.
    """
    stmt = select(TravelPlan).where(TravelPlan.user_id == current_user.id)
    if not include_expired:
        stmt = stmt.where(TravelPlan.end_date >= today_utc())
    stmt = stmt.order_by(TravelPlan.start_date.desc(), TravelPlan.id.asc())
    return [_read_model(plan) for plan in db.scalars(stmt).all()]


@router.get(
    "/{plan_id}",
    response_model=TravelPlanRead,
    summary="Get one of my travel plans",
)
def get_plan(
    plan_id: UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> TravelPlanRead:
    """Fetch a single plan; 404 for other users' and missing plans alike."""
    return _read_model(_get_owned_plan(plan_id, current_user, db))


@router.patch(
    "/{plan_id}",
    response_model=TravelPlanRead,
    summary="Update one of my travel plans (partial)",
)
def patch_plan(
    plan_id: UUID,
    body: TravelPlanPatch,
    current_user: CurrentUser,
    db: DbSession,
) -> TravelPlanRead:
    """Partial update of an owned plan.

    Changing destination/region re-derives the normalized matching key
    in the same operation. Cross-field date validation uses the STORED
    dates for whichever side the body omits, so a patch can never
    produce an inverted range (422).
    """
    plan = _get_owned_plan(plan_id, current_user, db)
    changes = body.model_dump(exclude_unset=True)

    new_start = changes.get("start_date", plan.start_date)
    new_end = changes.get("end_date", plan.end_date)
    if new_end < new_start:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="end_date must not precede start_date.",
        )

    if "destination" in changes:
        plan.destination_normalized = normalize_place(changes["destination"])
    if "region" in changes:
        plan.region_normalized = normalize_place(changes["region"]) if changes["region"] else None

    for field_name, value in changes.items():
        setattr(plan, field_name, value)
    plan.updated_at = utc_now()
    db.add(plan)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Could not save the travel plan.",
        ) from exc
    db.refresh(plan)
    return _read_model(plan)


@router.delete(
    "/{plan_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete one of my travel plans",
)
def delete_plan(
    plan_id: UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> None:
    """Delete an owned plan (204).

    A plan referenced by a travel-partner request keeps its history: the
    FK is RESTRICT, so the delete is refused with 409 rather than
    silently orphaning or cascading away someone else's request record.
    """
    plan = _get_owned_plan(plan_id, current_user, db)
    db.delete(plan)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This plan is referenced by a travel-partner request and "
                "cannot be deleted; pause or complete it instead."
            ),
        ) from exc
