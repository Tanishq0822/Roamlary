"""Health check endpoint (liveness only)."""

from fastapi import APIRouter

from app.core.config import settings

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    summary="Service liveness check",
    description=(
        "Confirms the Roamlary backend application is running and serving "
        "requests. This is a liveness check only: it does NOT verify "
        "database, AI provider, or notification connectivity (later phases)."
    ),
)
def get_health() -> dict[str, str]:
    """Return the approved Phase 1 health contract.

    Response fields (stable contract for the Flutter frontend):
    - status: "ok" means the process is alive
    - service: fixed service identifier
    - version: API version, overridable via the APP_VERSION env var
    """
    return {
        "status": "ok",
        "service": "roamlary-backend",
        "version": settings.app_version,
    }
