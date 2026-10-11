"""Automated tests for Phase 1: app initialization, health contract, routing, CORS.

These tests are intentionally self-contained: no PostgreSQL, no Firebase,
no external network access is required.
"""

from fastapi import FastAPI

from app.core.config import settings
from app.main import app, create_app


def test_app_can_be_imported_and_initialized() -> None:
    """The application object exists and the factory builds a FastAPI app."""
    assert isinstance(app, FastAPI)
    assert isinstance(create_app(), FastAPI)
    assert app.title == settings.app_name


def test_health_returns_ok(client) -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    body = response.json()
    # Approved Phase 1 contract: exactly these three fields.
    assert set(body) == {"status", "service", "version"}
    assert body["status"] == "ok"
    assert body["service"] == "roamlary-backend"
    assert body["version"] == settings.app_version


def test_versioned_api_router_is_registered(client) -> None:
    """Every documented path lives under the /api/v1 prefix."""
    response = client.get("/api/v1/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/api/v1/health" in paths
    assert all(path.startswith("/api/v1/") for path in paths)


def test_unknown_route_returns_404(client) -> None:
    response = client.get("/api/v1/does-not-exist")

    assert response.status_code == 404


def test_cors_allows_configured_dev_origin(client) -> None:
    """A configured development origin receives the CORS allowance header."""
    response = client.get(
        "/api/v1/health",
        headers={"Origin": settings.cors_origins[0]},
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == settings.cors_origins[0]


def test_cors_does_not_allow_unknown_origin(client) -> None:
    """An unconfigured origin gets no CORS allowance (deny by default)."""
    response = client.get(
        "/api/v1/health",
        headers={"Origin": "http://evil.example.com"},
    )

    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers


def test_docs_page_is_available(client) -> None:
    response = client.get("/docs")

    assert response.status_code == 200
