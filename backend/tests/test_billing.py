"""Tests for pay-per-post monetization (Phase 14).

First post free (shared across categories, consumed atomically);
second costs ₹10 (1000 paise, INR); unpaid posts never publish;
mock-verified payments publish exactly once; duplicate callbacks are
idempotent; client-side success is impossible (no such route; tampered
tokens fail); failed/cancelled never unlock; refunds are owner-only and
record-consistent; ordinary chat messages are never charged; payment
rows are strictly per-user (owners excepted via the admin listing).
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.core.policy import set_policy
from app.models import User
from tests.conftest import register_user

BILLING_PATH = "/api/v1/billing"
TRAVEL_REQUESTS = "/api/v1/travel-buddies/requests"
CHAT_REQUESTS = "/api/v1/chat/requests"


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


def _mock_billing(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "billing_provider", "mock")


def _user(api_client, engine, tag="payer", policy_off=True):
    email = f"{tag}-{uuid.uuid4().hex[:8]}@example.com"
    _, headers = register_user(api_client, email, display_name=tag)
    if policy_off:
        _flip_policy(engine, False, email)
    return email, headers


def _id_of(api_client, headers) -> str:
    return api_client.get("/api/v1/users/me", headers=headers).json()["id"]


def _travel_pair(api_client, engine):
    """Two travel-discoverable users; returns (a_email, a_h, b_id, b_h)."""
    from app.models import TravelProfile

    a_email, a_h = _user(api_client, engine, tag="asker")
    b_email, b_h = _user(api_client, engine, tag="answer")
    db = _session(engine)
    try:
        for email, nick in ((a_email, "ta"), (b_email, "tb")):
            user = db.scalar(select(User).where(User.email == email))
            db.add(TravelProfile(user_id=user.id, travel_nickname=nick, discoverable=True))
        db.commit()
        b_id = str(db.scalar(select(User).where(User.email == b_email)).id)
    finally:
        db.close()
    return a_email, a_h, b_id, b_h


def test_policy_view_shows_price_and_free_state(api_client, sqlite_engine, monkeypatch) -> None:
    _mock_billing(monkeypatch)
    _, h = _user(api_client, sqlite_engine)
    policy = api_client.get(f"{BILLING_PATH}/policy", headers=h).json()
    assert policy["price_paise"] == 1000
    assert policy["currency"] == "INR"
    assert policy["free_posts_total"] == 1
    assert policy["free_posts_used"] == 0
    assert policy["free_remaining"] == 1
    assert policy["next_charge_paise"] == 0
    assert policy["provider_configured"] is True
    assert "refund" in policy["refund_terms"].lower()
    assert api_client.get(f"{BILLING_PATH}/policy").status_code == 401


def test_first_post_free_second_costs_inr10(api_client, sqlite_engine, monkeypatch) -> None:
    _mock_billing(monkeypatch)
    _, a_h, b_id, _ = _travel_pair(api_client, sqlite_engine)
    first = api_client.post(TRAVEL_REQUESTS, json={"recipient_id": b_id}, headers=a_h)
    assert first.status_code == 201, first.text

    policy = api_client.get(f"{BILLING_PATH}/policy", headers=a_h).json()
    assert policy["free_posts_used"] == 1
    assert policy["free_remaining"] == 0
    assert policy["next_charge_paise"] == 1000

    # Second post: 402 with the exact structured charge (nothing published).
    c_email = f"third-{uuid.uuid4().hex[:8]}@example.com"
    _, c_h = register_user(api_client, c_email, display_name="third")
    db = _session(sqlite_engine)
    try:
        from app.models import TravelProfile

        user = db.scalar(select(User).where(User.email == c_email))
        db.add(TravelProfile(user_id=user.id, travel_nickname="tc", discoverable=True))
        db.commit()
        c_id = str(user.id)
    finally:
        db.close()
    second = api_client.post(TRAVEL_REQUESTS, json={"recipient_id": c_id}, headers=a_h)
    assert second.status_code == 402, second.text
    detail = second.json()["detail"]
    assert detail["amount_paise"] == 1000
    assert detail["currency"] == "INR"
    assert detail["payment_id"]
    # No second request row exists (unpaid posts never publish).
    outgoing = api_client.get(f"{TRAVEL_REQUESTS}?direction=outgoing", headers=a_h).json()
    assert outgoing["total"] == 1


def test_free_entitlement_shared_across_categories(api_client, sqlite_engine, monkeypatch) -> None:
    """One free post TOTAL: a free travel request exhausts chat asks and
    meetup creates too (brief B: combined, not per-category)."""
    _mock_billing(monkeypatch)
    _, a_h, b_id, b_h = _travel_pair(api_client, sqlite_engine)
    assert (
        api_client.post(TRAVEL_REQUESTS, json={"recipient_id": b_id}, headers=a_h).status_code
        == 201
    )

    chat_ask = api_client.post(CHAT_REQUESTS, json={"recipient_id": b_id}, headers=a_h)
    assert chat_ask.status_code == 402
    assert chat_ask.json()["detail"]["amount_paise"] == 1000

    from datetime import UTC, datetime, timedelta

    now = datetime.now(UTC)
    meetup = api_client.post(
        "/api/v1/meetups",
        json={
            "title": "Paid Hike",
            "category": "hiking",
            "start_at": (now + timedelta(days=30)).isoformat(),
            "end_at": (now + timedelta(days=31)).isoformat(),
        },
        headers=a_h,
    )
    assert meetup.status_code == 402


def test_mock_payment_publishes_exactly_once(api_client, sqlite_engine, monkeypatch) -> None:
    """Pay the 402's payment with the mock token, re-submit WITH its id:
    the correct post publishes once; reusing the payment is 409."""
    _mock_billing(monkeypatch)
    _, a_h, b_id, _ = _travel_pair(api_client, sqlite_engine)
    assert (
        api_client.post(TRAVEL_REQUESTS, json={"recipient_id": b_id}, headers=a_h).status_code
        == 201
    )

    c_email = f"third-{uuid.uuid4().hex[:8]}@example.com"
    _, c_h = register_user(api_client, c_email, display_name="third")
    db = _session(sqlite_engine)
    try:
        from app.models import TravelProfile

        user = db.scalar(select(User).where(User.email == c_email))
        db.add(TravelProfile(user_id=user.id, travel_nickname="tc", discoverable=True))
        db.commit()
        c_id = str(user.id)
    finally:
        db.close()
    needed = api_client.post(TRAVEL_REQUESTS, json={"recipient_id": c_id}, headers=a_h)
    payment_id = needed.json()["detail"]["payment_id"]

    paid = api_client.post(
        f"{BILLING_PATH}/payments/{payment_id}/pay",
        json={"provider_token": f"mock-ok-{payment_id}"},
        headers=a_h,
    )
    assert paid.status_code == 200
    assert paid.json()["status"] == "succeeded"
    assert paid.json()["amount_paise"] == 1000

    published = api_client.post(
        TRAVEL_REQUESTS, json={"recipient_id": c_id, "payment_id": payment_id}, headers=a_h
    )
    assert published.status_code == 201, published.text
    assert published.json()["recipient_id"] == c_id  # the CORRECT post

    again = api_client.post(
        TRAVEL_REQUESTS, json={"recipient_id": c_id, "payment_id": payment_id}, headers=a_h
    )
    assert again.status_code == 409  # consumed payments never fund twice


def test_concurrent_first_posts_consume_once(api_client, sqlite_engine, monkeypatch) -> None:
    """Two racing first-posts: the free grant is consumed exactly once
    (compare-and-set); the loser gets 402, never a second free post."""
    _mock_billing(monkeypatch)
    _, a_h, b_id, _ = _travel_pair(api_client, sqlite_engine)
    # Simulate the race at the service layer: consume twice directly.
    from app.services.billing import consume_free_grant

    db = _session(sqlite_engine)
    try:
        a = db.scalar(select(User).where(User.email == _email_of(api_client, a_h)))
        first = consume_free_grant(db, user_id=a.id, free_total=1)
        db.commit()
        second = consume_free_grant(db, user_id=a.id, free_total=1)
        db.commit()
    finally:
        db.close()
    assert first is True
    assert second is False
    # And the account now pays for everything (endpoint-level proof).
    c_email = f"third-{uuid.uuid4().hex[:8]}@example.com"
    _, c_h = register_user(api_client, c_email, display_name="third")
    db = _session(sqlite_engine)
    try:
        from app.models import TravelProfile

        user = db.scalar(select(User).where(User.email == c_email))
        db.add(TravelProfile(user_id=user.id, travel_nickname="tc", discoverable=True))
        db.commit()
        c_id = str(user.id)
    finally:
        db.close()
    assert (
        api_client.post(CHAT_REQUESTS, json={"recipient_id": c_id}, headers=a_h).status_code == 402
    )


def _email_of(api_client, headers) -> str:
    return api_client.get("/api/v1/users/me", headers=headers).json()["email"]


def test_duplicate_webhook_never_duplicates(api_client, sqlite_engine, monkeypatch) -> None:
    """Same webhook delivered twice: one charge, one post, same row."""
    _mock_billing(monkeypatch)
    _, a_h, b_id, _ = _travel_pair(api_client, sqlite_engine)
    assert (
        api_client.post(TRAVEL_REQUESTS, json={"recipient_id": b_id}, headers=a_h).status_code
        == 201
    )

    c_email = f"third-{uuid.uuid4().hex[:8]}@example.com"
    _, _ = register_user(api_client, c_email, display_name="third")
    db = _session(sqlite_engine)
    try:
        from app.models import TravelProfile

        user = db.scalar(select(User).where(User.email == c_email))
        db.add(TravelProfile(user_id=user.id, travel_nickname="tc", discoverable=True))
        db.commit()
        c_id = str(user.id)
    finally:
        db.close()
    needed = api_client.post(TRAVEL_REQUESTS, json={"recipient_id": c_id}, headers=a_h)
    payment_id = needed.json()["detail"]["payment_id"]
    hook = {"payment_id": payment_id, "provider_reference": "wh-1", "outcome": "succeeded"}
    first = api_client.post(f"{BILLING_PATH}/webhook", json=hook)
    assert first.status_code == 200
    second = api_client.post(f"{BILLING_PATH}/webhook", json=hook)
    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]
    mine = api_client.get(f"{BILLING_PATH}/payments", headers=a_h).json()
    assert mine["total"] == 2  # free row + this payment (no duplicates)

    published = api_client.post(
        TRAVEL_REQUESTS, json={"recipient_id": c_id, "payment_id": payment_id}, headers=a_h
    )
    assert published.status_code == 201


def test_client_success_and_bad_tokens_rejected(api_client, sqlite_engine, monkeypatch) -> None:
    """No route marks payments successful except provider verification:
    tampered tokens fail; failed payments never unlock publishing."""
    _mock_billing(monkeypatch)
    _, a_h, b_id, _ = _travel_pair(api_client, sqlite_engine)
    assert (
        api_client.post(TRAVEL_REQUESTS, json={"recipient_id": b_id}, headers=a_h).status_code
        == 201
    )

    c_email = f"third-{uuid.uuid4().hex[:8]}@example.com"
    _, _ = register_user(api_client, c_email, display_name="third")
    db = _session(sqlite_engine)
    try:
        from app.models import TravelProfile

        user = db.scalar(select(User).where(User.email == c_email))
        db.add(TravelProfile(user_id=user.id, travel_nickname="tc", discoverable=True))
        db.commit()
        c_id = str(user.id)
    finally:
        db.close()
    payment_id = api_client.post(TRAVEL_REQUESTS, json={"recipient_id": c_id}, headers=a_h).json()[
        "detail"
    ]["payment_id"]
    # Forged token for THIS payment: fails, row stays payable-but-unpaid.
    forged = api_client.post(
        f"{BILLING_PATH}/payments/{payment_id}/pay",
        json={"provider_token": "mock-ok-someone-elses-payment"},
        headers=a_h,
    )
    assert forged.status_code == 200
    assert forged.json()["status"] == "failed"
    locked = api_client.post(
        TRAVEL_REQUESTS, json={"recipient_id": c_id, "payment_id": payment_id}, headers=a_h
    )
    assert locked.status_code == 409  # failed never unlocks
    # Token for a DIFFERENT payment: fails too (replay across rows).
    other = api_client.post(
        f"{BILLING_PATH}/payments/{payment_id}/pay",
        json={"provider_token": "mock-ok-00000000-0000-0000-0000-000000000000"},
        headers=a_h,
    )
    assert other.json()["status"] == "failed"


def test_cancelled_payment_never_unlocks(api_client, sqlite_engine, monkeypatch) -> None:
    _mock_billing(monkeypatch)
    _, a_h, b_id, _ = _travel_pair(api_client, sqlite_engine)
    assert (
        api_client.post(TRAVEL_REQUESTS, json={"recipient_id": b_id}, headers=a_h).status_code
        == 201
    )

    c_email = f"third-{uuid.uuid4().hex[:8]}@example.com"
    _, _ = register_user(api_client, c_email, display_name="third")
    db = _session(sqlite_engine)
    try:
        from app.models import TravelProfile

        user = db.scalar(select(User).where(User.email == c_email))
        db.add(TravelProfile(user_id=user.id, travel_nickname="tc", discoverable=True))
        db.commit()
        c_id = str(user.id)
    finally:
        db.close()
    payment_id = api_client.post(TRAVEL_REQUESTS, json={"recipient_id": c_id}, headers=a_h).json()[
        "detail"
    ]["payment_id"]
    assert (
        api_client.post(f"{BILLING_PATH}/payments/{payment_id}/cancel", headers=a_h).status_code
        == 200
    )
    locked = api_client.post(
        TRAVEL_REQUESTS, json={"recipient_id": c_id, "payment_id": payment_id}, headers=a_h
    )
    assert locked.status_code == 409
    # And a cancelled row cannot be paid afterwards.
    assert (
        api_client.post(
            f"{BILLING_PATH}/payments/{payment_id}/pay",
            json={"provider_token": f"mock-ok-{payment_id}"},
            headers=a_h,
        ).status_code
        == 409
    )


def test_refund_owner_only_and_consistent(api_client, sqlite_engine, monkeypatch) -> None:
    """Refunds: owner-only, succeeded-only, record-consistent (state +
    history preserved, free posts untouched, nothing unpublished)."""
    _mock_billing(monkeypatch)
    owner_email, _ = _user(api_client, sqlite_engine, tag="owner")
    db = _session(sqlite_engine)
    try:
        owner = db.scalar(select(User).where(User.email == owner_email))
        owner.role = "owner"
        db.commit()
    finally:
        db.close()
    # Fresh owner login via the known password (register_user's default).
    owner_login = api_client.post(
        "/api/v1/auth/login", json={"email": owner_email, "password": "s3cure-Pass!"}
    )
    owner_h = {"Authorization": f"Bearer {owner_login.json()['access_token']}"}

    _, a_h, b_id, _ = _travel_pair(api_client, sqlite_engine)
    assert (
        api_client.post(TRAVEL_REQUESTS, json={"recipient_id": b_id}, headers=a_h).status_code
        == 201
    )
    c_email = f"third-{uuid.uuid4().hex[:8]}@example.com"
    _, _ = register_user(api_client, c_email, display_name="third")
    db = _session(sqlite_engine)
    try:
        from app.models import TravelProfile

        user = db.scalar(select(User).where(User.email == c_email))
        db.add(TravelProfile(user_id=user.id, travel_nickname="tc", discoverable=True))
        db.commit()
        c_id = str(user.id)
    finally:
        db.close()
    payment_id = api_client.post(TRAVEL_REQUESTS, json={"recipient_id": c_id}, headers=a_h).json()[
        "detail"
    ]["payment_id"]
    api_client.post(
        f"{BILLING_PATH}/payments/{payment_id}/pay",
        json={"provider_token": f"mock-ok-{payment_id}"},
        headers=a_h,
    )
    published = api_client.post(
        TRAVEL_REQUESTS, json={"recipient_id": c_id, "payment_id": payment_id}, headers=a_h
    )
    assert published.status_code == 201

    # Non-owners cannot refund (or even see the admin listing).
    assert (
        api_client.post(f"/api/v1/admin/payments/{payment_id}/refund", headers=a_h).status_code
        == 403
    )
    assert api_client.get("/api/v1/admin/payments", headers=a_h).status_code == 403
    refunded = api_client.post(f"/api/v1/admin/payments/{payment_id}/refund", headers=owner_h)
    assert refunded.status_code == 200
    assert refunded.json()["status"] == "refunded"
    # Consistent: the post still exists (refunds don't unpublish), the
    # free-post counter is untouched, history lists the row.
    assert (
        api_client.get(f"{TRAVEL_REQUESTS}/{published.json()['id']}", headers=a_h).status_code
        == 200
    )
    policy = api_client.get(f"{BILLING_PATH}/policy", headers=a_h).json()
    assert policy["free_posts_used"] == 1
    mine = api_client.get(f"{BILLING_PATH}/payments", headers=a_h).json()
    assert any(p["status"] == "refunded" for p in mine["results"])
    # Refunding twice is refused.
    assert (
        api_client.post(f"/api/v1/admin/payments/{payment_id}/refund", headers=owner_h).status_code
        == 409
    )


def test_chat_messages_never_charged(api_client, sqlite_engine, monkeypatch) -> None:
    """Ordinary messages inside an accepted conversation create no
    charges and need no payment (only the ASK is a post)."""
    _mock_billing(monkeypatch)
    _, a_h, b_id, b_h = _travel_pair(api_client, sqlite_engine)
    asked = api_client.post(CHAT_REQUESTS, json={"recipient_id": b_id}, headers=a_h)
    assert asked.status_code == 201  # first post free
    conv_id = asked.json()["id"]
    assert api_client.post(f"{CHAT_REQUESTS}/{conv_id}/accept", headers=b_h).status_code == 200
    for n in range(3):
        sent = api_client.post(
            f"/api/v1/chat/conversations/{conv_id}/messages", json={"body": f"m{n}"}, headers=a_h
        )
        assert sent.status_code == 201, sent.text
    mine = api_client.get(f"{BILLING_PATH}/payments", headers=a_h).json()
    assert mine["total"] == 1  # only the free ask row
    assert mine["results"][0]["amount_paise"] == 0


def test_payments_are_per_user(api_client, sqlite_engine, monkeypatch) -> None:
    """Nobody touches another user's rows (identical 404s); the admin
    listing is owner-only."""
    _mock_billing(monkeypatch)
    _, a_h, b_id, b_h = _travel_pair(api_client, sqlite_engine)
    assert (
        api_client.post(TRAVEL_REQUESTS, json={"recipient_id": b_id}, headers=a_h).status_code
        == 201
    )
    payment_id = api_client.get(f"{BILLING_PATH}/payments", headers=a_h).json()["results"][0]["id"]
    assert (
        api_client.post(
            f"{BILLING_PATH}/payments/{payment_id}/pay", json={"provider_token": "x"}, headers=b_h
        ).status_code
        == 404
    )
    assert (
        api_client.post(f"{BILLING_PATH}/payments/{payment_id}/cancel", headers=b_h).status_code
        == 404
    )
    assert api_client.get("/api/v1/admin/payments", headers=b_h).status_code == 403
    assert api_client.get(f"{BILLING_PATH}/payments", headers=b_h).json()["total"] == 0


def test_unconfigured_provider_keeps_paid_pending(api_client, sqlite_engine, monkeypatch) -> None:
    """With BILLING_PROVIDER=none (default), paid publishing is honestly
    pending: pay attempts fail, never confirm."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "billing_provider", "none")
    _, a_h, b_id, _ = _travel_pair(api_client, sqlite_engine)
    assert (
        api_client.post(TRAVEL_REQUESTS, json={"recipient_id": b_id}, headers=a_h).status_code
        == 201
    )
    c_email = f"third-{uuid.uuid4().hex[:8]}@example.com"
    _, _ = register_user(api_client, c_email, display_name="third")
    db = _session(sqlite_engine)
    try:
        from app.models import TravelProfile

        user = db.scalar(select(User).where(User.email == c_email))
        db.add(TravelProfile(user_id=user.id, travel_nickname="tc", discoverable=True))
        db.commit()
        c_id = str(user.id)
    finally:
        db.close()
    needed = api_client.post(TRAVEL_REQUESTS, json={"recipient_id": c_id}, headers=a_h)
    assert needed.status_code == 402
    payment_id = needed.json()["detail"]["payment_id"]
    policy = api_client.get(f"{BILLING_PATH}/policy", headers=a_h).json()
    assert policy["provider_configured"] is False
    failed = api_client.post(
        f"{BILLING_PATH}/payments/{payment_id}/pay",
        json={"provider_token": "anything"},
        headers=a_h,
    )
    assert failed.status_code == 200
    assert failed.json()["status"] == "failed"
    assert "No billing provider" in failed.json()["last_error"]


