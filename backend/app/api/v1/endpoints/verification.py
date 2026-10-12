"""Identity-verification workflow endpoints (Phase 6b).

Plain language: two routes, both for the CALLER'S OWN account:

    GET  /verification/status   - "am I verified yet?" plus the live
                                  policy and the caller's latest request.
                                  Always reachable (never gated) so users
                                  can see where they stand.
    POST /verification/requests - submit a request for manual review.
                                  Server sets status=pending; the client
                                  cannot choose anything.

TRANSITIONS ENFORCED HERE (the complete allowed set):

    unverified -> pending    by submitting a request (this route)
    rejected   -> pending    by submitting a request again
    pending    -> verified   by an OWNER approving (admin route)
    pending    -> rejected   by an OWNER rejecting (admin route)

    Anything else is refused: duplicate submissions while pending (409),
    submissions once verified (409), and every self-service path to
    `verified` (there is none - the API simply has no route for it).

NO IDENTITY DATA: no documents, no ID numbers, no scans are collected or
stored anywhere in this workflow - only an optional short note for the
reviewer. This is a labelled DEVELOPMENT/MANUAL-REVIEW process; a real
identity-verification provider is still required (documented gap).
"""

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.deps import CurrentUser, DbSession
from app.api.v1.schemas.verification import (
    VerificationRequestCreate,
    VerificationRequestSummary,
    VerificationStatusResponse,
)
from app.core.policy import get_policy
from app.models.enums import VerificationRequestStatus, VerificationStatus
from app.models.identity_verification import IdentityVerification

router = APIRouter(prefix="/verification", tags=["verification"])


def _latest_request(db: Session, user_id) -> IdentityVerification | None:
    """Most recent request row for this user (history newest-first)."""
    return db.scalar(
        select(IdentityVerification)
        .where(IdentityVerification.user_id == user_id)
        .order_by(IdentityVerification.created_at.desc())
        .limit(1)
    )


@router.get(
    "/status",
    response_model=VerificationStatusResponse,
    summary="Current user's verification status",
)
def get_verification_status(
    current_user: CurrentUser,
    db: DbSession,
) -> VerificationStatusResponse:
    """Return the CALLER'S OWN verification picture (any role, any state).

    Deliberately NOT gated by require_verified_user: a user must always be
    able to read their own verification state - that is how they know to
    submit or resubmit. Everything derives from the token's identity;
    there is no user_id parameter to ask about someone else.
    """
    latest = _latest_request(db, current_user.id)
    return VerificationStatusResponse(
        verification_status=VerificationStatus(current_user.verification_status),
        role=current_user.role,
        social_access_required=get_policy(db),
        latest_request=latest,
    )


@router.post(
    "/requests",
    response_model=VerificationRequestSummary,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a verification request (manual review)",
)
def create_verification_request(
    current_user: CurrentUser,
    db: DbSession,
    body: VerificationRequestCreate | None = None,
) -> IdentityVerification:
    """Start a new verification request for the caller's own account.

    Allowed only from `unverified` or `rejected` (a rejected applicant may
    always try again). `pending` and `verified` are refused with 409.

    The optional body note (<=200 chars) is the ONLY data collected -
    never identity documents. Account status moves unverified/rejected ->
    pending in the SAME transaction as the row insert, so the account can
    never be pending without a request or vice versa.
    """
    if current_user.verification_status == VerificationStatus.VERIFIED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Account is already verified; no new request is possible.",
        )
    if current_user.verification_status == VerificationStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A verification request is already under review.",
        )

    request_row = IdentityVerification(
        user_id=current_user.id,
        status=VerificationRequestStatus.PENDING,
        applicant_note=body.note if body else None,
    )
    current_user.verification_status = VerificationStatus.PENDING
    db.add(request_row)
    db.commit()
    db.refresh(request_row)
    return request_row
