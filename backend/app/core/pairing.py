"""Canonical unordered user-pair helper (Phase 8).

Plain language: many Phase 8 rules are about "these two users", with no
direction (a block stops BOTH directions; one conversation row covers the
pair; the Phase 7 cross-direction race fix keys on the pair). This module
reduces any two user IDs to ONE canonical (low, high) ordering so the
database sees a single key no matter who acted first.

Ordering is by UUID integer value. That matches the migration backfill
exactly: PostgreSQL LEAST/GREATEST on uuid and SQLite min/max on the
stored hex strings both order the same way (fixed-width hex sorts like
the integer), so rows written by old SQL and rows written by this helper
always agree.
"""

from uuid import UUID


def canonical_pair(first: UUID, second: UUID) -> tuple[UUID, UUID]:
    """Return (low, high) for two user IDs. Raises ValueError for a pair
    with itself (self-pairs are structurally impossible everywhere)."""
    if first == second:
        raise ValueError("A user pair cannot contain the same user twice.")
    low, high = (first, second) if first.int <= second.int else (second, first)
    return low, high
