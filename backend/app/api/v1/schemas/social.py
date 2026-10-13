"""Schemas for the social surface (Phase 6b gate + Phase 7 discovery).

Plain language: this file keeps the JSON contract Phase 6b shipped for
GET /social/discovery - `profiles` (a list) plus `message` (a string) -
so the already-committed UI keeps working unchanged. Phase 7 changed
ONLY the contents: `profiles` now carries real discovery candidates
(limited public travel profiles with their best plan and compatibility
score) instead of an empty list, and `message` carries an honest
description of what the score means (and does not mean).
"""

from typing import Any

from pydantic import BaseModel, Field


class DiscoveryResponse(BaseModel):
    """Broad discovery payload for GET /social/discovery.

    `profiles` is a list of limited public profiles (same shape as the
    `results` items of GET /travel-buddies/discover). `message` states
    plainly that scores are a deterministic ranking heuristic, never a
    safety guarantee - the client shows it verbatim.
    """

    profiles: list[dict[str, Any]] = Field(default_factory=list)
    message: str