def test_owner_can_change_price_and_free_count(api_client, sqlite_engine, monkeypatch) -> None:
    """Pricing is configurable at runtime (audited); bad values 422."""
    _mock_billing(monkeypatch)
    owner_email, _ = _user(api_client, sqlite_engine, tag="owner")
    db = _session(sqlite_engine)
    try:
        owner = db.scalar(select(User).where(User.email == owner_email))
        owner.role = "owner"
        db.commit()
    finally:
        db.close()
    owner_login = api_client.post(
        "/api/v1/auth/login", json={"email": owner_email, "password": "s3cure-Pass!"}
    )
    owner_h = {"Authorization": f"Bearer {owner_login.json()['access_token']}"}
    try:
        updated = api_client.patch(
            "/api/v1/admin/policy/billing",
            json={"price_paise": 2000, "free_posts": 2},
            headers=owner_h,
        )
        assert updated.status_code == 200
        assert updated.json()["price_paise"] == 2000
        assert updated.json()["free_posts_total"] == 2
        assert (
            api_client.patch(
                "/api/v1/admin/policy/billing", json={"price_paise": -5}, headers=owner_h
            ).status_code
            == 422
        )
        _, h = _user(api_client, sqlite_engine, tag="plain")
        assert (
            api_client.patch(
                "/api/v1/admin/policy/billing", json={"price_paise": 5}, headers=h
            ).status_code
            == 403
        )
    finally:
        # Restore documented defaults even on failure (shared settings row).
        api_client.patch(
            "/api/v1/admin/policy/billing",
            json={"price_paise": 1000, "free_posts": 1},
            headers=owner_h,
        )
