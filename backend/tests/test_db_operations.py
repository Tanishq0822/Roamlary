"""Database behaviour tests (SQLite in-memory): create/read, relationships,
defaults, deletion protection and session lifecycle."""

from datetime import datetime

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import CheckIn, CommunityReport, SosEvent, TrustedContact, User
from app.models.enums import CheckInStatus, ReportStatus, SosStatus


def test_create_and_read_user(db_session: Session) -> None:
    db_session.add(User(display_name="Asha", email="asha@example.com"))
    db_session.commit()

    saved = db_session.query(User).one()
    assert saved.id is not None
    assert saved.display_name == "Asha"
    assert isinstance(saved.created_at, datetime)
    assert isinstance(saved.updated_at, datetime)


def test_user_optional_fields_allow_minimal_profile(db_session: Session) -> None:
    """A profile with only a display name is valid (email/fb uid optional)."""
    db_session.add(User(display_name="Ravi"))
    db_session.commit()

    saved = db_session.query(User).one()
    assert saved.email is None
    assert saved.firebase_uid is None


def test_duplicate_email_is_rejected(db_session: Session) -> None:
    db_session.add(User(display_name="A", email="same@example.com"))
    db_session.add(User(display_name="B", email="same@example.com"))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_user_with_trusted_contact_relationship(db_session: Session) -> None:
    """Contacts attach to a user and are reachable from both directions."""
    user = User(display_name="Asha")
    contact = TrustedContact(name="Mom", phone="+911234567890", owner=user)
    db_session.add(contact)
    db_session.commit()

    # Child -> parent
    reloaded_contact = db_session.query(TrustedContact).one()
    assert reloaded_contact.owner.display_name == "Asha"
    # Parent -> children
    reloaded_user = db_session.query(User).one()
    assert [c.name for c in reloaded_user.trusted_contacts] == ["Mom"]


def test_contact_requires_an_owner(db_session: Session) -> None:
    """user_id is NOT NULL - a contact without an owner is impossible."""
    db_session.add(TrustedContact(name="Orphan", phone="+0000000000"))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_check_in_defaults_to_pending(db_session: Session) -> None:
    user = User(display_name="Asha")
    db_session.add(CheckIn(user=user))
    db_session.commit()

    saved = db_session.query(CheckIn).one()
    assert saved.status == CheckInStatus.PENDING
    assert saved.due_at is None
    assert saved.completed_at is None


def test_check_in_invalid_status_is_rejected(db_session: Session) -> None:
    """The CHECK constraint blocks statuses outside the enum values."""
    user = User(display_name="Asha")
    db_session.add(user)
    db_session.flush()
    db_session.add(CheckIn(user=user, status="not-a-status"))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_sos_event_defaults_and_location_stored(db_session: Session) -> None:
    user = User(display_name="Asha")
    db_session.add(SosEvent(user=user, latitude=28.6139, longitude=77.2090))
    db_session.commit()

    saved = db_session.query(SosEvent).one()
    assert saved.status == SosStatus.ACTIVE
    assert saved.resolved_at is None
    assert saved.latitude == pytest.approx(28.6139)
    assert saved.longitude == pytest.approx(77.2090)


def test_sos_event_out_of_range_location_rejected(db_session: Session) -> None:
    user = User(display_name="Asha")
    db_session.add(SosEvent(user=user, latitude=999.0))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_community_report_created_pending(db_session: Session) -> None:
    """A fresh report is stored as `pending` with its category intact.

    The sample category is `poor_lighting`: Phase 6 turned the Phase 2
    loose category string into a closed set (ReportCategory) enforced by
    a CHECK constraint, so values like the old "lighting" sample are now
    rejected by the database.
    """
    user = User(display_name="Asha")
    db_session.add(
        CommunityReport(
            user=user, category="poor_lighting", description="Dark square near the station"
        )
    )
    db_session.commit()

    saved = db_session.query(CommunityReport).one()
    assert saved.status == ReportStatus.PENDING
    assert saved.category == "poor_lighting"


def test_deleting_user_with_safety_records_is_restricted(db_session: Session) -> None:
    """ON DELETE RESTRICT: safety history can never vanish with a user."""
    user = User(display_name="Asha")
    db_session.add(TrustedContact(name="Mom", phone="+911", owner=user))
    db_session.commit()

    db_session.delete(user)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
    # The user and the contact both still exist.
    assert db_session.query(User).count() == 1
    assert db_session.query(TrustedContact).count() == 1


def test_updated_at_changes_on_modification(db_session: Session) -> None:
    user = User(display_name="Asha")
    db_session.add(user)
    db_session.commit()
    # Re-read from the database first so both captured values have the
    # same representation before comparing them.
    db_session.refresh(user)
    first_updated = user.updated_at

    user.display_name = "Asha K"
    db_session.commit()
    db_session.refresh(user)
    assert user.updated_at > first_updated


def test_get_db_yields_a_session_and_always_closes_it() -> None:
    """The FastAPI dependency provides one session and closes it on exit.

    Runs fully offline: creating/closing a session never opens a
    database connection.
    """
    dependency = get_db()
    db = next(dependency)
    assert isinstance(db, Session)
    with pytest.raises(StopIteration):
        next(dependency)  # generator finished -> finally block ran -> closed
