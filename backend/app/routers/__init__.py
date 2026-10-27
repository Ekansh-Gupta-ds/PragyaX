"""
PragyaX Routers Package
"""

from .health import router as health_router
from .auth import router as auth_router
from .subjects import router as subjects_router
from .chat import router as chat_router
from .assessments import router as assessments_router
from .dashboard import router as dashboard_router
from .challenges import router as challenges_router
from .roadmap import router as roadmap_router

__all__ = [
    "health_router",
    "auth_router",
    "subjects_router",
    "chat_router",
    "assessments_router",
    "dashboard_router",
    "challenges_router",
    "roadmap_router"
]
