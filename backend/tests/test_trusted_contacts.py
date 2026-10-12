"""Trusted-contact endpoint tests (Phase 4).

These drive the real FastAPI app end-to-end against the in-memory SQLite
database via the shared `api_client` fixture (register -> token ->
authenticated call). They prove the two headline guarantees: a user can
manage their own contacts, and cannot see or touch anyone else's.
"""

from tests.conftest import register_user

BASE = "/api/v1/trusted-contacts/"


def _create(client, headers, **overrides):
    """Create a contact with sensible defaults, overridable per test."""
    payload = {"name": "Asha", "phone": "+91 98765 43210"}
    payload.update(overrides)
    return client.post(BASE, json=payload, headers=headers)


# --------------------------------------------------------------- creation


def test_create_contact_succeeds_and_returns_public_fields(api_client):
    uid, h = register_user(api_client, "owner@example.com")
    resp = _create(api_client, h, relationship="friend", email="asha@example.com")
    assert resp.status_code == 201
    body = resp.json()
    # Exact approved field set - nothing internal can leak.
    assert set(body) == {
        "id",
        "user_id",
        "name",
        "phone",
        "relationship",
        "email",
        "created_at",
        "updated_at",
    }
    assert body["user_id"] == uid
    assert body["name"] == "Asha"
    assert body["relationship"] == "friend"


def test_unauthenticated_requests_rejected(api_client):
    assert api_client.post(BASE, json={"name": "X", "phone": "1234567"}).status_code == 401
    assert api_client.get(BASE).status_code == 401
    assert api_client.get(BASE + "00000000-0000-0000-0000-000000000000").status_code == 401


def test_missing_required_information_rejected(api_client):
    _, h = register_user(api_client, "a@example.com")
    # No name.
    assert api_client.post(BASE, json={"phone": "1234567"}, headers=h).status_code == 422
    # No phone.
    assert api_client.post(BASE, json={"name": "X"}, headers=h).status_code == 422
    # Empty body.
    assert api_client.post(BASE, json={}, headers=h).status_code == 422


def test_invalid_inputs_rejected(api_client):
    _, h = register_user(api_client, "b@example.com")
    # Malformed phone (too short / letters).
    assert _create(api_client, h, phone="123").status_code == 422
    assert _create(api_client, h, phone="not-a-number").status_code == 422
    # Blank name (whitespace only).
    assert _create(api_client, h, name="   ").status_code == 422
    # Bad email.
    assert _create(api_client, h, email="not-an-email").status_code == 422
    # Overlong name.
    assert _create(api_client, h, name="x" * 81).status_code == 422


def test_client_supplied_user_id_cannot_establish_ownership(api_client):
    """A smuggled user_id must be a 422, never honored."""
    uid, h = register_user(api_client, "c@example.com")
    resp = api_client.post(
        BASE,
        json={
            "name": "X",
            "phone": "1234567",
            "user_id": "00000000-0000-0000-0000-000000000000",
        },
        headers=h,
    )
    assert resp.status_code == 422
    # And the contact, when created cleanly, is owned by the caller.
    assert _create(api_client, h).json()["user_id"] == uid


def test_phone_normalization_is_consistent(api_client):
    _, h = register_user(api_client, "d@example.com")
    body = _create(api_client, h, phone=" +1 (415) 555-2671 ").json()
    assert body["phone"] == "+14155552671"


# ------------------------------------------------------------------- reads


def test_list_returns_only_own_contacts_oldest_first(api_client):
    uid_a, h_a = register_user(api_client, "alice@example.com")
    uid_b, h_b = register_user(api_client, "bob@example.com")
    _create(api_client, h_a, name="A1")
    _create(api_client, h_a, name="A2")
    _create(api_client, h_b, name="B1")

    a_list = api_client.get(BASE, headers=h_a).json()
    assert [c["name"] for c in a_list] == ["A1", "A2"]
    assert all(c["user_id"] == uid_a for c in a_list)

    b_list = api_client.get(BASE, headers=h_b).json()
    assert [c["name"] for c in b_list] == ["B1"]
    assert all(c["user_id"] == uid_b for c in b_list)


def test_get_own_contact_succeeds(api_client):
    _, h = register_user(api_client, "e@example.com")
    created = _create(api_client, h).json()
    resp = api_client.get(BASE + created["id"], headers=h)
    assert resp.status_code == 200
    assert resp.json()["id"] == created["id"]


