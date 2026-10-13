"""Billing schemas: policy view, payment reads, pay/cancel bodies (Phase 14).

Plain language: the policy view shows the price BEFORE the user
confirms anything (amount, currency, free-post state, provider
readiness, refund terms). Payment reads expose charge STATE, never
credentials. NO schema carries an amount from the client (amounts are
server-set) and NO schema can mark a payment successful (only provider
verification does that).
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class BillingPolicyRead(BaseModel):
    """The effective pay-per-post policy as the caller sees it.

    `free_remaining` and `next_charge_paise` (0 while free entitlement
    lasts, else the live price) are exactly what the UI shows before
    the user confirms publishing. `refund_terms` is the standing
    disclosure (record-only refunds without a real provider).
    """

    model_config = ConfigDict(extra="forbid")

    price_paise: int
    currency: str
    free_posts_total: int
    free_posts_used: int
    free_remaining: int
    next_charge_paise: int
    provider_configured: bool
    refund_terms: str


class PaymentRead(BaseModel):
    """One payment row as its payer (or the owner) sees it."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    category: str
    subject_type: str | None
    subject_id: UUID | None
    amount_paise: int
    currency: str
    status: str
    provider: str
    attempts: int
    last_error: str | None
    consumed_at: datetime | None
    created_at: datetime


class PaymentList(BaseModel):
    """Payment history, newest first (owner sees all, users see own)."""

    model_config = ConfigDict(extra="forbid")

    total: int
    offset: int
    limit: int
    results: list[PaymentRead]


class PaymentPay(BaseModel):
    """Body for POST /billing/payments/{id}/pay. The payer-supplied
    provider token (verified server-side; a wrong token fails the
    payment, never confirms it)."""

    model_config = ConfigDict(extra="forbid")

    provider_token: str = Field(..., min_length=1, max_length=200)


class BillingPolicyUpdate(BaseModel):
    """Body for PATCH /admin/policy/billing (owner only). Each field
    optional; provided values must be non-negative integers. A price of
    0 means "posting is currently free"; free_posts 0 means "no free
    entitlement" (every post is charged)."""

    model_config = ConfigDict(extra="forbid")

    price_paise: int | None = Field(None, ge=0)
    free_posts: int | None = Field(None, ge=0)


class WebhookEvent(BaseModel):
    """Body for POST /billing/webhook (mock provider, tests only).

    Carries the provider reference + outcome for a payment. Processed
    idempotently via the UNIQUE reference: duplicate deliveries return
    the SAME row state, never a second charge or post. Real providers
    MUST replace this endpoint with signed verification - this shape
    documents that requirement and refuses non-mock providers.
    """

    model_config = ConfigDict(extra="forbid")

    payment_id: UUID
    provider_reference: str = Field(..., min_length=1, max_length=120)
    outcome: str = Field(..., min_length=1, max_length=20)  # 'succeeded' | 'failed'
