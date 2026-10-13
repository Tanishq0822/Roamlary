"""Community safety report endpoints (Phase 6).

Plain language: a report is one traveller's observation about a PLACE
("dark street behind the station"). These routes let an authenticated
user file one, browse the community's reports, fetch a single report,
and search reports near a map position. The Phase 3 ideas carry over:
identity comes only from the token, and a report that does not exist
and a hidden one return the identical 404.

VISIBILITY & MODERATION (enforced here):

    Every report is created `pending` (user-submitted, UNVERIFIED).
    Moderation does not exist yet: nothing can set `approved` or
    `rejected`, and no endpoint accepts a status from clients - so
    ordinary users can never mark their own reports "verified".
    Public reads return everything EXCEPT `status='rejected'` rows
    (hidden), which makes the hiding rule ready the day moderation
    arrives. Because `status` travels in every response, clients can
    always tell an unverified user report (`pending`) from an approved
    one (`approved`).

    Reports have NO owner lifecycle actions in this phase: no PATCH, no
    DELETE, no status transitions - the status column belongs to the
    future moderation system, not to the submitter.

PRIVACY: the table stores `user_id` for accountability, but responses
never include it - reports are about places, not people. No email,
phone, or auth data can appear in any response (the response schema is
a closed set of 8 fields).

NEARBY SEARCH: a plain SQL haversine distance query (Earth radius
6,371,000 m), NOT a geospatial index and NOT PostGIS. It scans the
table (O(n)), is exact enough for a city-sized radius (well under 1%
error), wraps correctly across the antimeridian, and stays accurate at
high latitudes because it uses no flat-map approximation. NULL-coordinate
rows are excluded automatically. Appropriate for prototype scale;
revisit with a real geospatial index before real traffic.

SAFETY BOUNDARY: a submitted report is an OPINION, not verified truth.
Filing one sends nothing to anyone - no notifications, no emergency
services, no nearby-user alerts.
"""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import case, func, select
from sqlalchemy.exc import IntegrityError

from app.api.v1.deps import CurrentUser, DbSession, OwnerUser
from app.api.v1.schemas.community_report import ReportCreate, ReportModerate, ReportRead
from app.models.community_report import CommunityReport
from app.models.enums import ReportCategory, ReportStatus

router = APIRouter(prefix="/reports", tags=["reports"])

# Mean Earth radius in METERS - the documented unit of every radius in
# this API. Used by the haversine formula below.
_EARTH_RADIUS_M = 6_371_000.0

# The largest search radius the API accepts (50 km): beyond that a
# "nearby" listing stops being about the traveller's surroundings.
_MAX_RADIUS_M = 50_000.0


def _get_visible_report(report_id: UUID, db) -> CommunityReport:
    """Load a report by ID unless it is missing or hidden (`rejected`).

    404 for both cases, identically, so a hidden report cannot be
    distinguished from one that never existed.
    """
    report = db.scalar(
        select(CommunityReport).where(
            CommunityReport.id == report_id,
            CommunityReport.status != ReportStatus.REJECTED,
        )
    )
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found.",
        )
    return report


@router.post(
    "",
    response_model=ReportRead,
    status_code=status.HTTP_201_CREATED,
    summary="File a community safety report (as `pending`)",
)
def create_community_report(
    body: ReportCreate,
    current_user: CurrentUser,
    db: DbSession,
) -> ReportRead:
    """Submit one observation about a place.

    The submitter is the token's user; the `pending` (unverified)
    moderation state is chosen by the server. Nothing is sent to
    anyone, and the report is an opinion - not verified truth.
    """
    report = CommunityReport(
        user_id=current_user.id,
        category=body.category,
        description=body.description,
        latitude=body.latitude,
        longitude=body.longitude,
        status=ReportStatus.PENDING,
    )
    db.add(report)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Could not save the report.",
        ) from exc
    db.refresh(report)
    return ReportRead.model_validate(report)


@router.get(
    "",
    response_model=list[ReportRead],
    summary="List visible community reports (newest first, paginated)",
)
def list_community_reports(
    current_user: CurrentUser,
    db: DbSession,
    category: Annotated[
        ReportCategory | None,
        Query(description="Optional filter: only reports of this category."),
    ] = None,
    report_status: Annotated[
        Literal[ReportStatus.PENDING, ReportStatus.APPROVED, ReportStatus.RESOLVED] | None,
        Query(
            alias="status",
            description=(
                "Optional filter: pending (unverified), approved, or "
                "resolved. 'rejected' is hidden from the public API entirely."
            ),
        ),
    ] = None,
    offset: Annotated[int, Query(ge=0, description="Rows to skip (default 0).")] = 0,
    limit: Annotated[int, Query(ge=1, le=100, description="Page size, 1-100 (default 20).")] = 20,
) -> list[ReportRead]:
    """Return visible reports, newest first (stable order), paginated.

    Hidden (`rejected`) rows are never returned, with or without a
    status filter. Any authenticated user may read reports - they are
    community content, not private data.
    """
    stmt = select(CommunityReport).where(CommunityReport.status != ReportStatus.REJECTED)
    if category is not None:
        stmt = stmt.where(CommunityReport.category == category)
    if report_status is not None:
        stmt = stmt.where(CommunityReport.status == report_status)
    stmt = (
        stmt.order_by(CommunityReport.created_at.desc(), CommunityReport.id.desc())
        .offset(offset)
        .limit(limit)
    )
    reports = db.scalars(stmt).all()
    return [ReportRead.model_validate(r) for r in reports]


