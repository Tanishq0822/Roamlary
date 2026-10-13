"""Domain models package.

Importing this package registers EVERY table with SQLAlchemy's
registry. This is exactly how Alembic discovers the schema: alembic/env.py
imports `app.models`, compares the registered tables with the database,
and can then generate accurate migrations.
"""

from app.models.app_setting import AppSetting
from app.models.auth_session import AuthSession
from app.models.check_in import CheckIn
from app.models.community_report import CommunityReport
from app.models.conversation import Conversation
from app.models.enums import (
    BuddyRequestStatus,
    CheckInStatus,
    ConversationStatus,
    InvitationStatus,
    MeetupCategory,
    MeetupKind,
    MeetupStatus,
    MeetupVisibility,
    MembershipStatus,
    NotificationStatus,
    ParticipationPolicy,
    PlanVisibility,
    ReportStatus,
    SosStatus,
    TravelPlanStatus,
    UserRole,
    VerificationRequestStatus,
    VerificationStatus,
)
from app.models.event_invitation import EventInvitation
from app.models.identity_verification import IdentityVerification
from app.models.meetup import Meetup
from app.models.meetup_announcement import MeetupAnnouncement
from app.models.meetup_membership import MeetupMembership
from app.models.message import ChatMessage
from app.models.notification import Notification
from app.models.setting_change import SettingChange
from app.models.sos_event import SosEvent
from app.models.travel_partner_request import TravelPartnerRequest
from app.models.travel_plan import TravelPlan
from app.models.travel_profile import TravelProfile
from app.models.trip_share import TripShare
from app.models.trusted_contact import TrustedContact
from app.models.user import User
from app.models.user_block import UserBlock

__all__ = [
    "AppSetting",
    "AuthSession",
    "BuddyRequestStatus",
    "ChatMessage",
    "CheckIn",
    "CheckInStatus",
    "CommunityReport",
    "Conversation",
    "ConversationStatus",
    "EventInvitation",
    "IdentityVerification",
    "InvitationStatus",
    "Meetup",
    "MeetupAnnouncement",
    "MeetupCategory",
    "MeetupKind",
    "MeetupMembership",
    "MeetupStatus",
    "MeetupVisibility",
    "MembershipStatus",
    "Notification",
    "NotificationStatus",
    "ParticipationPolicy",
    "PlanVisibility",
    "ReportStatus",
    "SettingChange",
    "SosEvent",
    "SosStatus",
    "TravelPartnerRequest",
    "TravelPlan",
    "TravelPlanStatus",
    "TravelProfile",
    "TripShare",
    "TrustedContact",
    "User",
    "UserBlock",
    "UserRole",
    "VerificationRequestStatus",
    "VerificationStatus",
]
