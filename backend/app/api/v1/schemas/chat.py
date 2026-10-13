"""Message-request, conversation, and message schemas (Phase 8).

Plain language: a conversation row has no direction (one row per pair),
so reads always resolve "the OTHER user" relative to the caller. Sender
identity is NEVER accepted from a request body - the only sender field
any schema carries is the read-side `sender_id` the server filled in.
"""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MessageRequestCreate(BaseModel):
    """Body for POST /chat/requests. Who to ask, plus optional Phase 14
    payment funding (`payment_id` with a SUCCEEDED payment;
    `idempotency_key` against double-clicks). First asks are free."""

    model_config = ConfigDict(extra="forbid")

    recipient_id: UUID
    payment_id: UUID | None = None
    idempotency_key: str | None = Field(None, max_length=100)


class ConversationRead(BaseModel):
    """One conversation as a participant sees it.

    `other_user_id`/`other_display_name` resolve the pair relative to
    the caller (the row itself stores no direction). `requested_by_me`
    tells who sent the current ask (who may cancel it). Timestamps leave
    the API as UTC ISO strings (the Phase 4 convention).
    """

    model_config = ConfigDict(extra="forbid")

    id: UUID
    other_user_id: UUID
    other_display_name: str
    status: str
    requested_by_me: bool
    responded_at: str | None
    created_at: str
    updated_at: str


class ConversationList(BaseModel):
    """The caller's conversations, most recently active first."""

    model_config = ConfigDict(extra="forbid")

    total: int
    offset: int
    limit: int
    results: list[ConversationRead]


class MessageSend(BaseModel):
    """Body for POST /chat/conversations/{id}/messages. Text only."""

    model_config = ConfigDict(extra="forbid")

    body: str = Field(..., min_length=1, max_length=2000)

    @field_validator("body")
    @classmethod
    def strip_nonblank_body(cls, value: str) -> str:
        """Whitespace-only messages are empty messages (422)."""
        stripped = value.strip()
        if not stripped:
            raise ValueError("body must not be blank")
        return stripped


class MessageRead(BaseModel):
    """One message as a conversation participant sees it.

    `mine` marks messages the caller sent. A soft-deleted message keeps
    its place in history with `body=None` and `is_deleted=True` - the
    row is never removed, so history is never silently rewritten. No
    tokens, no account data, no unrelated conversation metadata travel
    here - only the message itself.
    """

    model_config = ConfigDict(extra="forbid")

    id: UUID
    conversation_id: UUID
    sender_id: UUID
    mine: bool
    body: str | None
    is_deleted: bool
    created_at: str


class MessageList(BaseModel):
    """Paginated history, stable order (created_at, id)."""

    model_config = ConfigDict(extra="forbid")

    total: int
    offset: int
    limit: int
    results: list[MessageRead]
