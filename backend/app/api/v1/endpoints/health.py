"""Health check endpoint."""

from fastapi import APIRouter

from app.core.config import settings

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    summary="Service health check",
    description="Liveness/readiness probe for the Roamlary API service.",
)
def get_health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "roamlary-api",
        "environment": settings.app_env,
        "version": settings.app_version,
    }