@router.get(
    "/nearby",
    response_model=list[ReportRead],
    summary="List visible reports within radius_m meters of a position",
)
def nearby_community_reports(
    current_user: CurrentUser,
    db: DbSession,
    latitude: Annotated[float, Query(ge=-90, le=90, description="Center latitude.")],
    longitude: Annotated[float, Query(ge=-180, le=180, description="Center longitude.")],
    radius_m: Annotated[
        float,
        Query(
            gt=0,
            le=_MAX_RADIUS_M,
            description="Search radius in METERS, above 0 and at most 50000 (50 km).",
        ),
    ],
    category: Annotated[
        ReportCategory | None,
        Query(description="Optional filter: only reports of this category."),
    ] = None,
    offset: Annotated[int, Query(ge=0, description="Rows to skip (default 0).")] = 0,
    limit: Annotated[int, Query(ge=1, le=100, description="Page size, 1-100 (default 20).")] = 20,
) -> list[ReportRead]:
    """Reports near a map position, nearest first (stable order).

    `radius_m` is in METERS, above 0 and capped at 50000 (50 km). The
    distance is a haversine computed in SQL (see the module docstring
    for the method and its limitations). Hidden (`rejected`) rows are
    never returned. `NULL`-coordinate rows cannot match and are
    skipped. The response uses the same 8-field shape as every other
    report listing (distance is not exposed; ordering conveys it).
    """
    # Haversine distance in meters, as a parameterized SQL expression.
    # The formula uses trig of the half-differences, so it wraps
    # correctly across the antimeridian (Δlon 359.8° behaves exactly
    # like 0.2°) and stays accurate at high latitudes. `a` is clamped
    # to <= 1 so rounding at antipodal points cannot push asin()
    # outside its domain and error the query.
    half_dlat = func.radians((CommunityReport.latitude - latitude) / 2.0)
    half_dlon = func.radians((CommunityReport.longitude - longitude) / 2.0)
    a = func.sin(half_dlat) * func.sin(half_dlat) + func.cos(func.radians(latitude)) * func.cos(
        func.radians(CommunityReport.latitude)
    ) * func.sin(half_dlon) * func.sin(half_dlon)
    a_clamped = case((a > 1.0, 1.0), else_=a)
    distance_m = 2.0 * _EARTH_RADIUS_M * func.asin(func.sqrt(a_clamped))

    stmt = (
        select(CommunityReport, distance_m.label("distance_m"))
        .where(
            CommunityReport.status != ReportStatus.REJECTED,
            distance_m <= radius_m,
        )
        .order_by(
            distance_m,
            CommunityReport.created_at.desc(),
            CommunityReport.id.desc(),
        )
        .offset(offset)
        .limit(limit)
    )
    if category is not None:
        stmt = stmt.where(CommunityReport.category == category)
    rows = db.execute(stmt).all()
    return [ReportRead.model_validate(row[0]) for row in rows]


@router.get(
    "/{report_id}",
    response_model=ReportRead,
    summary="Return one visible report (404 if missing or hidden)",
)
def get_community_report(
    report_id: UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> ReportRead:
    """Fetch a single visible report. 404 if it is missing OR rejected."""
    report = _get_visible_report(report_id, db)
    return ReportRead.model_validate(report)


# Allowed moderation moves (Phase 11). Terminal states lock: rejected
# and resolved never move again (a bad decision is corrected by a new
# report, not by rewriting review history).
_MODERATION_MOVES: dict[str, set[str]] = {
    ReportStatus.PENDING: {ReportStatus.APPROVED, ReportStatus.REJECTED},
    ReportStatus.APPROVED: {ReportStatus.RESOLVED, ReportStatus.REJECTED},
    ReportStatus.REJECTED: set(),
    ReportStatus.RESOLVED: set(),
}


@router.patch(
    "/{report_id}/moderate",
    response_model=ReportRead,
    summary="Moderate a report (owner only)",
)
def moderate_community_report(
    report_id: UUID,
    body: ReportModerate,
    owner: OwnerUser,
    db: DbSession,
) -> ReportRead:
    """Owner sets the moderation state with an audit stamp (reviewer +
    server clock). Ordinary users cannot approve/reject/resolve anything
    - not their own reports, not anyone else's: this is the ONLY route
    that writes `status`, and it demands the owner role. Illegal moves
    (including re-deciding terminal rows) are 409; the row keeps its
    state. Moderation never exposes the submitter (responses stay
    identity-free) and never notifies anyone (notifications are Phase
    12's explicit surface, not a side effect)."""
    from datetime import UTC, datetime

    report = db.scalar(select(CommunityReport).where(CommunityReport.id == report_id))
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found.",
        )
    if body.status not in _MODERATION_MOVES.get(report.status, set()):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Cannot move a report from '{report.status}' to '{body.status}'. "
                "Terminal states (rejected, resolved) never move again."
            ),
        )
    report.status = body.status
    report.reviewed_by = owner.id
    report.reviewed_at = datetime.now(UTC)
    db.commit()
    db.refresh(report)
    return ReportRead.model_validate(report)
