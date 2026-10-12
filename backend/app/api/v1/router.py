"""Version 1 API router aggregation."""

from fastapi import APIRouter

from app.api.v1.endpoints import auth, check_ins, health, sos_events, trusted_contacts, users

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(trusted_contacts.router)
api_router.include_router(check_ins.router)
api_router.include_router(sos_events.router)
