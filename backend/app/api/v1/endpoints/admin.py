"""Owner-only admin endpoints: verification review + social policy (Phase 6b).

Plain language: every route in this file demands the `owner` role via the
`require_owner` dependency (401 without a token, 403 for ordinary users).
There is no other way in - no query parameter, no header, no body field
can grant access.

REVIEW QUEUE

    GET  /admin/verification-requests?status=pending   -> list (oldest
         submitted first, so the queue is fair FIFO; optional status
         filter: pending | approved | rejected, default = all)
    POST /admin/verification-requests/{id}/approve     -> request row
    POST /admin/verification-requests/{id}/reject      -> request row

    Approve/reject rules (all tested):
      * 404 if the request does not exist.
      * 409 unless the request is currently `pending` (compare-and-set
        update, so two reviewers racing cannot double-decide).
      * 409 if a reviewer tries to review THEIR OWN request - even the
        owner may not self-approve; with a single-owner deployment that
        means the owner's own account simply stays unverified through the
        API (documented; a second reviewer or a deliberate server-side
        DB action is required). No self-elevation, ever.
      * Decision + reviewed_at + reviewed_by land in the SAME transaction
        as the applicant's account-status move.

SOCIAL POLICY

    GET   /admin/policy/social-verification  -> effective value (fail-closed
          read: missing/corrupt row reports "required")
    PATCH /admin/policy/social-verification  -> validated boolean write

    The PATCH is rate limited in-process (5 attempts / hour / owner) -
    "consistent with existing architecture", which has no shared
    rate-limit store; the limitation is documented. A change appends a
    `setting_changes` audit row (who/when/old/new) in the same
    transaction, and NEVER touches any user's verification_status or any
    historical review row.
"""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.api.v1.deps import DbSession, OwnerUser
from app.api.v1.schemas.verification import (
    PolicyResponse,
    PolicyUpdateRequest,
    ReviewActionRequest,
    VerificationRequestReview,
)
from app.core.policy import (
    SOCIAL_REQUIRES_VERIFICATION_KEY,
    get_policy,
    set_policy,
)
from app.core.rate_limit import check_rate_limit
from app.db.base_class import utc_now
from app.models.app_setting import AppSetting
from app.models.enums import VerificationRequestStatus, VerificationStatus
from app.models.identity_verification import IdentityVerification
from app.models.user import User

router = APIRouter(prefix="/admin", tags=["admin"])

# Sensitive-config throttle: how many policy changes one owner may make
# per rolling hour, per process (see module docstring for the caveat).
_POLICY_CHANGE_LIMIT = 5
_POLICY_CHANGE_WINDOW_S = 3600


def _policy_response(db: Session) -> PolicyResponse:
    """Build the policy view from the row + the fail-closed effective read."""
    row = db.scalar(select(AppSetting).where(AppSetting.key == SOCIAL_REQUIRES_VERIFICATION_KEY))
    return PolicyResponse(
        key=SOCIAL_REQUIRES_VERIFICATION_KEY,
        requires_verification=get_policy(db),
        updated_at=row.updated_at if row else None,
        updated_by=row.updated_by if row else None,
    )


def _review_request(
    db: Session,
    owner: User,
    request_id: UUID,
    *,
    approve: bool,
    review_note: str | None,
) -> VerificationRequestReview:
    """Shared approve/reject logic (see module docstring for the rules)."""
    row = db.scalar(select(IdentityVerification).where(IdentityVerification.id == request_id))
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Verification request not found.",
        )
    if row.user_id == owner.id:
        # Self-review is refused for EVERYONE, owner included.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You cannot review your own verification request.",
        )
    if row.status != VerificationRequestStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only pending requests can be reviewed.",
        )

    new_request_status = (
        VerificationRequestStatus.APPROVED if approve else VerificationRequestStatus.REJECTED
    )
    new_account_status = VerificationStatus.VERIFIED if approve else VerificationStatus.REJECTED

    # Compare-and-set: re-assert `pending` in the WHERE clause so two
    # concurrent reviewers cannot both decide (rowcount 0 -> lost race).
    result = db.execute(
        update(IdentityVerification)
        .where(
            IdentityVerification.id == request_id,
            IdentityVerification.status == VerificationRequestStatus.PENDING,
        )
        .values(
            status=new_request_status,
            reviewed_at=utc_now(),
            reviewed_by=owner.id,
            review_note=review_note,
        )
    )
    if result.rowcount == 0:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only pending requests can be reviewed.",
        )

    # Account state moves in the SAME transaction as the decision.
    db.execute(
        update(User).where(User.id == row.user_id).values(verification_status=new_account_status)
    )
    db.commit()
    db.refresh(row)

    return VerificationRequestReview(
        id=row.id,
        user_id=row.user_id,
        display_name=row.user.display_name,
        status=row.status,
        created_at=row.created_at,
        reviewed_at=row.reviewed_at,
        reviewed_by=row.reviewed_by,
        review_note=row.review_note,
        applicant_note=row.applicant_note,
    )


