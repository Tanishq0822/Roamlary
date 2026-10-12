"""Minimal in-process rate limiter for sensitive actions (Phase 6b).

Plain language: this is a small "counter with a cooldown" for dangerous
endpoints. It remembers, per key (e.g. "policy-change:<owner id>"), the
timestamps of recent attempts inside a sliding window; when a new attempt
would exceed `limit`, it raises 429 instead of doing the work.

Why so small: the project deliberately has NO rate-limiting infrastructure
(documented limitation), and the phase brief asks for "rate limiting or
other protections consistent with existing architecture". One dict, one
function, no new dependencies - that is the consistent scope. It protects
the policy-change endpoint (the most dangerous write in this phase).

Known limitation (documented, not hidden): state lives in THIS process's
memory. With multiple worker processes each worker counts separately, so
the real global limit can be `workers x limit`. A production deployment
needs a shared store (Redis etc.) - a later hardening phase.

The module-level dict is process-global on purpose (the window must
survive across requests), and `reset_rate_limits()` exists so tests start
from a clean slate instead of leaking state between cases.
"""

from __future__ import annotations

from collections import defaultdict
from time import monotonic

from fastapi import HTTPException, status

# key -> deque-like list of monotonic timestamps of accepted attempts.
_attempts: dict[str, list[float]] = defaultdict(list)

# Attempts are KEPT this long only so the window can slide correctly;
# entries older than (window + 1s) are pruned on every check.
_MAX_AGE_SECONDS = 600.0


def reset_rate_limits() -> None:
    """Forget all recorded attempts (test isolation only)."""
    _attempts.clear()


def check_rate_limit(key: str, *, limit: int, window_seconds: int) -> None:
    """Raise 429 if `key` already used `limit` attempts in the window.

    Uses a monotonic clock (immune to wall-clock jumps, unlike `time.time`)
    and prunes stale entries as it goes so the dict cannot grow unbounded.
    """
    now = monotonic()
    history = _attempts[key]
    # Drop attempts that have fully slid out of the window.
    cutoff = now - max(float(window_seconds), _MAX_AGE_SECONDS)
    history[:] = [t for t in history if t > cutoff]

    if len(history) >= limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(f"Too many attempts. Try again in {window_seconds} seconds."),
        )

    history.append(now)
