"""AI companion schemas (Phase 13).

Plain language: the request carries a question and optional pointers to
the caller's OWN trip data (a plan id). The response is a structured
answer with honesty metadata: `verified` is True ONLY for retrieved
(non-generated) content, `sources` names what was used, and the two
footers (uncertainty + emergency) travel in EVERY answer. Provider keys,
model names, and raw provider payloads never appear here.
"""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AIChatRequest(BaseModel):
    """Body for POST /ai/chat. A question plus optional own-trip context."""

    model_config = ConfigDict(extra="forbid")

    message: str = Field(..., min_length=1, max_length=2000)
    plan_id: UUID | None = None

    @field_validator("message")
    @classmethod
    def strip_nonblank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("message must not be blank")
        return stripped


class AIChatResponse(BaseModel):
    """Structured companion answer (frontend-ready shape)."""

    model_config = ConfigDict(extra="forbid")

    answer: str
    verified: bool
    sources: list[str]
    emergency_footer: str
    honesty_footer: str
    generated_at: str


class AIStatusResponse(BaseModel):
    """Provider configuration state (no keys, ever)."""

    model_config = ConfigDict(extra="forbid")

    provider: str
    configured: bool
