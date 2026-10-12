"""Tests for Phase 2 model metadata: tables, keys, columns, FKs, constraints."""

import uuid

from sqlalchemy import create_engine, inspect

from app.db.base_class import Base
from app.models import CheckIn, CommunityReport, SosEvent, TrustedContact, User
from app.models.enums import CheckInStatus, ReportStatus, SosStatus

EXPECTED_TABLES = {"users", "trusted_contacts", "check_ins", "sos_events", "community_reports"}


def test_all_tables_are_registered() -> None:
    """Importing app.models registers every expected table."""
    assert EXPECTED_TABLES.issubset(set(Base.metadata.tables))


def test_primary_keys_are_uuid_columns() -> None:
    """Every table uses a single UUID primary key named `id`."""
    for table_name in EXPECTED_TABLES:
        table = Base.metadata.tables[table_name]
        pk_columns = list(table.primary_key.columns)
        assert len(pk_columns) == 1, table_name
        assert pk_columns[0].name == "id", table_name
        assert pk_columns[0].type.python_type is uuid.UUID, table_name


def test_user_columns_and_uniqueness() -> None:
    users = Base.metadata.tables["users"]
    assert users.columns["display_name"].nullable is False
    assert users.columns["email"].nullable is True
    assert users.columns["firebase_uid"].nullable is True
    assert users.columns["email"].unique is True
    assert users.columns["firebase_uid"].unique is True


def test_foreign_keys_reference_users_table() -> None:
    """Every child table references users.id (owner relationship).

    Metadata is inspected via a throwaway in-memory database, so no
    real database is needed for this check.
    """
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    inspector = inspect(engine)
    for table_name in ("trusted_contacts", "check_ins", "sos_events", "community_reports"):
        fks = inspector.get_foreign_keys(table_name)
        user_fks = [fk for fk in fks if fk["referred_table"] == "users"]
        assert user_fks, table_name
        assert user_fks[0]["constrained_columns"] == ["user_id"], table_name
        assert user_fks[0]["referred_columns"] == ["id"], table_name
    engine.dispose()


def test_status_check_constraints_exist() -> None:
    """Status columns are protected by database CHECK constraints."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    inspector = inspect(engine)
    expected = {
        "check_ins": "ck_check_ins_status_valid",
        "sos_events": "ck_sos_events_status_valid",
        "community_reports": "ck_community_reports_status_valid",
    }
    for table_name, constraint_name in expected.items():
        names = {c["name"] for c in inspector.get_check_constraints(table_name)}
        assert constraint_name in names, f"{table_name}: {names}"
    engine.dispose()


def test_location_range_check_constraints_exist() -> None:
    """Latitude/longitude guard rails exist on location-bearing tables."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    inspector = inspect(engine)
    for table_name in ("sos_events", "community_reports"):
        names = {c["name"] for c in inspector.get_check_constraints(table_name)}
        assert f"ck_{table_name}_latitude_range" in names, table_name
        assert f"ck_{table_name}_longitude_range" in names, table_name
    engine.dispose()


def test_status_enums_match_the_contract() -> None:
    """The Python status enums hold exactly the documented values.

    'cancelled' was added to CheckInStatus in Phase 4 (users must be
    able to abandon a check-in) and to SosStatus in Phase 5 (users must
    be able to retract an SOS); the rest are the Phase 2 design.
    """
    assert {s.value for s in CheckInStatus} == {
        "pending",
        "safe",
        "needs_help",
        "expired",
        "cancelled",
    }
    assert {s.value for s in SosStatus} == {
        "active",
        "acknowledged",
        "resolved",
        "false_alarm",
        "cancelled",
    }
    assert {s.value for s in ReportStatus} == {"pending", "approved", "rejected"}


def test_model_classes_map_to_expected_tables() -> None:
    assert User.__tablename__ == "users"
    assert TrustedContact.__tablename__ == "trusted_contacts"
    assert CheckIn.__tablename__ == "check_ins"
    assert SosEvent.__tablename__ == "sos_events"
    assert CommunityReport.__tablename__ == "community_reports"
