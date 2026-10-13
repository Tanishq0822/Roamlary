"""Billing endpoints: policy view, payment lifecycle, admin visibility (Phase 14).

Plain language: money rules live here; POSTS live in their own
endpoints. Publishing endpoints call `authorize_post()` and answer 402
with the price when payment is needed; THIS module moves payments
through pending -> succeeded|failed|cancelled (+ owner-recorded
refunded) and shows everyone exactly what they may see (payers see
their rows; owners see all + the policy).

What this module NEVER does (brief C.9/C.12): accept an amount from
any client (amounts are server-set from the live policy); mark a
payment successful except through provider verification (mock test
tokens are verified server-side); pretend an unconfigured provider
succeeded (NullProvider fails honestly); log credentials (rows and
logs carry references and states only).
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.api.v1.deps import CurrentUser, DbSession, OwnerUser
from app.api.v1.schemas.billing import (
    BillingPolicyRead,
    BillingPolicyUpdate,
    PaymentList,
    PaymentPay,
    PaymentRead,
    WebhookEvent,
)
from app.core.billing_policy import (
    CURRENCY,
    get_billing_policy,
    set_billing_policy,
)
from app.core.rate_limit import check_rate_limit
from app.models.enums import PaymentStatus
from app.models.post_payment import PostPayment
from app.services.billing import pay_pending_payment, select_billing_provider

router = APIRouter(prefix="/billing", tags=["billing"])
admin_router = APIRouter(prefix="/admin", tags=["admin"])

# Standing refund disclosure (served verbatim in the policy view so the
# API, docs, and UI always quote one text). Record-only refunds: with no
# real provider no money moves - the row state is the whole mechanism,
# and the text says exactly that (no promised processing).
REFUND_TERMS = (
    "Refund policy (record-only until a real payment provider is configured): "
    "a succeeded payment may be marked refunded by the platform owner for confirmed "
    "duplicate charges or other approved cases; marking refunded updates the record only "
    "and moves no money. No subscriptions and no hidden charges exist in this phase."
)

# Anti-brute-force on payer-supplied provider tokens (shared in-process
# limiter, same documented caveat).
_PAY_LIMIT_PER_HOUR = 10


def _payment_read(row: PostPayment) -> PaymentRead:
    """One payment row (state and references only - never credentials)."""
    return PaymentRead(
        id=row.id,
        category=row.category,
        subject_type=row.subject_type,
        subject_id=row.subject_id,
        amount_paise=row.amount_paise,
        currency=row.currency,
        status=row.status,
        provider=row.provider,
        attempts=row.attempts or 0,
        last_error=row.last_error,
        consumed_at=row.consumed_at,
        created_at=row.created_at,
    )


def _policy_view(user, db: DbSession) -> BillingPolicyRead:
    """Effective pricing + the CALLER's free-post counters (shared by
    the user policy view and the owner policy view)."""
    price_paise, free_total = get_billing_policy(db)
    free_used = user.free_posts_used or 0
    remaining = max(free_total - free_used, 0)
    return BillingPolicyRead(
        price_paise=price_paise,
        currency=CURRENCY,
        free_posts_total=free_total,
        free_posts_used=free_used,
        free_remaining=remaining,
        next_charge_paise=0 if remaining > 0 else price_paise,
        provider_configured=select_billing_provider().name != "unconfigured"
        and select_billing_provider().name != "none",
        refund_terms=REFUND_TERMS,
    )


@router.get(
    "/policy",
    response_model=BillingPolicyRead,
    summary="Show the pay-per-post price and my free-post state",
)
def read_billing_policy(current_user: CurrentUser, db: DbSession) -> BillingPolicyRead:
    """The price display BEFORE anyone confirms publishing: live price,
    currency, free entitlement total/used/remaining, the exact next
    charge (0 while free entitlement lasts), provider readiness, and
    the standing refund terms. Per-user `free_posts_used` comes from
    the token's account - never from a parameter."""
    return _policy_view(current_user, db)


