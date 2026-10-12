"""Schemas for the social surface (Phase 6b placeholder).

Plain language: travel-buddy discovery, messaging, and events belong to
Phase 7+. This phase ships ONE route - GET /social/discovery - purely so
the identity-verification gate has a real endpoint to protect (and real
API tests to prove denial). It returns an empty list plus an honest
message; Phase 7 replaces this file with actual discovery shapes.
"""

from typing import Any

from pydantic import BaseModel, Field


class DiscoveryResponse(BaseModel):
    """Placeholder discovery payload.

    `profiles` stays empty until Phase 7 implements matching - there is no
    user-search system yet, and inventing fake profiles here would be a
    fabricated result. `message` tells the client exactly that.
    """

    profiles: list[dict[str, Any]] = Field(default_factory=list)
    message: str
