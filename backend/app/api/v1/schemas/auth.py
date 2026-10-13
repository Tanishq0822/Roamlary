"""Request and response schemas for authentication (Phase 3).

Plain language: Pydantic schemas are the "shapes" of the data the API
accepts and returns. They do three jobs: they validate and normalize
incoming data, they document the API, and - just as important here - they
decide which fields are VISIBLE to a client. `UserProfile` deliberately
omits `password_hash`, so the hash can never leak in a response.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class RegisterRequest(BaseModel):
    """Body for POST /auth/register.

    `extra="forbid"` makes this a STRICT schema: any field that is not
    display_name/email/password/device_label (for example a smuggled `id`,
    `password_hash`, or `firebase_uid`) is rejected with a 422 validation
    error instead of being silently ignored. That turns accidental API
    misuse into a visible error and keeps privileged fields impossible to
    inject through this endpoint.
    """

    model_config = ConfigDict(extra="forbid")

    display_name: str = Field(..., min_length=1, max_length=80)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    # Optional user-supplied session label ("my phone"). Purely a display
    # aid for the session list (Phase 8); nothing is collected
    # automatically, and a blank label is stored as NULL.
    device_label: str | None = Field(None, max_length=80)

    @field_validator("display_name")
    @classmethod
    def strip_display_name(cls, value: str) -> str:
        """Trim surrounding whitespace from the display name."""
        stripped = value.strip()
        if not stripped:
            raise ValueError("display_name must not be blank")
        return stripped

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        """Normalize email: trim + lowercase, so 'A@B.com' == 'a@b.com'."""
        return value.strip().lower()

    @field_validator("device_label")
    @classmethod
    def clean_device_label(cls, value: str | None) -> str | None:
        """Trim the label; a blank label is stored as NULL."""
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class LoginRequest(BaseModel):
    """Body for POST /auth/login.

    Strict schema (`extra="forbid"`), same rationale as RegisterRequest:
    unknown fields are a 422, never silently dropped.
    """

    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str = Field(..., min_length=1, max_length=128)
    # Optional user-supplied session label, same meaning as on register.
    device_label: str | None = Field(None, max_length=80)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("device_label")
    @classmethod
    def clean_device_label(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class TokenResponse(BaseModel):
    """Successful login/register response."""

    access_token: str
    token_type: str = "bearer"


class AuthSessionRead(BaseModel):
    """One login session as its owner sees it (Phase 8).

    `current` marks the session behind the calling token. Timestamps
    leave the API as UTC ISO strings (the Phase 4 convention), so SQLite
    and PostgreSQL render identically.
    """

    model_config = ConfigDict(extra="forbid")

    id: UUID
    label: str | None
    created_at: str
    revoked_at: str | None
    current: bool


class AuthSessionList(BaseModel):
    """The caller's own sessions, newest first."""

    model_config = ConfigDict(extra="forbid")

    total: int
    sessions: list[AuthSessionRead]


class UserProfile(BaseModel):
    """The PUBLIC profile shape returned by the API.

    Notice what is missing: `password_hash` and `firebase_uid`. Fields are
    only exposed here if the client is meant to see them. `model_config`
    with from_attributes lets FastAPI build this from a SQLAlchemy object.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    display_name: str
    email: str | None
    created_at: datetime
    updated_at: datetime


class UserProfileUpdate(BaseModel):
    """Body for PATCH /users/me - only fields a user may self-edit.

    `extra="forbid"` makes any unknown field (e.g. `id`, `password_hash`,
    `firebase_uid`) a 422 validation error instead of being silently
    ignored, so protected fields cannot be smuggled in.
    """

    model_config = ConfigDict(extra="forbid")

    display_name: str | None = Field(None, min_length=1, max_length=80)

    @field_validator("display_name")
    @classmethod
    def strip_display_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("display_name must not be blank")
        return stripped
