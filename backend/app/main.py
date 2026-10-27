"""
EMRP FastAPI Application — Main Entry Point

Lifespan:
  - Connect MongoDB replica set
  - Connect Redis
  - Initialise Arq pool for enqueuing background jobs

Middleware:
  - CORS
  - Request ID injection
  - Structured access logging
  - Global error envelope

Routes:
  /api/v1/auth/       — authentication
  /api/v1/emergency/  — SOS creation and tracking
  /api/v1/fleet/      — ambulance fleet management
  /api/v1/hospitals/  — hospital registry
  /api/v1/dispatcher/ — dispatcher console
"""
from __future__ import annotations

import time
import uuid
from contextlib import asynccontextmanager
from typing import Any

import structlog
try:
    from arq import create_pool
    from arq.connections import RedisSettings
except ImportError:
    create_pool = None
    RedisSettings = None
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.database import connect_db, close_db
from app.core.logging import configure_logging, logger
from app.core.redis_client import connect_redis, close_redis
from app.routers import (
    auth_router, emergency_router, fleet_router,
    hospitals_router, dispatcher_router, triage_router,
    voice_ivr_router,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown."""
    configure_logging()
    settings = get_settings()

    logger.info("EMRP starting up", environment=settings.environment)

    try:
        await connect_db()
        logger.info("MongoDB connected")
    except Exception as e:
        logger.warning("MongoDB not reached (running in offline/dev mode)", error=str(e))

    try:
        await connect_redis()
        logger.info("Redis connected")
        if create_pool and RedisSettings:
            app.state.arq = await create_pool(RedisSettings.from_dsn(settings.redis_url))
            logger.info("Arq pool ready")
        else:
            app.state.arq = None
    except Exception as e:
        logger.warning("Redis/Arq not reached (running in offline/dev mode)", error=str(e))
        app.state.arq = None

    yield

    logger.info("EMRP shutting down")
    if getattr(app.state, "arq", None):
        await app.state.arq.aclose()
    await close_redis()
    await close_db()
    logger.info("Shutdown complete")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Emergency Medical Response Platform",
        description=(
            "Real-time emergency dispatch API. "
            "Handles SOS creation, ambulance dispatch, hospital pre-alerts, "
            "and live status tracking."
        ),
        version="1.0.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )

    # ── CORS ──────────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Request ID + Logging Middleware ───────────────────────────────────────
    @app.middleware("http")
    async def request_logging(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        start = time.perf_counter()
        response: Response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000

        logger.info(
            "HTTP",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            elapsed_ms=round(elapsed_ms, 2),
        )
        response.headers["X-Request-ID"] = request_id
        return response

    # ── Global Error Handler ──────────────────────────────────────────────────
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error("Unhandled exception", exc_info=exc, path=request.url.path)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error", "type": type(exc).__name__},
        )

    # ── Routers ───────────────────────────────────────────────────────────────
    prefix = "/api/v1"
    app.include_router(auth_router, prefix=prefix)
    app.include_router(emergency_router, prefix=prefix)
    app.include_router(fleet_router, prefix=prefix)
    app.include_router(hospitals_router, prefix=prefix)
    app.include_router(dispatcher_router, prefix=prefix)
    app.include_router(triage_router, prefix=prefix)
    app.include_router(voice_ivr_router, prefix=prefix)

    # ── Health Check ─────────────────────────────────────────────────────────
    @app.get("/health", tags=["Health"])
    async def health():
        return {"status": "ok", "service": "emrp-backend"}

    return app


app = create_app()
