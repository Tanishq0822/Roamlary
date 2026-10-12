"""Domain models package.

Importing this package registers EVERY table with SQLAlchemy's
registry. This is exactly how Alembic discovers the schema: alembic/env.py
imports `app.models`, compares the registered tables with the database,
and can then generate accurate migrations.
"""

from app.models.app_setting import AppSetting
from app.models.check_in import CheckIn
from app.models.community_report import CommunityReport
from app.models.enums import (
    CheckInStatus,
    ReportStatus,
    SosStatus,
    UserRole,
    VerificationRequestStatus,
    VerificationStatus,
)
from app.models.identity_verification import IdentityVerification
from app.models.setting_change import SettingChange
from app.models.sos_event import SosEvent
from app.models.trusted_contact import TrustedContact
from app.models.user import User

__all__ = [
    "AppSetting",
    "CheckIn",
    "CheckInStatus",
    "CommunityReport",
    "IdentityVerification",
    "ReportStatus",
    "SettingChange",
    "SosEvent",
    "SosStatus",
    "TrustedContact",
    "User",
    "UserRole",
    "VerificationRequestStatus",
    "VerificationStatus",
]
