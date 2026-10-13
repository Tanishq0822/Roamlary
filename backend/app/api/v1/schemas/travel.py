"""Request and response schemas for the travel surface (Phase 7).

Plain language: these classes are the API's doorman - they decide what
a client may SEND (strict validation, `extra="forbid"` so unknown fields
are rejected instead of silently ignored) and exactly what a client
EVER SEES BACK (closed response models, so a field like `email` can
never leak into discovery by accident).

PRIVACY RULES ENFORCED HERE:
- No schema in this file contains the account email, phone, password
  hash, firebase uid, role, or verification status. Discovery and public
  profiles expose only the travel fields a traveller chose to publish.
- Profile lists (languages/interests/styles) are length-bounded and
  (for interests/styles) checked against the closed sets in
  `app/core/matching.py`, so a client cannot store arbitrary blobs.
- Profile text fields are bounded (nickname 40, bio 200, region 80) -
  this is a travel companion app, not a data-harvesting form.
- Plan dates validate end >= start; destinations are trimmed +
  whitespace-collapsed and length-bounded, and are NEVER presented as
  externally verified (they are free text normalized for matching).
- `min_score` is 0-100, `limit` is 1-100 (page-size ceiling), matching
  the pagination conventions of the rest of the API.
"""

from datetime import date
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.matching import ALLOWED_INTERESTS, ALLOWED_TRAVEL_STYLES
from app.models.enums import BuddyRequestStatus, PlanVisibility, TravelPlanStatus

# Preference-list bounds (kept here so schemas and docs agree).
MAX_LANGUAGES = 8
MAX_INTERESTS = 12
MAX_TRAVEL_STYLES = 6


def _clean_optional_text(value: str | None) -> str | None:
    """Trim + collapse whitespace; empty-after-strip becomes None."""
    if value is None:
        return None
    cleaned = " ".join(value.split())
    return cleaned or None


def _validated_list(
    values: list[str] | None,
    *,
    max_items: int,
    allowed: frozenset[str] | None,
    label: str,
) -> list[str] | None:
    """Normalize a preference list: trim, dedupe preserving order, bound.

    When `allowed` is given, every value must be a member (checked after
    lowercasing) - the closed sets are the documented vocabulary.
    """
    if values is None:
        return None
    seen: list[str] = []
    for raw in values:
        item = " ".join(raw.split()).casefold()
        if not item:
            continue
        if allowed is not None and item not in allowed:
            raise ValueError(f"unsupported {label} '{item}'")
        if item not in seen:
            seen.append(item)
    if len(seen) > max_items:
        raise ValueError(f"at most {max_items} {label} values are allowed")
    return seen


# --- Travel profile -------------------------------------------------------


class TravelProfileBase(BaseModel):
    """Shared editable fields for create/update/read."""

    model_config = ConfigDict(extra="forbid")

    travel_nickname: str | None = Field(None, max_length=40)
    bio: str | None = Field(None, max_length=200)
    home_region: str | None = Field(None, max_length=80)
    languages: list[str] | None = None
    travel_styles: list[str] | None = None
    interests: list[str] | None = None
    group_size_pref: int | None = Field(None, ge=2, le=12)
    discoverable: bool = False

    @field_validator("travel_nickname", "bio", "home_region")
    @classmethod
    def _clean_text(cls, value: str | None) -> str | None:
        return _clean_optional_text(value)

    @field_validator("languages")
    @classmethod
    def _check_languages(cls, value: list[str] | None) -> list[str] | None:
        # Languages are a free list (too many to enumerate): bounded in
        # count and per-item length only.
        if value is None:
            return None
        cleaned = _validated_list(value, max_items=MAX_LANGUAGES, allowed=None, label="language")
        for item in cleaned or []:
            if len(item) < 2 or len(item) > 24:
                raise ValueError("each language must be 2-24 characters")
        return cleaned

    @field_validator("travel_styles")
    @classmethod
    def _check_styles(cls, value: list[str] | None) -> list[str] | None:
        return _validated_list(
            value, max_items=MAX_TRAVEL_STYLES, allowed=ALLOWED_TRAVEL_STYLES, label="travel style"
        )

    @field_validator("interests")
    @classmethod
    def _check_interests(cls, value: list[str] | None) -> list[str] | None:
        return _validated_list(
            value, max_items=MAX_INTERESTS, allowed=ALLOWED_INTERESTS, label="interest"
        )


