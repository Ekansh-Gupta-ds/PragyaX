"""
PragyaX FastAPI Application Entrypoint
Owned by: Arsh (FastAPI Backend Architecture)
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from .database.connection import init_db, close_db_pool
from .routers import (
    health_router,
    auth_router,
    subjects_router,
    chat_router,
    assessments_router,
    dashboard_router,
    challenges_router,
    roadmap_router
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database (PostgreSQL connection pool or SQLite) on startup
    init_db()
    try:
        yield
    finally:
        close_db_pool()


app = FastAPI(
    title="PragyaX API",
    description="Backend API for PragyaX — AI-Powered Gamified Learning: From Theory to Practice",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# CORS configuration for Vite local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API Routers
app.include_router(health_router, prefix=settings.API_PREFIX)
app.include_router(auth_router, prefix=settings.API_PREFIX)
app.include_router(subjects_router, prefix=settings.API_PREFIX)
app.include_router(chat_router, prefix=settings.API_PREFIX)
app.include_router(assessments_router, prefix=settings.API_PREFIX)
app.include_router(dashboard_router, prefix=settings.API_PREFIX)
app.include_router(challenges_router, prefix=settings.API_PREFIX)
app.include_router(roadmap_router, prefix=settings.API_PREFIX)


@app.get("/")
def root():
    return {
        "message": "Welcome to PragyaX API — AI-Powered Gamified Learning",
        "documentation": "/docs",
        "health_check": f"{settings.API_PREFIX}/health"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
