"""Block request/response schemas (Phase 8).

Plain language: blocking is a one-way safety switch ("I want nothing
from them"). The list a user sees contains ONLY blocks THEY created -
nobody can read anyone else's list, and unblocking someone else's block
is impossible (the delete key is the blocked id scoped to the caller).
"""

from uuid import UUID

from pydantic import BaseModel, ConfigDict


class BlockCreate(BaseModel):
    """Body for POST /blocks. Exactly one field: who to block."""

    model_config = ConfigDict(extra="forbid")

    blocked_id: UUID


class BlockRead(BaseModel):
    """One block row as the blocker sees it.

    The blocked account's display name is included (needed to manage the
    list); nothing else about them travels - no email, role, status, or
    timestamps of their account.
    """

    model_config = ConfigDict(extra="forbid")

    id: UUID
    blocked_id: UUID
    blocked_display_name: str
    created_at: str


class BlockList(BaseModel):
    """The caller's own block list, newest first."""

    model_config = ConfigDict(extra="forbid")

    total: int
    blocks: list[BlockRead]
