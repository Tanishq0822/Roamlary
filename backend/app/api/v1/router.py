"""Version 1 API router aggregation."""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    admin,
    ai,
    auth,
    blocks,
    chat,
    check_ins,
    community_reports,
    health,
    meetups,
    notifications,
    parties,
    social,
    sos_events,
    travel_buddies,
    travel_plans,
    travel_profile,
    trip_shares,
    trusted_contacts,
    users,
    verification,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(blocks.router)
api_router.include_router(chat.router)
api_router.include_router(meetups.router)
api_router.include_router(parties.router)
api_router.include_router(parties.invitations_router)
api_router.include_router(notifications.router)
api_router.include_router(trip_shares.router)
api_router.include_router(ai.router)
api_router.include_router(trusted_contacts.router)
api_router.include_router(check_ins.router)
api_router.include_router(sos_events.router)
api_router.include_router(community_reports.router)
api_router.include_router(verification.router)
api_router.include_router(admin.router)
api_router.include_router(social.router)
api_router.include_router(travel_profile.router)
api_router.include_router(travel_plans.router)
api_router.include_router(travel_buddies.router)
