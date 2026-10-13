"""Endpoint tests for one-to-one messaging: requests, conversations, messages (Phase 8).

These prove the brief's messaging rules: an explicit ask precedes chat;
accepting a TRAVEL-partner request never opens chat by itself; only
participants read or write; ids cannot be swapped to reach other
people's chats; duplicate pending asks are impossible (one row per
unordered pair); terminal states lock; rejection can be followed by an
explicit new ask but never reopens silently; blocks and lapsed
eligibility are rechecked live at send time; history stays readable
after blocking while sending stops; and the sender always comes from
the token, never the body.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.core.policy import set_policy
from app.core.rate_limit import reset_rate_limits
from app.models import Conversation, User
from tests.conftest import register_user

REQUESTS_PATH = "/api/v1/chat/requests"
CONVERSATIONS_PATH = "/api/v1/chat/conversations"


def _session(engine):
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    return factory()


def _set_verification(engine, email: str, state: str) -> None:
    db = _session(engine)
    try:
        user = db.scalar(select(User).where(User.email == email))
        user.verification_status = state
        db.commit()
    finally:
        db.close()


def _flip_policy(engine, required: bool, changed_by_email: str) -> None:
    db = _session(engine)
    try:
        owner = db.scalar(select(User).where(User.email == changed_by_email))
        set_policy(db, value=required, changed_by=owner.id)
        db.commit()
    finally:
        db.close()


def _chat_pair(api_client, engine, policy_off=True):
    """Two plain registered users (chat needs no travel profile).

    Returns (a_email, a_h, b_email, b_id, b_h).
    """
    a_email = f"chatter-a-{uuid.uuid4().hex[:8]}@example.com"
    _, a_h = register_user(api_client, a_email, display_name="chatter-a")
    b_email = f"chatter-b-{uuid.uuid4().hex[:8]}@example.com"
    _, b_h = register_user(api_client, b_email, display_name="chatter-b")
    db = _session(engine)
    try:
        b = db.scalar(select(User).where(User.email == b_email))
        b_id = str(b.id)
    finally:
        db.close()
    if policy_off:
        _flip_policy(engine, False, a_email)
    return a_email, a_h, b_email, b_id, b_h


def _ask(api_client, sender_h, recipient_id, payment_id=None):
    body = {"recipient_id": recipient_id}
    if payment_id is not None:
        body["payment_id"] = payment_id
    return api_client.post(REQUESTS_PATH, json=body, headers=sender_h)


def _accepted_pair(api_client, engine):
    """A pair with an accepted conversation; returns (a_email, a_h, b_email, b_id, b_h, conv)."""
    a_email, a_h, b_email, b_id, b_h = _chat_pair(api_client, engine)
    sent = _ask(api_client, a_h, b_id)
    assert sent.status_code == 201, sent.text
    accepted = api_client.post(f"{REQUESTS_PATH}/{sent.json()['id']}/accept", headers=b_h)
    assert accepted.status_code == 200, accepted.text
    return a_email, a_h, b_email, b_id, b_h, accepted.json()


def test_request_lifecycle_end_to_end(api_client, sqlite_engine) -> None:
    a_email, a_h, b_email, b_id, b_h, conv = _accepted_pair(api_client, sqlite_engine)
    assert conv["status"] == "accepted"
    assert conv["requested_by_me"] is False  # B reads the row: A asked
    assert conv["other_display_name"] == "chatter-a"

    # A's own view of the same row is mirrored, not duplicated.
    mine = api_client.get(f"{REQUESTS_PATH}/{conv['id']}", headers=a_h).json()
    assert mine["requested_by_me"] is True
    assert mine["other_user_id"] == b_id

    # Message exchange in both directions.
    first = api_client.post(
        f"{CONVERSATIONS_PATH}/{conv['id']}/messages", json={"body": "Hello B"}, headers=a_h
    )
    assert first.status_code == 201, first.text
    assert first.json()["mine"] is True
    second = api_client.post(
        f"{CONVERSATIONS_PATH}/{conv['id']}/messages", json={"body": "Hi A"}, headers=b_h
    )
    assert second.status_code == 201, second.text

    history = api_client.get(f"{CONVERSATIONS_PATH}/{conv['id']}/messages", headers=a_h).json()
    assert history["total"] == 2
    assert [m["body"] for m in history["results"]] == ["Hello B", "Hi A"]
    assert [m["mine"] for m in history["results"]] == [True, False]

    # No tokens, no account data, no unrelated metadata in messages.
    for message in history["results"]:
        assert set(message) == {
            "id",
            "conversation_id",
            "sender_id",
            "mine",
            "body",
            "is_deleted",
            "created_at",
        }


def test_chat_requires_authentication(api_client) -> None:
    assert (
        api_client.post(REQUESTS_PATH, json={"recipient_id": str(uuid.uuid4())}).status_code == 401
    )
    assert api_client.get(REQUESTS_PATH).status_code == 401
    assert api_client.get(CONVERSATIONS_PATH).status_code == 401
    assert (
        api_client.post(
            f"{CONVERSATIONS_PATH}/{uuid.uuid4()}/messages", json={"body": "x"}
        ).status_code
        == 401
    )


def test_send_to_self_is_422(api_client, sqlite_engine) -> None:
    a_email, a_h, _, _, _ = _chat_pair(api_client, sqlite_engine)
    db = _session(sqlite_engine)
    try:
        me = db.scalar(select(User).where(User.email == a_email))
        resp = _ask(api_client, a_h, str(me.id))
    finally:
        db.close()
    assert resp.status_code == 422


def test_send_to_unknown_user_is_404(api_client, sqlite_engine) -> None:
    _, a_h, _, _, _ = _chat_pair(api_client, sqlite_engine)
    resp = _ask(api_client, a_h, str(uuid.uuid4()))
    assert resp.status_code == 404
    assert resp.json()["detail"] == "User not found."


def test_send_gated_403_while_policy_requires_verification(api_client, sqlite_engine) -> None:
    # Policy left ON (no flip): both accounts are unverified.
    _, a_h, _, b_id, _ = _chat_pair(api_client, sqlite_engine, policy_off=False)
    assert _ask(api_client, a_h, b_id).status_code == 403


def test_duplicate_pending_in_either_direction_is_409(api_client, sqlite_engine) -> None:
    _, a_h, _, b_id, b_h = _chat_pair(api_client, sqlite_engine)
    assert _ask(api_client, a_h, b_id).status_code == 201
    # Same direction again...
    assert _ask(api_client, a_h, b_id).status_code == 409
    # ...and the reverse direction: the row has no direction, so B must
    # answer A's ask instead of opening a second one.
    reverse = _ask(api_client, b_h, _other_id(api_client, a_h))
    assert reverse.status_code == 409
    assert "Answer it" in reverse.json()["detail"]


def _other_id(api_client, headers) -> str:
    return api_client.get("/api/v1/users/me", headers=headers).json()["id"]


def test_accepted_pair_cannot_request_again(api_client, sqlite_engine) -> None:
    _, a_h, _, b_id, _, _ = _accepted_pair(api_client, sqlite_engine)
    resp = _ask(api_client, a_h, b_id)
    assert resp.status_code == 409


def test_reject_then_explicit_rerequest_reopens(api_client, sqlite_engine) -> None:
    a_email, a_h, b_email, b_id, b_h = _chat_pair(api_client, sqlite_engine)
    sent = _ask(api_client, a_h, b_id)
    assert (
        api_client.post(f"{REQUESTS_PATH}/{sent.json()['id']}/reject", headers=b_h).status_code
        == 200
    )

    # The row is terminal...
    again = api_client.post(f"{REQUESTS_PATH}/{sent.json()['id']}/accept", headers=b_h)
    assert again.status_code == 409
    # ...until an explicit NEW ask reopens the same row (no duplicate).
    reopened = _ask(api_client, b_h, _other_id(api_client, a_h))
    assert reopened.status_code == 201, reopened.text
    body = reopened.json()
    assert body["id"] == sent.json()["id"]  # the SAME row, not a second one
    assert body["status"] == "pending"
    assert body["requested_by_me"] is True  # B is the new asker now
    db = _session(sqlite_engine)
    try:
        count = len(db.scalars(select(Conversation)).all())
    finally:
        db.close()
    assert count == 1


def test_cancel_by_requester_only(api_client, sqlite_engine) -> None:
    _, a_h, _, _, b_h = _chat_pair(api_client, sqlite_engine)
    sent = _ask(api_client, a_h, _other_id(api_client, b_h))
    wrong = api_client.post(f"{REQUESTS_PATH}/{sent.json()['id']}/cancel", headers=b_h)
    assert wrong.status_code == 404
    ok = api_client.post(f"{REQUESTS_PATH}/{sent.json()['id']}/cancel", headers=a_h)
    assert ok.status_code == 200
    assert ok.json()["status"] == "cancelled"


def test_terminal_states_refuse_further_moves(api_client, sqlite_engine) -> None:
    _, a_h, _, _, b_h, conv = _accepted_pair(api_client, sqlite_engine)
    for action in ("reject", "accept"):
        resp = api_client.post(f"{REQUESTS_PATH}/{conv['id']}/{action}", headers=b_h)
        assert resp.status_code == 409, (action, resp.text)
    assert api_client.post(f"{REQUESTS_PATH}/{conv['id']}/cancel", headers=a_h).status_code == 409


def test_nonparty_cannot_read_or_move(api_client, sqlite_engine) -> None:
    _, a_h, _, b_id, _ = _chat_pair(api_client, sqlite_engine)
    sent = _ask(api_client, a_h, b_id)
    stranger_h = register_user(api_client, f"stranger-{uuid.uuid4().hex[:8]}@example.com")[1]
    assert (
        api_client.get(f"{REQUESTS_PATH}/{sent.json()['id']}", headers=stranger_h).status_code
        == 404
    )
    assert (
        api_client.post(
            f"{REQUESTS_PATH}/{sent.json()['id']}/accept", headers=stranger_h
        ).status_code
        == 404
    )
    assert (
        api_client.get(f"{CONVERSATIONS_PATH}/{sent.json()['id']}", headers=stranger_h).status_code
        == 404
    )
    assert (
        api_client.post(
            f"{CONVERSATIONS_PATH}/{sent.json()['id']}/messages",
            json={"body": "intruder"},
            headers=stranger_h,
        ).status_code
        == 404
    )


def test_send_requires_accepted_conversation(api_client, sqlite_engine) -> None:
    _, a_h, _, b_id, _ = _chat_pair(api_client, sqlite_engine)
    sent = _ask(api_client, a_h, b_id)
    resp = api_client.post(
        f"{CONVERSATIONS_PATH}/{sent.json()['id']}/messages",
        json={"body": "too soon"},
        headers=a_h,
    )
    assert resp.status_code == 409


def test_message_body_validation(api_client, sqlite_engine) -> None:
    _, a_h, _, _, _, conv = _accepted_pair(api_client, sqlite_engine)
    url = f"{CONVERSATIONS_PATH}/{conv['id']}/messages"
    assert api_client.post(url, json={"body": "   "}, headers=a_h).status_code == 422
    assert api_client.post(url, json={"body": ""}, headers=a_h).status_code == 422
    assert api_client.post(url, json={"body": "x" * 2001}, headers=a_h).status_code == 422
    assert (
        api_client.post(url, json={"body": "ok", "sender_id": "forged"}, headers=a_h).status_code
        == 422
    )


def test_history_pagination_is_stable(api_client, sqlite_engine) -> None:
    _, a_h, _, _, _, conv = _accepted_pair(api_client, sqlite_engine)
    url = f"{CONVERSATIONS_PATH}/{conv['id']}/messages"
    for n in range(5):
        assert api_client.post(url, json={"body": f"m{n}"}, headers=a_h).status_code == 201
    page1 = api_client.get(url + "?limit=2&offset=0", headers=a_h).json()
    page2 = api_client.get(url + "?limit=2&offset=2", headers=a_h).json()
    page3 = api_client.get(url + "?limit=2&offset=4", headers=a_h).json()
    assert page1["total"] == 5
    assert [m["body"] for m in page1["results"]] == ["m0", "m1"]
    assert [m["body"] for m in page2["results"]] == ["m2", "m3"]
    assert [m["body"] for m in page3["results"]] == ["m4"]
    assert api_client.get(url + "?limit=0", headers=a_h).status_code == 422
    assert api_client.get(url + "?limit=101", headers=a_h).status_code == 422


def test_delete_own_message_is_soft(api_client, sqlite_engine) -> None:
    _, a_h, _, _, _, conv = _accepted_pair(api_client, sqlite_engine)
    url = f"{CONVERSATIONS_PATH}/{conv['id']}/messages"
    sent = api_client.post(url, json={"body": "oops"}, headers=a_h)
    deleted = api_client.delete(f"/api/v1/chat/messages/{sent.json()['id']}", headers=a_h)
    assert deleted.status_code == 200
    body = deleted.json()
    assert body["is_deleted"] is True
    assert body["body"] is None
    history = api_client.get(url, headers=a_h).json()
    assert history["total"] == 1  # the row keeps its place in history
    assert history["results"][0]["body"] is None
    # Re-deleting is idempotent.
    assert (
        api_client.delete(f"/api/v1/chat/messages/{sent.json()['id']}", headers=a_h).status_code
        == 200
    )


def test_delete_others_message_is_404(api_client, sqlite_engine) -> None:
    _, a_h, _, _, b_h, conv = _accepted_pair(api_client, sqlite_engine)
    url = f"{CONVERSATIONS_PATH}/{conv['id']}/messages"
    sent = api_client.post(url, json={"body": "mine"}, headers=a_h)
    assert (
        api_client.delete(f"/api/v1/chat/messages/{sent.json()['id']}", headers=b_h).status_code
        == 404
    )
    assert (
        api_client.delete(f"/api/v1/chat/messages/{uuid.uuid4()}", headers=a_h).status_code == 404
    )


def test_conversation_list_orders_recent_first(api_client, sqlite_engine) -> None:
    """Sending a message refreshes the conversation row, so the recently
    active chat sorts above the newer-but-quiet one."""
    from tests.conftest import prefund_payment

    a_email, a_h, _, b_id, b_h = _chat_pair(api_client, sqlite_engine)
    c_email = f"chatter-c-{uuid.uuid4().hex[:8]}@example.com"
    _, c_h = register_user(api_client, c_email, display_name="chatter-c")
    db = _session(sqlite_engine)
    try:
        c_id = str(db.scalar(select(User).where(User.email == c_email)).id)
    finally:
        db.close()
    first = _ask(api_client, a_h, b_id)
    assert (
        api_client.post(f"{REQUESTS_PATH}/{first.json()['id']}/accept", headers=b_h).status_code
        == 200
    )
    # The first ask consumed the free post: fund the second ask (the
    # recent-first ordering is under test, not billing).
    payment_id = prefund_payment(sqlite_engine, a_email, "chat_request")
    second = _ask(api_client, a_h, c_id, payment_id=payment_id)
    assert second.status_code == 201, second.text
    assert (
        api_client.post(f"{REQUESTS_PATH}/{second.json()['id']}/accept", headers=c_h).status_code
        == 200
    )

    # The FIRST conversation gets a message: it must sort above the
    # newer-but-quiet second one.
    assert (
        api_client.post(
            f"{CONVERSATIONS_PATH}/{first.json()['id']}/messages",
            json={"body": "recent activity"},
            headers=a_h,
        ).status_code
        == 201
    )
    convs = api_client.get(CONVERSATIONS_PATH, headers=a_h).json()
    assert convs["total"] == 2
    assert [c["id"] for c in convs["results"]] == [first.json()["id"], second.json()["id"]]


def test_travel_accept_does_not_open_chat(api_client, sqlite_engine) -> None:
    """An accepted TRAVEL-partner request authorizes no chat: the pair has
    no conversation, cannot message, and still needs a message request."""
    from app.models import TravelProfile

    a_email, a_h, b_email, b_id, b_h = _chat_pair(api_client, sqlite_engine)
    # Make both travel-discoverable so a travel request can be accepted.
    db = _session(sqlite_engine)
    try:
        for email, nick in ((a_email, "ta"), (b_email, "tb")):
            user = db.scalar(select(User).where(User.email == email))
            db.add(TravelProfile(user_id=user.id, travel_nickname=nick, discoverable=True))
        db.commit()
    finally:
        db.close()
    sent = api_client.post(
        "/api/v1/travel-buddies/requests", json={"recipient_id": b_id}, headers=a_h
    )
    assert sent.status_code == 201, sent.text
    assert (
        api_client.post(
            f"/api/v1/travel-buddies/requests/{sent.json()['id']}/accept", headers=b_h
        ).status_code
        == 200
    )

    convs = api_client.get(CONVERSATIONS_PATH, headers=a_h).json()
    assert convs["total"] == 0
    # A message request is still required - and still allowed (funded:
    # the travel request above consumed the free post).
    from tests.conftest import prefund_payment

    payment_id = prefund_payment(sqlite_engine, a_email, "chat_request")
    assert _ask(api_client, a_h, b_id, payment_id=payment_id).status_code == 201


def test_block_stops_sending_but_history_stays(api_client, sqlite_engine) -> None:
    _, a_h, _, b_id, b_h, conv = _accepted_pair(api_client, sqlite_engine)
    url = f"{CONVERSATIONS_PATH}/{conv['id']}/messages"
    assert api_client.post(url, json={"body": "before"}, headers=a_h).status_code == 201
    assert (
        api_client.post("/api/v1/blocks", json={"blocked_id": b_id}, headers=a_h).status_code == 201
    )

    blocked_send = api_client.post(url, json={"body": "after"}, headers=a_h)
    assert blocked_send.status_code == 403
    blocked_send_b = api_client.post(url, json={"body": "after"}, headers=b_h)
    assert blocked_send_b.status_code == 403
    # History remains readable to both participants (documented policy).
    for headers in (a_h, b_h):
        history = api_client.get(url, headers=headers)
        assert history.status_code == 200
        assert [m["body"] for m in history.json()["results"]] == ["before"]
    # Unblocking restores sending.
    assert api_client.delete(f"/api/v1/blocks/{b_id}", headers=a_h).status_code == 204
    assert api_client.post(url, json={"body": "again"}, headers=a_h).status_code == 201


def test_message_request_to_blocked_pair_is_404(api_client, sqlite_engine) -> None:
    a_email, a_h, _, b_id, b_h = _chat_pair(api_client, sqlite_engine)
    assert (
        api_client.post("/api/v1/blocks", json={"blocked_id": b_id}, headers=a_h).status_code == 201
    )
    # Either direction collapses to the same 404 (no block probing).
    assert _ask(api_client, a_h, b_id).status_code == 404
    assert _ask(api_client, b_h, _other_id(api_client, a_h)).status_code == 404


def test_accept_while_blocked_is_409(api_client, sqlite_engine) -> None:
    a_email, a_h, _, b_id, b_h = _chat_pair(api_client, sqlite_engine)
    sent = _ask(api_client, a_h, b_id)
    db = _session(sqlite_engine)
    try:
        a_id = str(db.scalar(select(User).where(User.email == a_email)).id)
    finally:
        db.close()
    assert (
        api_client.post("/api/v1/blocks", json={"blocked_id": a_id}, headers=b_h).status_code == 201
    )
    accept = api_client.post(f"{REQUESTS_PATH}/{sent.json()['id']}/accept", headers=b_h)
    assert accept.status_code == 409
    assert (
        api_client.get(f"{REQUESTS_PATH}/{sent.json()['id']}", headers=b_h).json()["status"]
        == "pending"
    )


def test_lapsed_counterparty_cannot_be_messaged(api_client, sqlite_engine) -> None:
    a_email, a_h, b_email, b_id, b_h, conv = _accepted_pair(api_client, sqlite_engine)
    url = f"{CONVERSATIONS_PATH}/{conv['id']}/messages"
    # Policy back ON with both verified: sending works.
    _set_verification(sqlite_engine, a_email, "verified")
    _set_verification(sqlite_engine, b_email, "verified")
    _flip_policy(sqlite_engine, True, a_email)
    assert api_client.post(url, json={"body": "ok"}, headers=a_h).status_code == 201
    # The counterparty lapses: the old accepted relationship bypasses nothing.
    _set_verification(sqlite_engine, b_email, "unverified")
    refused = api_client.post(url, json={"body": "late"}, headers=a_h)
    assert refused.status_code == 403


def test_accept_rechecks_requester_verification(api_client, sqlite_engine) -> None:
    a_email, a_h, b_email, b_id, b_h = _chat_pair(api_client, sqlite_engine)
    _set_verification(sqlite_engine, a_email, "verified")
    _set_verification(sqlite_engine, b_email, "verified")
    _flip_policy(sqlite_engine, True, a_email)
    sent = _ask(api_client, a_h, b_id)
    assert sent.status_code == 201
    _set_verification(sqlite_engine, a_email, "unverified")
    accept = api_client.post(f"{REQUESTS_PATH}/{sent.json()['id']}/accept", headers=b_h)
    assert accept.status_code == 409
    assert "no longer eligible" in accept.json()["detail"]


def test_message_send_rate_limit_429(api_client, sqlite_engine) -> None:
    reset_rate_limits()
    _, a_h, _, _, _, conv = _accepted_pair(api_client, sqlite_engine)
    url = f"{CONVERSATIONS_PATH}/{conv['id']}/messages"
    for n in range(60):
        resp = api_client.post(url, json={"body": f"burst {n}"}, headers=a_h)
        assert resp.status_code == 201, (n, resp.text)
    limited = api_client.post(url, json={"body": "one too many"}, headers=a_h)
    assert limited.status_code == 429
    reset_rate_limits()