@router.get(
    "/verification-requests",
    response_model=list[VerificationRequestReview],
    summary="List verification requests (review queue)",
)
def list_verification_requests(
    owner: OwnerUser,
    db: DbSession,
    status_filter: Literal["pending", "approved", "rejected"] | None = Query(None, alias="status"),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> list[VerificationRequestReview]:
    """Owner-only review queue, oldest submitted first (FIFO fairness).

    `owner` is fetched but unused for logic - its presence IS the 403/401
    gate. The optional `status` filter narrows the queue; offset/limit
    pagination matches the conventions used by /reports.
    """
    stmt = (
        select(IdentityVerification, User.display_name)
        .join(User, IdentityVerification.user_id == User.id)
        .order_by(IdentityVerification.created_at.asc())
        .offset(offset)
        .limit(limit)
    )
    if status_filter is not None:
        stmt = stmt.where(IdentityVerification.status == status_filter)

    rows = db.execute(stmt).all()
    return [
        VerificationRequestReview(
            id=request.id,
            user_id=request.user_id,
            display_name=display_name,
            status=request.status,
            created_at=request.created_at,
            reviewed_at=request.reviewed_at,
            reviewed_by=request.reviewed_by,
            review_note=request.review_note,
            applicant_note=request.applicant_note,
        )
        for request, display_name in rows
    ]


@router.post(
    "/verification-requests/{request_id}/approve",
    response_model=VerificationRequestReview,
    summary="Approve a pending verification request",
)
def approve_verification_request(
    request_id: UUID,
    owner: OwnerUser,
    db: DbSession,
    body: ReviewActionRequest | None = None,
) -> VerificationRequestReview:
    """Owner approves: request -> approved, applicant's account -> verified."""
    return _review_request(
        db,
        owner,
        request_id,
        approve=True,
        review_note=body.review_note if body else None,
    )


@router.post(
    "/verification-requests/{request_id}/reject",
    response_model=VerificationRequestReview,
    summary="Reject a pending verification request",
)
def reject_verification_request(
    request_id: UUID,
    owner: OwnerUser,
    db: DbSession,
    body: ReviewActionRequest | None = None,
) -> VerificationRequestReview:
    """Owner rejects: request -> rejected, applicant's account -> rejected.

    The applicant may then submit a NEW request (rejected -> pending).
    """
    return _review_request(
        db,
        owner,
        request_id,
        approve=False,
        review_note=body.review_note if body else None,
    )


@router.get(
    "/policy/social-verification",
    response_model=PolicyResponse,
    summary="Read the social-verification policy (owner only)",
)
def read_social_policy(
    owner: OwnerUser,
    db: DbSession,
) -> PolicyResponse:
    """Owner-only read of the effective policy (fail-closed reporting)."""
    return _policy_response(db)


@router.patch(
    "/policy/social-verification",
    response_model=PolicyResponse,
    summary="Change the social-verification policy (owner only)",
)
def update_social_policy(
    owner: OwnerUser,
    db: DbSession,
    body: PolicyUpdateRequest,
) -> PolicyResponse:
    """Owner-only policy write: rate limited, validated, audited.

    Order of defenses: (1) owner role (dependency), (2) schema validation
    of the boolean, (3) per-owner rate limit 5/hour -> 429, (4) audit row
    with who/when/old/new. Changing policy NEVER marks anyone verified or
    rewrites history - it touches only `app_settings` + `setting_changes`.
    """
    check_rate_limit(
        f"policy-change:{owner.id}",
        limit=_POLICY_CHANGE_LIMIT,
        window_seconds=_POLICY_CHANGE_WINDOW_S,
    )
    set_policy(db, value=body.requires_verification, changed_by=owner.id)
    db.commit()
    return _policy_response(db)
