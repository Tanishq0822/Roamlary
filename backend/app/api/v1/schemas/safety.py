"""Safety disclosure, capabilities, and consent schemas (Phase 15).

Plain language: the disclosure endpoint serves the exact versioned text
the user acknowledges (draft pending legal review - labeled as such).
Consent reads show per-feature states plus the decision, version, and
expiry. The consent BODY carries independent per-feature flags (never
one broad checkbox) plus the disclosure version the user saw - stale
versions are refused so nobody acknowledges old text unknowingly.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SafetyDisclosureRead(BaseModel):
    """The current disclosure: version + draft text + feature catalog."""

    model_config = ConfigDict(extra="forbid")

    version: str
    text: str
    legal_review_pending: bool
    features: list[str]
    unavailable_features: list[str]


class SafetyCapabilitiesRead(BaseModel):
    """What safety support actually exists on this build (brief 15.A:
    only implemented capabilities are offered - the rest are named as
    unavailable, never silently omitted)."""

    model_config = ConfigDict(extra="forbid")

    trip_detail_sharing: str  # 'available'
    checkin_reminders: str  # 'available'
    sos_notify_attempts: str  # 'available'
    location_sharing: str  # 'unavailable'
    microphone_camera: str  # 'never'


class ConsentCreate(BaseModel):
    """Body for POST /safety/consents. One decision for one activity.

    `features` keys are the AVAILABLE_FEATURES names; unknown keys are
    422, and consenting to an unavailable feature (location sharing) is
    refused - consent can never authorize what does not exist.
    `decision` 'declined' records the risk acknowledgement with features
    off (never the absence of a row). `disclosure_version` must equal
    the current version (stale text is 409). `expires_at`, when given,
    must be future and timezone-aware.
    """

    model_config = ConfigDict(extra="forbid")

    subject_type: str = Field(..., min_length=1, max_length=20)
    subject_id: UUID
    features: dict[str, bool] = Field(default_factory=dict)
    decision: str = Field(..., min_length=1, max_length=20)
    disclosure_version: str = Field(..., min_length=1, max_length=20)
    expires_at: datetime | None = None


class ConsentRead(BaseModel):
    """One consent row as its owner (or authorized personnel) sees it."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    subject_type: str
    subject_id: UUID
    share_trip_details: bool
    checkin_reminders: bool
    sos_notify: bool
    decision: str
    disclosure_version: str
    expires_at: datetime | None
    created_at: datetime


class ConsentList(BaseModel):
    """Consent history (append-only), newest first."""

    model_config = ConfigDict(extra="forbid")

    total: int
    offset: int
    limit: int
    results: list[ConsentRead]
