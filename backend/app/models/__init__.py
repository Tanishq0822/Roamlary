"""Domain models package.

Importing this package registers EVERY table with SQLAlchemy's
registry. This is exactly how Alembic discovers the schema: alembic/env.py
imports `app.models`, compares the registered tables with the database,
and can then generate accurate migrations.
"""

from app.models.check_in import CheckIn
from app.models.community_report import CommunityReport
from app.models.enums import CheckInStatus, ReportStatus, SosStatus
from app.models.sos_event import SosEvent
from app.models.trusted_contact import TrustedContact
from app.models.user import User

__all__ = [
    "CheckIn",
    "CheckInStatus",
    "CommunityReport",
    "ReportStatus",
    "SosEvent",
    "SosStatus",
    "TrustedContact",
    "User",
]
