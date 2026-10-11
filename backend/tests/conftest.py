"""Shared pytest fixtures."""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def client() -> TestClient:
    """FastAPI TestClient bound to the application under test."""
    with TestClient(app) as test_client:
        yield test_client