def test_cannot_get_another_users_contact(api_client):
    _, h_owner = register_user(api_client, "f@example.com")
    _, h_thief = register_user(api_client, "g@example.com")
    created = _create(api_client, h_owner).json()
    assert api_client.get(BASE + created["id"], headers=h_thief).status_code == 404


def test_not_found_and_not_owned_return_identical_404(api_client):
    """No ownership enumeration: a real-but-foreign ID and a fake ID
    must be indistinguishable to the caller."""
    _, h_owner = register_user(api_client, "h@example.com")
    _, h_thief = register_user(api_client, "i@example.com")
    created = _create(api_client, h_owner).json()
    foreign = api_client.get(BASE + created["id"], headers=h_thief)
    missing = api_client.get(BASE + "00000000-0000-0000-0000-000000000000", headers=h_thief)
    assert foreign.status_code == missing.status_code == 404
    assert foreign.json() == missing.json()


# ----------------------------------------------------------------- updates


def test_update_own_contact_succeeds(api_client):
    _, h = register_user(api_client, "j@example.com")
    created = _create(api_client, h).json()
    resp = api_client.patch(
        BASE + created["id"], json={"name": "Renamed", "phone": "2223334444"}, headers=h
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "Renamed"
    assert body["phone"] == "2223334444"
    # Untouched fields stay put.
    assert body["email"] == created["email"]


def test_cannot_update_another_users_contact(api_client):
    _, h_owner = register_user(api_client, "k@example.com")
    _, h_thief = register_user(api_client, "l@example.com")
    created = _create(api_client, h_owner).json()
    resp = api_client.patch(BASE + created["id"], json={"name": "Hacked"}, headers=h_thief)
    assert resp.status_code == 404
    # Owner's record unchanged.
    assert api_client.get(BASE + created["id"], headers=h_owner).json()["name"] == "Asha"


def test_update_cannot_change_user_id(api_client):
    uid, h = register_user(api_client, "m@example.com")
    created = _create(api_client, h).json()
    resp = api_client.patch(
        BASE + created["id"],
        json={"user_id": "00000000-0000-0000-0000-000000000000"},
        headers=h,
    )
    assert resp.status_code == 422
    assert api_client.get(BASE + created["id"], headers=h).json()["user_id"] == uid


# ----------------------------------------------------------------- delete


def test_delete_own_contact_succeeds(api_client):
    _, h = register_user(api_client, "n@example.com")
    created = _create(api_client, h).json()
    assert api_client.delete(BASE + created["id"], headers=h).status_code == 204
    assert api_client.get(BASE + created["id"], headers=h).status_code == 404


def test_cannot_delete_another_users_contact(api_client):
    _, h_owner = register_user(api_client, "o@example.com")
    _, h_thief = register_user(api_client, "p@example.com")
    created = _create(api_client, h_owner).json()
    assert api_client.delete(BASE + created["id"], headers=h_thief).status_code == 404
    # Still there for the owner.
    assert api_client.get(BASE + created["id"], headers=h_owner).status_code == 200


def test_delete_does_not_remove_unrelated_records(api_client, db_session):
    """Deleting one contact must not cascade to the user or their
    check-ins or other contacts."""
    from uuid import UUID

    from sqlalchemy import select

    from app.models.check_in import CheckIn
    from app.models.trusted_contact import TrustedContact
    from app.models.user import User

    uid_str, h = register_user(api_client, "q@example.com")
    uid = UUID(uid_str)
    keep = _create(api_client, h, name="Keep").json()
    doomed = _create(api_client, h, name="Doomed").json()
    api_client.post("/api/v1/check-ins/", json={"note": "hike"}, headers=h)  # unrelated record

    assert api_client.delete(BASE + doomed["id"], headers=h).status_code == 204

    remaining = db_session.scalars(
        select(TrustedContact).where(TrustedContact.user_id == uid)
    ).all()
    assert [c.name for c in remaining] == ["Keep"]
    assert keep["id"] in [str(c.id) for c in remaining]
    # The user's check-in is untouched.
    assert db_session.scalars(select(CheckIn).where(CheckIn.user_id == uid)).all() != []
    # And the user row itself survives.
    assert db_session.get(User, uid) is not None
