"""AI travel companion endpoints (Phase 13).

Plain language: one endpoint answers travel questions using the
caller's OWN trip data as context. With no provider configured (the
normal state of this prototype) it answers with an explicit,
documented "unavailable" message - it NEVER fabricates guidance, hours,
routes, statistics, or safety verdicts.

Data minimization (brief item 7): the ONLY context ever built is the
caller's own travel plan (destination/dates) and own interests - never
other users, messages, SOS records, contacts, or precise locations.
Provider keys stay server-side and never appear in responses. Every
answer carries uncertainty + emergency footers; failures return honest
errors without crashing the app.
"""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.v1.deps import CurrentUser, DbSession, SocialUser
from app.api.v1.schemas.ai import AIChatRequest, AIChatResponse, AIStatusResponse
from app.core.config import settings
from app.core.rate_limit import check_rate_limit
from app.models.travel_plan import TravelPlan
from app.models.travel_profile import TravelProfile
from app.services.ai_provider import MAX_QUESTION_CHARS, AIAnswer, select_provider

router = APIRouter(prefix="/ai", tags=["ai-companion"])

# Usage control (shared in-process limiter, same documented caveat).
_CHAT_LIMIT_PER_HOUR = 20


def _own_trip_context(db, user_id: UUID, plan_id: UUID | None) -> str:
    """Build the context string from the caller's OWN trip data only.

    plan_id must be the caller's own plan (foreign ids 404 - no
    probing); without it, context is the caller's interests alone.
    Anything missing yields LESS context (stated uncertainty), never
    invented detail.
    """
    parts: list[str] = []
    if plan_id is not None:
        plan = db.scalar(
            select(TravelPlan).where(
                TravelPlan.id == plan_id,
                TravelPlan.user_id == user_id,
            )
        )
        if plan is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Travel plan not found.",
            )
        parts.append(f"destination {plan.destination}, {plan.start_date} to {plan.end_date}")
    profile = db.scalar(select(TravelProfile).where(TravelProfile.user_id == user_id))
    if profile is not None and profile.interests:
        parts.append(f"interests: {', '.join(profile.interests)}")
    return "; ".join(parts)


@router.get(
    "/status",
    response_model=AIStatusResponse,
    summary="AI companion configuration state (no keys, ever)",
)
def ai_status(current_user: CurrentUser, db: DbSession) -> AIStatusResponse:
    """Which provider is selected and whether it can answer. The key
    itself is never exposed (the response carries a boolean, not a
    secret)."""
    provider = select_provider()
    return AIStatusResponse(provider=provider.name, configured=provider.configured)


@router.post(
    "/chat",
    response_model=AIChatResponse,
    summary="Ask the AI travel companion (verified users only)",
)
def ai_chat(body: AIChatRequest, current_user: SocialUser, db: DbSession) -> AIChatResponse:
    """Answer a travel question with the caller's own trip context.

    Unconfigured provider (the default) -> 200 with the documented
    unavailable answer (verified=false, empty sources): the contract is
    stable and the UI renders the message instead of a fake answer.
    Provider faults -> 503 honest error, never a crash, never a
    fabricated fallback. Rate limited (20/hour/user, in-process)."""
    check_rate_limit(
        f"ai-chat:{current_user.id}",
        limit=_CHAT_LIMIT_PER_HOUR,
        window_seconds=3600,
    )
    if len(body.message) > MAX_QUESTION_CHARS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"message must be at most {MAX_QUESTION_CHARS} characters.",
        )
    context = _own_trip_context(db, current_user.id, body.plan_id)
    provider = select_provider()
    try:
        answer: AIAnswer = provider.answer(
            question=body.message,
            context=context,
            timeout_seconds=settings.ai_timeout_seconds,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The AI companion failed to answer. Try again later.",
        ) from exc
    return AIChatResponse(
        answer=answer.answer,
        verified=answer.verified,
        sources=answer.sources,
        emergency_footer=answer.emergency_footer,
        honesty_footer=answer.honesty_footer,
        generated_at=answer.generated_at,
    )
