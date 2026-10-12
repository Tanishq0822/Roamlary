"""Request/response schemas for the identity-verification workflow (Phase 6b).

Plain language: these shapes decide what clients may SEND and what the
API will say back about verification.

Rules enforced here:

1. STRICT BODIES: extra="forbid" everywhere a body exists. A client that
   tries `{"status": "verified"}`, `{"role": "owner"}`, or `{"user_id": ...}`
   gets 422 - self-elevation is impossible at the schema layer (the DB
   CHECK constraints are the second layer).

2. NO IDENTITY DATA: the submit body accepts at most an optional short
   `note` for the human reviewer. There is deliberately NO field for
   Aadhaar/ID numbers, documents, or scans - this phase is a labelled
   MANUAL-REVIEW workflow, not a real identity check.

3. OWNERSHIP: `VerificationStatusResponse` describes the CALLER'S OWN
   account only (the server derives it from the token, never from the
   body). Admin review shapes include another user's `user_id` +
   `display_name` and are reachable only through owner-gated routes.

4. UTC timestamps on the way out, matching every other response schema.
"""

from datetime import UTC, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

from app.models.enums import (
    UserRole,
    VerificationRequestStatus,
    VerificationStatus,
)


def _to_utc(value: datetime | None) -> datetime | None:
    """Normalize a datetime to UTC for the response (see community_report)."""
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class VerificationRequestCreate(BaseModel):
    """Body for POST /verification/requests.

    `note` is optional free text for the human reviewer (max 200 chars).
    Nothing else is accepted: no status, no user_id, no documents.
    """

    model_config = ConfigDict(extra="forbid")

    note: str | None = Field(None, max_length=200)

    @field_validator("note")
    @classmethod
    def strip_note(cls, value: str | None) -> str | None:
        """Trim; a blank note collapses to None (nothing to review)."""
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class VerificationRequestSummary(BaseModel):
    """The caller's own view of one request.

    `created_at` IS the submission time (the row is created exactly when
    the request is submitted); `reviewed_at`/`review_note` fill in later.
    `applicant_note` is what the caller wrote when submitting.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: VerificationRequestStatus
    created_at: datetime
    reviewed_at: datetime | None = None
    review_note: str | None = None
    applicant_note: str | None = None

    @field_serializer("created_at", "reviewed_at")
    def _serialize_utc(self, value: datetime | None) -> datetime | None:
        """Guarantee every timestamp leaves this API in UTC."""
        return _to_utc(value)


class VerificationStatusResponse(BaseModel):
    """GET /verification/status - the caller's OWN verification picture.

    `social_access_required` echoes the live effective policy so the client
    can explain the gate without a second request; it is global
    configuration, not private data. `role` discloses only the caller's
    OWN role (harmless, and lets an owner see their privileges); no route
    ever accepts a role from a request body.
    """

    verification_status: VerificationStatus
    role: UserRole
    social_access_required: bool
    latest_request: VerificationRequestSummary | None = None


class VerificationRequestReview(BaseModel):
    """Owner-only view of a request in the review queue.

    Includes `user_id`/`display_name` so the reviewer knows WHO they are
    reviewing - reachable only through owner-gated endpoints (never
    returned to other applicants).
    """

    id: UUID
    user_id: UUID
    display_name: str
    status: VerificationRequestStatus
    created_at: datetime
    reviewed_at: datetime | None = None
    reviewed_by: UUID | None = None
    review_note: str | None = None
    applicant_note: str | None = None

    @field_serializer("created_at", "reviewed_at")
    def _serialize_utc(self, value: datetime | None) -> datetime | None:
        """Guarantee every timestamp leaves this API in UTC."""
        return _to_utc(value)


class ReviewActionRequest(BaseModel):
    """Body for the owner's approve/reject decision.

    `review_note` is optional feedback the applicant will see (e.g. why it
    was rejected). No identity documents are involved at any point.
    """

    model_config = ConfigDict(extra="forbid")

    review_note: str | None = Field(None, max_length=200)

    @field_validator("review_note")
    @classmethod
    def strip_note(cls, value: str | None) -> str | None:
        """Trim; a blank note collapses to None."""
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class PolicyResponse(BaseModel):
    """Owner-only view of the social-verification policy."""

    key: str
    requires_verification: bool
    updated_at: datetime | None = None
    updated_by: UUID | None = None

    @field_serializer("updated_at")
    def _serialize_utc(self, value: datetime | None) -> datetime | None:
        """Guarantee the timestamp leaves this API in UTC."""
        return _to_utc(value)


class PolicyUpdateRequest(BaseModel):
    """Body for PATCH /admin/policy/social-verification (owner only).

    Exactly one boolean, nothing else. The server records who/when/old/new
    via `setting_changes`; changing this never touches any user's
    verification_status.
    """

    model_config = ConfigDict(extra="forbid")

    requires_verification: bool
