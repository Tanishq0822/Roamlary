"""Tests for the AI travel companion (Phase 13).

With no provider configured (the default), /ai/chat answers with the
documented unavailable message - never a fabricated answer. With the
mock provider (tests only), answers are deterministic and structured.
Data minimization is proven: foreign plans 404, and no other user's
data ever enters the context. Failures are honest errors, never
crashes or invented content.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.core.policy import set_policy
from app.core.rate_limit import reset_rate_limits
from app.models import User
from tests.conftest import register_user

AI_PATH = "/api/v1/ai/chat"


def _session(engine):
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    return factory()


def _flip_policy(engine, required: bool, changed_by_email: str) -> None:
    db = _session(engine)
    try:
        owner = db.scalar(select(User).where(User.email == changed_by_email))
        set_policy(db, value=required, changed_by=owner.id)
        db.commit()
    finally:
        db.close()


def _user(api_client, engine, tag="aiuser"):
    email = f"{tag}-{uuid.uuid4().hex[:8]}@example.com"
    _, headers = register_user(api_client, email, display_name=tag)
    _flip_policy(engine, False, email)
    return email, headers


def test_unavailable_by_default(api_client, sqlite_engine, monkeypatch) -> None:
    """No provider configured -> explicit unavailable answer (200 with
    the stable contract), verified=false, empty sources, both footers."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "ai_provider", "none")
    _, h = _user(api_client, sqlite_engine)
    status = api_client.get("/api/v1/ai/status", headers=h).json()
    assert status == {"provider": "unavailable", "configured": False}

    resp = api_client.post(AI_PATH, json={"message": "What should I pack for Goa?"}, headers=h)
    assert resp.status_code == 200
    body = resp.json()
    assert body["verified"] is False
    assert body["sources"] == []
    assert "not configured" in body["answer"]
    assert "nothing was sent" in body["answer"]
    assert body["emergency_footer"] != ""
    assert "not verified advice" in body["honesty_footer"]


def test_mock_provider_answers_with_context(api_client, sqlite_engine, monkeypatch) -> None:
    """Mock provider (tests only): deterministic structured answer that
    references the caller's OWN trip context."""
    from datetime import UTC, datetime, timedelta

    from app.core.config import settings
    from app.models import TravelPlan, TravelProfile

    monkeypatch.setattr(settings, "ai_provider", "mock")
    email, h = _user(api_client, sqlite_engine)
    db = _session(sqlite_engine)
    try:
        user = db.scalar(select(User).where(User.email == email))
        db.add(TravelProfile(user_id=user.id, travel_nickname="ai", interests=["hiking"]))
        today = datetime.now(UTC).date()
        db.add(
            TravelPlan(
                user_id=user.id,
                destination="Goa",
                destination_normalized="goa",
                start_date=today + timedelta(days=30),
                end_date=today + timedelta(days=37),
                status="active",
                visibility="private",
            )
        )
        db.commit()
        plan = db.scalar(select(TravelPlan).where(TravelPlan.user_id == user.id))
        plan_id = str(plan.id)
    finally:
        db.close()

    resp = api_client.post(
        AI_PATH, json={"message": "What should I pack?", "plan_id": plan_id}, headers=h
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["verified"] is False  # generated content is never "verified"
    assert body["sources"] == ["mock"]
    assert "Goa" in body["answer"]  # own trip context was used
    status = api_client.get("/api/v1/ai/status", headers=h).json()
    assert status == {"provider": "mock", "configured": True}


def test_foreign_plan_is_404(api_client, sqlite_engine, monkeypatch) -> None:
    """Another user's plan id cannot be pulled into AI context."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "ai_provider", "mock")
    _, h = _user(api_client, sqlite_engine)
    resp = api_client.post(AI_PATH, json={"message": "Hi", "plan_id": str(uuid.uuid4())}, headers=h)
    assert resp.status_code == 404


def test_ai_validates_and_gates(api_client, sqlite_engine, monkeypatch) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "ai_provider", "mock")
    _, h = _user(api_client, sqlite_engine)
    assert api_client.post(AI_PATH, json={"message": "   "}, headers=h).status_code == 422
    assert api_client.post(AI_PATH, json={"message": "x" * 2001}, headers=h).status_code == 422
    assert (
        api_client.post(AI_PATH, json={"message": "hi", " injections": 1}, headers=h).status_code
        == 422
    )
    assert api_client.post(AI_PATH, json={"message": "hi"}).status_code == 401


def test_ai_gated_while_policy_on(api_client, sqlite_engine, monkeypatch) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "ai_provider", "mock")
    email = f"unverified-{uuid.uuid4().hex[:8]}@example.com"
    _, h = register_user(api_client, email, display_name="unverified")
    assert api_client.post(AI_PATH, json={"message": "hi"}, headers=h).status_code == 403


def test_ai_rate_limit_429(api_client, sqlite_engine, monkeypatch) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "ai_provider", "mock")
    reset_rate_limits()
    _, h = _user(api_client, sqlite_engine)
    for n in range(20):
        assert api_client.post(AI_PATH, json={"message": f"q{n}"}, headers=h).status_code == 200
    assert api_client.post(AI_PATH, json={"message": "one more"}, headers=h).status_code == 429
    reset_rate_limits()