@router.get(
    "/payments",
    response_model=PaymentList,
    summary="List my payment history (newest first)",
)
def list_my_payments(
    current_user: CurrentUser,
    db: DbSession,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> PaymentList:
    """The caller's OWN rows only (owners use the admin listing for the
    full view) - user id always comes from the token."""
    conds = [PostPayment.user_id == current_user.id]
    total = db.scalar(select(func.count()).select_from(PostPayment).where(*conds)) or 0
    rows = db.scalars(
        select(PostPayment)
        .where(*conds)
        .order_by(PostPayment.created_at.desc(), PostPayment.id.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return PaymentList(
        total=total, offset=offset, limit=limit, results=[_payment_read(r) for r in rows]
    )


@router.post(
    "/payments/{payment_id}/pay",
    response_model=PaymentRead,
    summary="Pay a pending payment (provider-verified)",
)
def pay_payment(
    payment_id: UUID, body: PaymentPay, current_user: CurrentUser, db: DbSession
) -> PaymentRead:
    """Submit a provider token for ONE OWN pending or failed payment.
    The token is verified SERVER-SIDE against the configured provider:
    mock tokens confirm their exact payment row in tests; anything else
    (wrong token, unconfigured provider) FAILS the row honestly - it
    never confirms. Failed rows stay payable for another attempt
    (failed never unlocks publishing); cancelled/refunded/succeeded
    rows are 409. Foreign or missing ids are the identical 404."""
    check_rate_limit(
        f"billing-pay:{current_user.id}",
        limit=_PAY_LIMIT_PER_HOUR,
        window_seconds=3600,
    )
    row = db.scalar(
        select(PostPayment).where(
            PostPayment.id == payment_id, PostPayment.user_id == current_user.id
        )
    )
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found.",
        )
    return _payment_read(pay_pending_payment(db, payment=row, provider_token=body.provider_token))


@router.post(
    "/payments/{payment_id}/cancel",
    response_model=PaymentRead,
    summary="Cancel one of my pending payments",
)
def cancel_payment(payment_id: UUID, current_user: CurrentUser, db: DbSession) -> PaymentRead:
    """Withdraw a PENDING payment -> `cancelled` (terminal; it can never
    fund publishing afterwards). Only the payer; only pending rows."""
    row = db.scalar(
        select(PostPayment).where(
            PostPayment.id == payment_id, PostPayment.user_id == current_user.id
        )
    )
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found.",
        )
    if row.status != PaymentStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Only pending payments can be cancelled (current: '{row.status}').",
        )
    row.status = PaymentStatus.CANCELLED
    db.commit()
    db.refresh(row)
    return _payment_read(row)


@router.post(
    "/webhook",
    response_model=PaymentRead,
    summary="Provider webhook (mock only; idempotent)",
)
def billing_webhook(body: WebhookEvent, db: DbSession) -> PaymentRead:
    """Process one provider callback WITHOUT authentication (webhooks
    carry no user token by nature). Accepted ONLY when the mock
    provider is configured - any real-provider traffic here is refused
    (401 without credentials is meaningless; the refusal is 422 with an
    explicit message, because unsigned webhooks must never move money).
    Duplicate deliveries resolve via the UNIQUE provider reference to
    the SAME row state - never a second charge or post. Unknown payment
    ids are 404 (no probing value: ids are unguessable UUIDs)."""
    from app.core.config import settings

    if (settings.billing_provider or "none").strip().lower() != "mock":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Webhook delivery requires a configured, signed provider integration. "
                "The mock webhook is enabled only with BILLING_PROVIDER=mock (tests)."
            ),
        )
    if body.outcome not in ("succeeded", "failed"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="outcome must be 'succeeded' or 'failed'.",
        )
    row = db.scalar(select(PostPayment).where(PostPayment.id == body.payment_id))
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found.",
        )
    if row.provider_reference is not None:
        # Idempotent replay: a reference is already recorded - return the
        # row unchanged ONLY if it matches this delivery; a conflicting
        # reference for one payment is a provider error (409), never a
        # second charge.
        if row.provider_reference != body.provider_reference:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="That payment already carries a different provider reference.",
            )
        return _payment_read(row)
    if row.status not in (PaymentStatus.PENDING, PaymentStatus.FAILED):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Only pending or failed payments accept webhook outcomes "
                f"(current: '{row.status}')."
            ),
        )
    row.attempts = (row.attempts or 0) + 1
    if body.outcome == "succeeded":
        row.status = PaymentStatus.SUCCEEDED
        row.provider = "mock"
        row.provider_reference = body.provider_reference
        row.last_error = None
    else:
        row.status = PaymentStatus.FAILED
        row.last_error = f"Mock webhook reported failure (ref {body.provider_reference})."
    try:
        db.commit()
    except IntegrityError:
        # A duplicate delivery raced: the UNIQUE reference kept one row.
        db.rollback()
        row = db.scalar(select(PostPayment).where(PostPayment.id == body.payment_id))
        return _payment_read(row)
    db.refresh(row)
    return _payment_read(row)


