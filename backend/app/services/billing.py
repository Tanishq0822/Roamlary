"""Pay-per-post authorization, charging, and verification (Phase 14).

Plain language: this is the ONE place publishing decisions are made.
Every eligible create endpoint calls `authorize_post()` AFTER all other
validation (so invalid requests never burn free posts or create payment
rows) and BEFORE inserting anything:

- free entitlement left  -> atomically consume ONE grant AND create the
  post AND record a zero-amount succeeded payment row, all in ONE
  transaction (rollback undoes the counter increment too).
- no free left, no payment given -> create a PENDING payment row and
  tell the endpoint to answer 402 with the price (the user sees the ₹10
  charge BEFORE confirming anything).
- no free left, payment given -> verify it is SUCCEEDED + unconsumed,
  consume it exactly once (compare-and-set), then create the post - all
  in ONE transaction.

The provider surface (`BillingProvider`) has two implementations:
`NullProvider` (default - paid publishing stays pending/unavailable,
never faked) and `MockProvider` (tests only - deterministic, no
network). A real provider plugs in behind BILLING_PROVIDER without
touching callers. Client-supplied "success" is impossible by
construction: no route marks payments successful except provider
verification (mock test tokens are verified server-side).
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.billing_policy import CURRENCY, get_billing_policy
from app.core.config import settings
from app.models.enums import PaymentStatus
from app.models.post_payment import POST_CATEGORIES, PostPayment


def _now() -> datetime:
    return datetime.now(UTC)


class PaymentRequiredError(Exception):
    """Raised when publishing needs a confirmed payment first.

    Carries the PENDING payment row so the endpoint can answer 402 with
    the exact charge (amount, currency, free status) - the price display
    BEFORE confirmation the brief demands.
    """

    def __init__(self, payment: PostPayment, free_used: int, free_total: int) -> None:
        super().__init__("Payment required before publishing.")
        self.payment = payment
        self.free_used = free_used
        self.free_total = free_total


def raise_payment_required(error: PaymentRequiredError) -> None:
    """Answer 402 with the structured charge (never publishes).

    The detail dict is the price display: what will be charged (0 means
    unreachable here - free grants never raise), in what currency, the
    payment to confirm, and the free-post state. Clients confirm by
    paying (POST /billing/payments/{id}/pay) and re-submitting the
    original create WITH the succeeded payment_id.
    """
    from fastapi import status as _status

    payment = error.payment
    raise HTTPException(
        status_code=_status.HTTP_402_PAYMENT_REQUIRED,
        detail={
            "message": (
                f"This post costs {payment.amount_paise} paise ({payment.currency}): "
                "confirm the payment below, then re-submit your post with the "
                "succeeded payment_id."
            ),
            "payment_id": str(payment.id),
            "amount_paise": payment.amount_paise,
            "currency": payment.currency,
            "free_used": error.free_used,
            "free_total": error.free_total,
        },
    )


class BillingProvider:
    """Charge-verification surface. `verify` confirms a payment against
    provider data and returns (ok, receipt_or_error). Must never crash
    on provider faults (return ok=False instead)."""

    name = "none"

    def verify(self, *, payment: PostPayment, provider_token: str) -> tuple[bool, str]:
        """Verify a payer-supplied token for a PENDING payment."""
        return False, f"No {self.name} billing provider is configured."


class NullProvider(BillingProvider):
    """Default provider: paid publishing stays pending/unavailable."""

    name = "unconfigured"

    def verify(self, *, payment: PostPayment, provider_token: str) -> tuple[bool, str]:
        """Never confirms: without a provider there is nothing to verify
        against, and pretending otherwise would fake a charge."""
        return False, "No billing provider is configured for payment verification."


class MockProvider(BillingProvider):
    """Deterministic test provider (no network, no money).

    Accepts exactly the token f"mock-ok-{payment.id}" for a PENDING
    payment of the same row; anything else fails. The token shape binds
    the confirmation to ONE payment row, so a token can never confirm a
    different payment (replay across rows fails loudly).
    """

    name = "mock"

    def verify(self, *, payment: PostPayment, provider_token: str) -> tuple[bool, str]:
        """Check the test token against this exact payment row."""
        expected = f"mock-ok-{payment.id}"
        if provider_token != expected:
            return False, "Mock provider rejected the token."
        if payment.status != PaymentStatus.PENDING:
            return False, f"Mock provider only confirms pending payments (is '{payment.status}')."
        return True, f"mock-receipt-{payment.id}"


def select_billing_provider() -> BillingProvider:
    """Central provider selection (the only place configuration maps to
    a provider). `mock` is for tests; anything else (including the
    `none` default) is explicitly unverified - a real provider plugs in
    here without touching callers."""
    if (settings.billing_provider or "none").strip().lower() == "mock":
        return MockProvider()
    return NullProvider()


def consume_free_grant(db: Session, *, user_id: UUID, free_total: int) -> bool:
    """Atomically consume ONE free post (conditional UPDATE).

    Returns True exactly once per available grant: the WHERE clause
    carries the counter check, so two concurrent first-posts cannot both
    win (compare-and-set - the loser sees rowcount 0). Must be called
    inside the caller's transaction (the post insert + payment record
    join the same commit - rollback restores the grant).
    """
    from app.models.user import User

    result = db.execute(
        update(User)
        .where(User.id == user_id, User.free_posts_used < free_total)
        .values(free_posts_used=User.free_posts_used + 1)
    )
    return result.rowcount == 1


def authorize_post(
    db: Session,
    *,
    user,
    category: str,
    payment_id: UUID | None,
    idempotency_key: str | None = None,
) -> PostPayment | None:
    """Decide how this publishing attempt is funded (free grant, an
    existing SUCCEEDED payment, or a new PENDING payment via 402).

    Returns the funding payment row to record against the post:
    - a zero-amount SUCCEEDED 'free' row (grant just consumed), or
    - the caller-supplied SUCCEEDED payment (unconsumed - the endpoint
      consumes it atomically with the post insert via
      `consume_payment()`), or
    - raises PaymentRequiredError with a fresh PENDING row (endpoint
      answers 402; NOTHING is published).

    Raises 422 for unknown categories; 404 for unknown/foreign
    payments; 409 for non-payable payment states. Never publishes.
    """
    if category not in POST_CATEGORIES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown post category: {category}.",
        )
    price_paise, free_total = get_billing_policy(db)
    free_used = user.free_posts_used or 0

    if payment_id is None and free_used < free_total:
        # Fast path attempt: consume ONE grant. A concurrent first-post
        # may have taken it between our read and this statement - then
        # rowcount 0 and we fall through to the paid path (never 500).
        if consume_free_grant(db, user_id=user.id, free_total=free_total):
            free_row = PostPayment(
                user_id=user.id,
                category=category,
                amount_paise=0,
                currency=CURRENCY,
                status=PaymentStatus.SUCCEEDED,
                provider="none",
                idempotency_key=f"free:{user.id}:{uuid4().hex}",
            )
            db.add(free_row)
            db.flush()  # id available for the endpoint; commits with the post
            return free_row
        free_used = free_total  # lost the race: fall through to paid

    if payment_id is None:
        payment = PostPayment(
            user_id=user.id,
            category=category,
            amount_paise=price_paise,
            currency=CURRENCY,
            status=PaymentStatus.PENDING,
            provider=select_billing_provider().name,
            idempotency_key=idempotency_key or f"pay:{user.id}:{category}:{uuid4().hex}",
        )
        db.add(payment)
        try:
            db.flush()
        except IntegrityError as exc:
            # Same idempotency key raced: return THE row (UNIQUE index
            # is the idempotency truth, not us).
            db.rollback()
            payment = db.scalar(
                select(PostPayment).where(PostPayment.idempotency_key == payment.idempotency_key)
            )
            if payment is None:  # pragma: no cover - defensive
                raise
            if payment.user_id != user.id or payment.status != PaymentStatus.PENDING:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="A payment already exists for this request.",
                ) from None
            raise PaymentRequiredError(payment, free_used, free_total) from exc
        raise PaymentRequiredError(payment, free_used, free_total)

    payment = db.scalar(
        select(PostPayment).where(PostPayment.id == payment_id, PostPayment.user_id == user.id)
    )
    if payment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found.",
        )
    if payment.category != category:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That payment belongs to a different post category.",
        )
    if payment.status != PaymentStatus.SUCCEEDED or payment.consumed_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That payment cannot fund publishing (not succeeded, or already used).",
        )
    return payment


def consume_payment(
    db: Session, *, payment: PostPayment, subject_type: str, subject_id: UUID
) -> None:
    """Mark a SUCCEEDED payment consumed by exactly one post
    (compare-and-set on consumed_at IS NULL). Raises 409 if another
    request consumed it first. Called inside the post-creation
    transaction (same commit as the post row)."""
    result = db.execute(
        update(PostPayment)
        .where(
            PostPayment.id == payment.id,
            PostPayment.status == PaymentStatus.SUCCEEDED,
            PostPayment.consumed_at.is_(None),
        )
        .values(subject_type=subject_type, subject_id=subject_id, consumed_at=_now())
    )
    if result.rowcount != 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That payment was already used for another post.",
        )


def pay_pending_payment(db: Session, *, payment: PostPayment, provider_token: str) -> PostPayment:
    """Verify a PENDING or FAILED payment via the configured provider
    (attempts+1).

    Success flips to SUCCEEDED with the provider receipt (UNIQUE -
    webhook duplicates land here too); failure records the error and
    keeps the row payable for another attempt (failed never unlocks).
    Cancelled/refunded/succeeded rows are 409 (no double-confirm, no
    resurrecting, no re-confirming consumed rows).
    """
    if payment.status not in (PaymentStatus.PENDING, PaymentStatus.FAILED):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(f"Only pending or failed payments can be paid (current: '{payment.status}')."),
        )
    provider = select_billing_provider()
    ok, receipt = provider.verify(payment=payment, provider_token=provider_token)
    payment.attempts = (payment.attempts or 0) + 1
    if ok:
        payment.status = PaymentStatus.SUCCEEDED
        payment.provider = provider.name
        payment.provider_reference = receipt
        payment.last_error = None
    else:
        payment.status = PaymentStatus.FAILED
        payment.last_error = receipt
    try:
        db.commit()
    except IntegrityError as exc:
        # Duplicate webhook receipt raced: the UNIQUE reference kept one.
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That provider reference is already recorded.",
        ) from exc
    db.refresh(payment)
    return payment
