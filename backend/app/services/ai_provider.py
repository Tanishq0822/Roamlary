"""Modular AI travel companion with explicit failure behavior (Phase 13).

Plain language: one endpoint answers travel questions. The answers come
from a PROVIDER chosen by configuration - and when no provider is
configured (the normal state of this prototype), the API says so
explicitly (503-style unavailable) instead of fabricating an answer.
Safety rules baked in: no safety verdicts about people/places/events,
no invented hours/routes/statistics/numbers, uncertainty is stated, and
private records (messages, SOS, contacts, other users) are never sent
anywhere.

Architecture: `AIProvider` is the 3-method surface (name/configured/
answer). `UnavailableProvider` is the default; `MockProvider` gives
deterministic canned answers for tests (no paid calls, no network);
a real provider later implements the same surface behind
`AI_PROVIDER` + `AI_API_KEY` settings. Provider keys live server-side
only and never appear in responses.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from app.core.config import settings

# Hard ceilings: the request schema enforces most of these, the service
# re-checks defensively (never trust one layer alone for cost control).
MAX_QUESTION_CHARS = 2000
MAX_HISTORY_ITEMS = 10

# Static emergency footer. Deliberately number-free: fabricating local
# emergency numbers would violate the brief, so the guidance names the
# action, never a number.
EMERGENCY_FOOTER = (
    "If you are in immediate danger, contact your local emergency "
    "services right away and share your live location with a trusted contact."
)

# Uncertainty + no-safety-verdict disclaimers travel in EVERY answer.
HONESTY_FOOTER = (
    "This is general travel information, not verified advice: details "
    "may be outdated or incomplete. Nothing here certifies that any "
    "person, place, or event is safe."
)


@dataclass
class AIAnswer:
    """One structured companion answer (frontend-ready shape)."""

    answer: str
    verified: bool  # True only for retrieved (non-generated) content
    sources: list[str]  # provider/source names; empty when unavailable
    emergency_footer: str = EMERGENCY_FOOTER
    honesty_footer: str = HONESTY_FOOTER
    generated_at: str = ""

    def __post_init__(self) -> None:
        if not self.generated_at:
            self.generated_at = datetime.now(UTC).isoformat()


class AIProvider:
    """Answer surface every provider implements. No crashing: `answer`
    returns AIAnswer for success AND for handled failure (with
    verified=False and the reason inside the answer text)."""

    name = "none"

    @property
    def configured(self) -> bool:
        """Whether this provider can actually answer (keys + backend)."""
        return False

    def answer(self, *, question: str, context: str, timeout_seconds: int) -> AIAnswer:
        """Answer with trip context. Must never raise for provider faults."""
        raise NotImplementedError


class UnavailableProvider(AIProvider):
    """Default provider: explicitly unavailable, never fabricated."""

    name = "unavailable"

    def answer(self, *, question: str, context: str, timeout_seconds: int) -> AIAnswer:
        """Return the documented unavailable response (verified=False)."""
        return AIAnswer(
            answer=(
                "The AI travel companion is not configured on this server "
                "(no AI provider or API key). Your question was not answered "
                "and nothing was sent anywhere. An administrator can enable "
                "it by setting AI_PROVIDER and AI_API_KEY."
            ),
            verified=False,
            sources=[],
        )


class MockProvider(AIProvider):
    """Deterministic canned answers for tests (no network, no cost).

    Echoes the question shape with fixed guidance blocks so tests can
    assert structure, context use, disclaimers, and failure paths
    without paid API calls.
    """

    name = "mock"

    @property
    def configured(self) -> bool:
        return True

    def answer(self, *, question: str, context: str, timeout_seconds: int) -> AIAnswer:
        """Canned structured answer referencing the trip context given."""
        lines = [
            f"Mock travel guidance for: {question[:120]}",
            "General preparation: check documents, pack for the season, "
            "keep bookings offline, and share your itinerary with a trusted contact.",
        ]
        if context:
            lines.append(f"Using your trip context: {context[:300]}")
        else:
            lines.append("No trip context was provided, so this is generic guidance only.")
        return AIAnswer(answer=" ".join(lines), verified=False, sources=["mock"])


def select_provider() -> AIProvider:
    """Central provider selection (the only place configuration maps to
    a provider). `mock` is for tests; anything else (including the
    `none` default) is explicitly unavailable - a future real provider
    plugs in here behind AI_PROVIDER/AI_API_KEY without touching
    callers."""
    if (settings.ai_provider or "none").strip().lower() == "mock":
        return MockProvider()
    return UnavailableProvider()