@admin_router.get(
    "/payments",
    response_model=PaymentList,
    summary="List all payments (owner only)",
)
def list_all_payments(
    owner: OwnerUser,
    db: DbSession,
    payment_status: Annotated[
        PaymentStatus | None,
        Query(description="Optional status filter."),
    ] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> PaymentList:
    """Minimal authorized admin visibility into transactions (brief
    E): every row with user linkage, newest first. Owners only."""
    conds = []
    if payment_status is not None:
        conds.append(PostPayment.status == payment_status)
    total = db.scalar(select(func.count()).select_from(PostPayment).where(*conds)) or 0
    rows = db.scalars(
        select(PostPayment)
        .where(*conds)
        .order_by(PostPayment.created_at.desc(), PostPayment.id.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return PaymentList(
        total=total, offset=offset, limit=limit, results=[_payment_read(r) for r in rows]
    )


@admin_router.post(
    "/payments/{payment_id}/refund",
    response_model=PaymentRead,
    summary="Mark a succeeded payment refunded (owner only, record-only)",
)
def refund_payment(payment_id: UUID, owner: OwnerUser, db: DbSession) -> PaymentRead:
    """Record a refund for a SUCCEEDED payment (confirmed duplicates or
    other approved cases). Record-only until a real provider exists: no
    money moves - the row state IS the mechanism, and REFUND_TERMS says
    exactly that (no promised processing). Refunding does NOT restore
    free posts and does NOT unpublish anything (documented); only
    succeeded rows refund (409 otherwise)."""
    row = db.scalar(select(PostPayment).where(PostPayment.id == payment_id))
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found.",
        )
    if row.status != PaymentStatus.SUCCEEDED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Only succeeded payments can be refunded (current: '{row.status}').",
        )
    row.status = PaymentStatus.REFUNDED
    db.commit()
    db.refresh(row)
    return _payment_read(row)


@admin_router.get(
    "/policy/billing",
    response_model=BillingPolicyRead,
    summary="Read the billing policy (owner only)",
)
def read_billing_policy_admin(owner: OwnerUser, db: DbSession) -> BillingPolicyRead:
    """Owner view of the effective pricing (same shape as the user
    policy view, with the owner's own free-post counters)."""
    return _policy_view(owner, db)


@admin_router.patch(
    "/policy/billing",
    response_model=BillingPolicyRead,
    summary="Change the billing policy (owner only)",
)
def update_billing_policy(
    owner: OwnerUser, db: DbSession, body: BillingPolicyUpdate
) -> BillingPolicyRead:
    """Owner-only pricing write: validated non-negative integers, rate
    limited like the social-policy endpoint, audited per key
    (who/when/old/new) via `setting_changes`. Changing the price never
    rewrites past payments or restores consumed free posts - history is
    immutable."""
    check_rate_limit(
        f"policy-change:{owner.id}",
        limit=5,
        window_seconds=3600,
    )
    try:
        set_billing_policy(
            db,
            price_paise=body.price_paise,
            free_posts=body.free_posts,
            changed_by=owner.id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    db.commit()
    return _policy_view(owner, db)
