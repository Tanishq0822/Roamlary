"""Request and response schemas for trusted contacts (Phase 4).

Plain language: these are the "shapes" of data the trusted-contact API
accepts and returns. Three rules are enforced here rather than in the
route handlers, because validation belongs as close to the data as
possible:

1. `user_id` is NOT a field on any request schema, and every request
   schema uses extra="forbid". A client that tries to send `user_id`
   (or `id`, or `created_at`) gets a 422 instead of it being silently
   dropped. Ownership is always assigned server-side from the JWT.
2. Phone numbers are normalized to one consistent stored form so the
   same number always looks the same in the database.
3. The response schemas are the ONLY fields a client ever sees - no
   internal columns can leak because they simply are not listed here.
"""

import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

# A phone number, after cleanup: an optional leading '+' then 7-15
# digits. 15 digits is the international maximum (E.164). We deliberately
# do NOT assume any country code - Roamlary users are travelers, so a
# number is stored exactly as the user wrote it (minus separators).
_PHONE_RE = re.compile(r"^\+?\d{7,15}$")

# Characters we strip from a phone number before validating: spaces,
# dashes, parentheses, and dots. Everything else must already be a digit
# or a leading '+'.
_PHONE_SEPARATORS = re.compile(r"[\s\-\(\)\.]")


class TrustedContactCreate(BaseModel):
    """Body for POST /trusted-contacts.

    Required: name and phone (a contact with no reachable number is
    useless for safety). Optional: relationship label and email.
    `extra="forbid"` rejects attempts to smuggle `user_id` or `id`.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=80)
    phone: str = Field(..., min_length=1, max_length=32)
    relationship: str | None = Field(None, max_length=50)
    email: EmailStr | None = None

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        """Trim whitespace; a blank name is not a name."""
        stripped = value.strip()
        if not stripped:
            raise ValueError("name must not be blank")
        return stripped

    @field_validator("phone")
    @classmethod
    def normalize_phone(cls, value: str) -> str:
        """Normalize the phone number to a single canonical stored form.

        Policy (applies identically on create and update):
        - Strip spaces, dashes, parentheses, and dots (common formatting).
        - Keep a leading '+' if present (international prefix).
        - The result must be '+' and/or 7-15 digits.
        No country code is added or assumed. A value that does not match
        after cleanup is rejected with 422 - we never store a number we
        would not know how to read back.
        """
        cleaned = _PHONE_SEPARATORS.sub("", value.strip())
        if not _PHONE_RE.match(cleaned):
            raise ValueError(
                "phone must be 7-15 digits, optionally starting with '+' "
                "(separators like spaces or dashes are allowed and removed)"
            )
        return cleaned

    @field_validator("relationship")
    @classmethod
    def strip_relationship(cls, value: str | None) -> str | None:
        """Trim; an empty label becomes None (unset), not an empty string."""
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str | None) -> str | None:
        """Trim + lowercase, matching the user-account email policy."""
        if value is None:
            return None
        return value.strip().lower()


class TrustedContactUpdate(BaseModel):
    """Body for PATCH /trusted-contacts/{contact_id}.

    Every field is optional (send only what you want to change).
    `user_id`, `id`, and timestamps are absent AND extra="forbid", so
    they cannot be injected. Phone uses the same normalization as create.
    """

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(None, min_length=1, max_length=80)
    phone: str | None = Field(None, min_length=1, max_length=32)
    relationship: str | None = Field(None, max_length=50)
    email: EmailStr | None = None

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("name must not be blank")
        return stripped

    @field_validator("phone")
    @classmethod
    def normalize_phone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = _PHONE_SEPARATORS.sub("", value.strip())
        if not _PHONE_RE.match(cleaned):
            raise ValueError(
                "phone must be 7-15 digits, optionally starting with '+' "
                "(separators like spaces or dashes are allowed and removed)"
            )
        return cleaned

    @field_validator("relationship")
    @classmethod
    def strip_relationship(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip().lower()


class TrustedContactRead(BaseModel):
    """The public shape of a trusted contact.

    Exactly the approved fields - `password_hash`, database internals,
    and anything else are impossible to leak because they are not
    declared here.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    name: str
    phone: str
    relationship: str | None = None
    email: str | None = None
    created_at: datetime
    updated_at: datetime