class TravelProfileCreate(TravelProfileBase):
    """Body for POST /travel-profile. `discoverable` defaults to hidden."""


class TravelProfilePatch(TravelProfileBase):
    """Body for PATCH /travel-profile (partial update).

    Every field is optional; omitted fields keep their stored value. An
    explicit `null` CLEARS optional fields (or `[]` empties a list). A
    profile-update request can never touch role, verification status, or
    any account field - those have no counterpart in this schema.
    """

    travel_nickname: str | None = Field(None, max_length=40)
    bio: str | None = Field(None, max_length=200)
    home_region: str | None = Field(None, max_length=80)
    languages: list[str] | None = None
    travel_styles: list[str] | None = None
    interests: list[str] | None = None
    group_size_pref: int | None = Field(None, ge=2, le=12)
    discoverable: bool | None = None


class TravelProfileRead(BaseModel):
    """Own travel profile, including computed completion state.

    `completion` lists the still-empty recommended fields; it is a
    guidance hint ONLY and is deliberately decoupled from identity
    verification - completing a profile never verifies an account.
    """

    model_config = ConfigDict(extra="forbid")

    user_id: UUID
    travel_nickname: str | None
    bio: str | None
    home_region: str | None
    languages: list[str] | None
    travel_styles: list[str] | None
    interests: list[str] | None
    group_size_pref: int | None
    discoverable: bool
    completion: list[str]
    created_at: str
    updated_at: str


# --- Travel plans ---------------------------------------------------------


class TravelPlanCreate(BaseModel):
    """Body for POST /travel-plans.

    Destination/region are free text (trimmed, normalized server-side for
    matching - never claimed to be externally verified). Dates must form
    a valid range; a past START is allowed (an ongoing trip is real), but
    `end_date` must not precede `start_date`.
    """

    model_config = ConfigDict(extra="forbid")

    destination: str = Field(min_length=2, max_length=80)
    region: str | None = Field(None, max_length=80)
    start_date: date
    end_date: date
    flexible_dates: bool = False
    visibility: PlanVisibility = PlanVisibility.PRIVATE

    @field_validator("destination", "region")
    @classmethod
    def _clean_place(cls, value: str | None) -> str | None:
        cleaned = _clean_optional_text(value)
        if cleaned is None:
            raise ValueError("must not be blank")
        if len(cleaned) < 2:
            raise ValueError("must be at least 2 characters")
        return cleaned

    @field_validator("end_date")
    @classmethod
    def _check_range(cls, value: date, info) -> date:
        start = info.data.get("start_date")
        if start is not None and value < start:
            raise ValueError("end_date must not precede start_date")
        return value


