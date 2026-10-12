"""Trusted-contact endpoints (Phase 4).

Plain language: these routes let a logged-in user save the people who
should be reachable in an emergency. Two ideas govern every handler:

1. OWNERSHIP COMES FROM THE TOKEN. The user_id is always taken from the
   verified JWT via `current_user`, never from the URL or body. Every
   query filters on that user_id, so one user's data is invisible to
   another - you cannot read, edit, or delete someone else's contact by
   guessing its ID.

2. ONE 404 FOR "NOT YOURS" AND "DOES NOT EXIST". A request for a
   contact that belongs to someone else returns exactly the same 404 as
   a request for an ID that was never real. This avoids telling a
   caller which IDs exist (an enumeration leak).

SAFETY BOUNDARY: saving a contact stores a name and a number. Nothing
is sent, no one is notified, and no number is verified as reachable.
That is explicit Phase 4 scope - notifications belong to later phases.
"""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.v1.deps import CurrentUser, DbSession
from app.api.v1.schemas.trusted_contact import (
    TrustedContactCreate,
    TrustedContactRead,
    TrustedContactUpdate,
)
from app.db.base_class import utc_now
from app.models.trusted_contact import TrustedContact

router = APIRouter(prefix="/trusted-contacts", tags=["trusted-contacts"])


def _get_owned_contact(contact_id: UUID, current_user, db) -> TrustedContact:
    """Load a contact by ID, but ONLY if it belongs to the current user.

    Returns the contact or raises the same 404 in every not-found case
    (wrong owner or nonexistent ID), so ownership cannot be probed.
    """
    contact = db.scalar(
        select(TrustedContact).where(
            TrustedContact.id == contact_id,
            TrustedContact.user_id == current_user.id,
        )
    )
    if contact is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trusted contact not found.",
        )
    return contact


@router.post(
    "/",
    response_model=TrustedContactRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a trusted contact for the authenticated user",
)
def create_trusted_contact(
    body: TrustedContactCreate,
    current_user: CurrentUser,
    db: DbSession,
) -> TrustedContactRead:
    """Save a new contact. The owner is ALWAYS the token's user.

    The request schema has no `user_id` field and forbids extra fields,
    so a client cannot create a contact for anyone else. Duplicate
    rows are allowed (a user may deliberately save the same person
    twice); there is no uniqueness rule on contacts.
    """
    contact = TrustedContact(
        user_id=current_user.id,
        name=body.name,
        phone=body.phone,
        relationship=body.relationship,
        email=body.email,
    )
    db.add(contact)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Could not save the trusted contact.",
        ) from exc
    db.refresh(contact)
    return TrustedContactRead.model_validate(contact)


@router.get(
    "/",
    response_model=list[TrustedContactRead],
    summary="List the authenticated user's trusted contacts",
)
def list_trusted_contacts(
    current_user: CurrentUser,
    db: DbSession,
) -> list[TrustedContactRead]:
    """Return ONLY the caller's contacts, oldest first (stable order).

    The WHERE clause on user_id is what keeps other users' contacts out.
    There is no pagination yet (documented limitation); the prototype
    assumes a user has a handful of contacts, not thousands.
    """
    contacts = db.scalars(
        select(TrustedContact)
        .where(TrustedContact.user_id == current_user.id)
        .order_by(TrustedContact.created_at, TrustedContact.id)
    ).all()
    return [TrustedContactRead.model_validate(c) for c in contacts]


@router.get(
    "/{contact_id}",
    response_model=TrustedContactRead,
    summary="Return one of the authenticated user's trusted contacts",
)
def get_trusted_contact(
    contact_id: UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> TrustedContactRead:
    """Fetch a single contact. 404 if it is missing OR not yours."""
    contact = _get_owned_contact(contact_id, current_user, db)
    return TrustedContactRead.model_validate(contact)


@router.patch(
    "/{contact_id}",
    response_model=TrustedContactRead,
    summary="Update fields on one of the user's trusted contacts",
)
def update_trusted_contact(
    contact_id: UUID,
    body: TrustedContactUpdate,
    current_user: CurrentUser,
    db: DbSession,
) -> TrustedContactRead:
    """Update any subset of name/phone/relationship/email.

    The schema forbids `user_id`, `id`, and timestamps, so ownership and
    identity can never be edited here - only the contact's details.

    `body.model_fields_set` lists exactly the fields the client actually
    sent, which lets us tell "field omitted" (leave it alone) apart from
    "field explicitly null" (clear it - e.g. remove an email). An empty
    body is a valid no-op: the record is returned unchanged and
    `updated_at` is NOT touched.
    """
    contact = _get_owned_contact(contact_id, current_user, db)

    sent = body.model_fields_set
    if "name" in sent:
        # name/phone were validated as non-null by the schema's min
        # length rules, but a null would fail there too.
        if body.name is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="name cannot be null.",
            )
        contact.name = body.name
    if "phone" in sent:
        if body.phone is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="phone cannot be null.",
            )
        contact.phone = body.phone
    if "relationship" in sent:
        contact.relationship = body.relationship
    if "email" in sent:
        contact.email = body.email

    if sent:
        contact.updated_at = utc_now()
        db.add(contact)
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Could not save the trusted contact.",
            ) from exc
        db.refresh(contact)

    return TrustedContactRead.model_validate(contact)


@router.delete(
    "/{contact_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete one of the authenticated user's trusted contacts",
)
def delete_trusted_contact(
    contact_id: UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> None:
    """Delete a contact. 404 if it is missing OR not yours.

    Deleting a contact removes ONLY that row - the user account and all
    other records (check-ins, other contacts) are untouched, which the
    test suite verifies explicitly.
    """
    contact = _get_owned_contact(contact_id, current_user, db)
    db.delete(contact)
    db.commit()
    # No body on 204; returning None tells FastAPI to send no content.
