"""Roamlary API application factory.

Run locally with:
    uvicorn app.main:app --reload
Interactive API docs: http://127.0.0.1:8000/docs
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings


def create_app() -> FastAPI:
    """Build the FastAPI application with CORS and versioned routers."""
    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "Backend API for Roamlary - an AI-powered travel companion and "
            "personal safety prototype (CODE X 3.0 hackathon). "
            "This is a local prototype; no emergency services or real "
            "responders are connected."
        ),
        openapi_url=f"{settings.api_v1_prefix}/openapi.json",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(api_router, prefix=settings.api_v1_prefix)
    return application


app = create_app()
