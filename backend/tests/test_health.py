"""Tests for the health endpoint and OpenAPI availability."""


def test_health_returns_ok(client) -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "roamlary-api"
    assert body["version"]


def test_openapi_schema_exposes_health(client) -> None:
    response = client.get("/api/v1/openapi.json")

    assert response.status_code == 200
    schema = response.json()
    assert "/api/v1/health" in schema["paths"]


def test_docs_page_is_available(client) -> None:
    response = client.get("/docs")

    assert response.status_code == 200
