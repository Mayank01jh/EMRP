"""Routers package."""
from app.routers.auth import router as auth_router
from app.routers.emergency import router as emergency_router
from app.routers.fleet import router as fleet_router
from app.routers.hospitals import router as hospitals_router
from app.routers.dispatcher import router as dispatcher_router
from app.routers.triage import router as triage_router
from app.routers.voice_ivr import router as voice_ivr_router

__all__ = [
    "auth_router",
    "emergency_router",
    "fleet_router",
    "hospitals_router",
    "dispatcher_router",
    "triage_router",
    "voice_ivr_router",
]