class TravelPlanPatch(BaseModel):
    """Body for PATCH /travel-plans/{plan_id} (partial update).

    Status moves are explicit client intent (active/paused/completed);
    there is no server-side automatic completion - expiry is evaluated
    at read time instead, so no background job is silently required.
    """

    model_config = ConfigDict(extra="forbid")

    destination: str | None = Field(None, min_length=2, max_length=80)
    region: str | None = Field(None, max_length=80)
    start_date: date | None = None
    end_date: date | None = None
    flexible_dates: bool | None = None
    status: TravelPlanStatus | None = None
    visibility: PlanVisibility | None = None

    @field_validator("destination", "region")
    @classmethod
    def _clean_place(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = _clean_optional_text(value)
        if cleaned is None:
            raise ValueError("must not be blank")
        if len(cleaned) < 2:
            raise ValueError("must be at least 2 characters")
        return cleaned


class TravelPlanRead(BaseModel):
    """A travel plan as its owner sees it (or as discovery summarizes it).

    `created_at`/`updated_at` are omitted (null) in discovery/public
    projections, which only need the trip facts; the owner's own
    endpoints always include them.
    """

    model_config = ConfigDict(extra="forbid")

    id: UUID
    destination: str
    region: str | None
    start_date: date
    end_date: date
    flexible_dates: bool
    status: TravelPlanStatus
    visibility: PlanVisibility
    created_at: str | None = None
    updated_at: str | None = None


# --- Discovery ------------------------------------------------------------


class DiscoveryCandidateRead(BaseModel):
    """One discovery result: a LIMITED public travel profile + best plan.

    Deliberately absent: email, phone, role, verification status,
    account timestamps, and the candidate's private or inactive plans.
    The compatibility score is a deterministic heuristic over travel
    logistics and stated preferences - NOT a safety or personality
    guarantee, and it must never be presented as one.
    """

    model_config = ConfigDict(extra="forbid")

    user_id: UUID
    display_name: str
    bio: str | None
    home_region: str | None
    languages: list[str] | None
    travel_styles: list[str] | None
    interests: list[str] | None
    group_size_pref: int | None
    plan: TravelPlanRead
    compatibility_score: int = Field(ge=0, le=100)
    match_breakdown: dict[str, int]
    existing_request: str = Field(
        description=(
            "Request state between the searcher and this candidate: "
            "'none', 'pending_sent', 'pending_received', or 'accepted'."
        )
    )


class DiscoveryPage(BaseModel):
    """Paginated discovery response with an explicit honesty note."""

    model_config = ConfigDict(extra="forbid")

    total: int = Field(description="Distinct matching candidates after filters and dedupe.")
    offset: int
    limit: int
    results: list[DiscoveryCandidateRead]
    note: str


class PublicTravelProfileRead(BaseModel):
    """Limited public profile for GET /travel-buddies/{user_id}.

    Shows only the target's discoverable, active, non-expired plans and
    their published travel fields - never their private plans, account
    data, or verification state.
    """

    model_config = ConfigDict(extra="forbid")

    user_id: UUID
    display_name: str
    bio: str | None
    home_region: str | None
    languages: list[str] | None
    travel_styles: list[str] | None
    interests: list[str] | None
    group_size_pref: int | None
    plan: TravelPlanRead


# --- Travel-partner requests ----------------------------------------------


class BuddyRequestCreate(BaseModel):
    """Body for POST /travel-buddies/requests.

    `plan_id` (optional) names the RECIPIENT's plan the requester saw in
    discovery, giving the request context. It is validated server-side:
    it must belong to the recipient and be discoverable/active/unexpired
    at send time.

    `payment_id` (optional, Phase 14) funds publishing with a SUCCEEDED
    payment: first posts are free (no payment needed); later posts
    answer 402 with a payment to confirm, then re-submit WITH its id.
    `idempotency_key` (optional) guards double-clicks/retries.
    """

    model_config = ConfigDict(extra="forbid")

    recipient_id: UUID
    plan_id: UUID | None = None
    payment_id: UUID | None = None
    idempotency_key: str | None = Field(None, max_length=100)


class BuddyRequestRead(BaseModel):
    """One travel-partner request, visible to its two parties only.

    Display names are the public travel names of each side (nickname or
    account display name) - never emails. `plan_destination`/dates are
    the context plan summary when the request is trip-specific.
    """

    model_config = ConfigDict(extra="forbid")

    id: UUID
    requester_id: UUID
    requester_display_name: str
    recipient_id: UUID
    recipient_display_name: str
    plan_id: UUID | None
    plan_destination: str | None
    plan_start_date: date | None
    plan_end_date: date | None
    status: BuddyRequestStatus
    created_at: str
    updated_at: str
    responded_at: str | None


class BuddyRequestList(BaseModel):
    """Paginated request list for the incoming or outgoing tab."""

    model_config = ConfigDict(extra="forbid")

    total: int
    offset: int
    limit: int
    results: list[BuddyRequestRead]


__all__ = [
    "BuddyRequestCreate",
    "BuddyRequestList",
    "BuddyRequestRead",
    "DiscoveryCandidateRead",
    "DiscoveryPage",
    "PublicTravelProfileRead",
    "TravelPlanCreate",
    "TravelPlanPatch",
    "TravelPlanRead",
    "TravelProfileCreate",
    "TravelProfilePatch",
    "TravelProfileRead",
]
