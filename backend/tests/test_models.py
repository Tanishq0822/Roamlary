"""Tests for Phase 2 model metadata: tables, keys, columns, FKs, constraints."""

import uuid

from sqlalchemy import create_engine, inspect

from app.db.base_class import Base
from app.models import (
    AppSetting,
    CheckIn,
    CommunityReport,
    IdentityVerification,
    SettingChange,
    SosEvent,
    TrustedContact,
    User,
)
from app.models.enums import (
    CheckInStatus,
    ReportCategory,
    ReportStatus,
    SosStatus,
    UserRole,
    VerificationRequestStatus,
    VerificationStatus,
)

EXPECTED_TABLES = {
    "users",
    "trusted_contacts",
    "check_ins",
    "sos_events",
    "community_reports",
    "identity_verifications",
    "app_settings",
    "setting_changes",
}


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


def test_report_category_check_constraint_exists() -> None:
    """Phase 6: the report category is a closed set, guarded by a CHECK
    constraint (added to the database by migration ab32047c8481)."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    inspector = inspect(engine)
    names = {c["name"] for c in inspector.get_check_constraints("community_reports")}
    assert "ck_community_reports_category_valid" in names, names
    engine.dispose()


def test_phase6b_check_constraints_exist() -> None:
    """Phase 6b: account verification state, role, and request status are
    closed sets, each guarded by a database CHECK constraint (the second
    validation layer behind the Python enums)."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    inspector = inspect(engine)
    users_names = {c["name"] for c in inspector.get_check_constraints("users")}
    assert "ck_users_verification_status_valid" in users_names, users_names
    assert "ck_users_role_valid" in users_names, users_names
    request_names = {c["name"] for c in inspector.get_check_constraints("identity_verifications")}
    assert "ck_identity_verifications_status_valid" in request_names, request_names
    engine.dispose()


def test_phase6b_columns_default_to_secure_values() -> None:
    """New accounts get `unverified` + `user` via the model defaults -
    registration can never start anyone verified or privileged."""
    users = Base.metadata.tables["users"]
    assert str(users.columns["verification_status"].default.arg) == "unverified"
    assert str(users.columns["role"].default.arg) == "user"
    assert users.columns["verification_status"].nullable is False
    assert users.columns["role"].nullable is False


def test_phase6b_tables_reference_users() -> None:
    """Every Phase 6b table has an ON DELETE RESTRICT foreign key to
    users, so verification/audit data can never be orphaned or silently
    dropped by deleting an account."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    inspector = inspect(engine)
    expected_columns = {
        "identity_verifications": {"user_id", "reviewed_by"},
        "app_settings": {"updated_by"},
        "setting_changes": {"changed_by"},
    }
    for table_name, wanted in expected_columns.items():
        fks = inspector.get_foreign_keys(table_name)
        found = set()
        for fk in fks:
            if fk["referred_table"] == "users":
                found.update(fk["constrained_columns"])
                assert fk["options"].get("ondelete") == "RESTRICT", table_name
        assert wanted <= found, f"{table_name}: {fks}"
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


def test_report_category_enum_matches_the_contract() -> None:
    """The Phase 6 category set holds exactly the six documented values
    (the Phase 2 model deferred this product decision to Phase 6)."""
    assert {c.value for c in ReportCategory} == {
        "unsafe_area",
        "harassment",
        "suspicious_activity",
        "road_hazard",
        "poor_lighting",
        "other",
    }


def test_verification_enums_match_the_contract() -> None:
    """Phase 6b: the account states, request states, and roles hold
    exactly the documented values - no silent extras."""
    assert {s.value for s in VerificationStatus} == {
        "unverified",
        "pending",
        "verified",
        "rejected",
    }
    assert {s.value for s in VerificationRequestStatus} == {
        "pending",
        "approved",
        "rejected",
    }
    assert {r.value for r in UserRole} == {"user", "owner"}


def test_model_classes_map_to_expected_tables() -> None:
    assert User.__tablename__ == "users"
    assert TrustedContact.__tablename__ == "trusted_contacts"
    assert CheckIn.__tablename__ == "check_ins"
    assert SosEvent.__tablename__ == "sos_events"
    assert CommunityReport.__tablename__ == "community_reports"
    assert IdentityVerification.__tablename__ == "identity_verifications"
    assert AppSetting.__tablename__ == "app_settings"
    assert SettingChange.__tablename__ == "setting_changes"
