# backend/app/main.py

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import List

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from app.core.config import settings

# ✅ DB lifecycle
from app.core.database import db, connect_to_mongo, close_mongo_connection

# API routers
from app.api import (
    admin,
    ai_agent,
    analytics,
    auth,
    files,
    invoices,
    reports,
    sunsynk,
    gemini_ai,
)

from app.api.recent_activities import router as recent_activities_router
from app.api.assets_sunsynk import router as assets_sunsynk_router
from app.api.assets import router as projects_router
from app.api.meters import router as meters_router

# ✅ Email router (only if it exists)
try:
    from app.api import email as email_router
    HAS_EMAIL = True
except Exception:
    email_router = None
    HAS_EMAIL = False

# Services (optional)
from app.services.egauge_poller import start_egauge_scheduler

logger = logging.getLogger(__name__)

logging.basicConfig(
    level=logging.DEBUG if getattr(settings, "DEBUG", False) else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

app = FastAPI(
    title="ESG Dashboard API",
    version="1.0.0",
    description="API for ESG Dashboard",
    docs_url="/docs" if getattr(settings, "DEBUG", False) else None,
    redoc_url="/redoc" if getattr(settings, "DEBUG", False) else None,
)

# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    content_type = request.headers.get("content-type", "")
    logger.warning(
        f"422 ValidationError on {request.method} {request.url.path} "
        f"(content-type={content_type}) errors={exc.errors()}"
    )
    return JSONResponse(
        status_code=422,
        content={
            "detail": exc.errors(),
            "path": str(request.url.path),
            "method": request.method,
            "content_type": content_type,
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled exception on {request.method} {request.url}")
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "path": str(request.url.path),
            "method": request.method,
            "error": str(exc) if getattr(settings, "DEBUG", False) else None,
        },
    )

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
def _split_csv(value: str | None) -> List[str]:
    if not value:
        return []
    return [v.strip().rstrip("/") for v in value.split(",") if v and v.strip()]


def _build_cors_origins() -> List[str]:
    origins = [
        # Local dev
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3002",
        "http://127.0.0.1:3002",
        # Vercel prod
        "https://esgfrontend-delta.vercel.app",
    ]

    # FRONTEND_URL (single origin)
    if getattr(settings, "FRONTEND_URL", None):
        origins.append(str(settings.FRONTEND_URL).strip().rstrip("/"))

    # CORS_ORIGINS from settings (JSON list or CSV)
    try:
        env_origins = settings.get_cors_origins()
    except Exception as e:
        logger.warning(f"Failed to parse CORS_ORIGINS from settings: {e}")
        env_origins = _split_csv(os.getenv("CORS_ORIGINS"))

    for o in env_origins or []:
        o = (o or "").strip().rstrip("/")
        if not o:
            continue
        if o == "*":
            logger.warning("CORS_ORIGINS contains '*'. Ignoring '*' and using explicit allow-list.")
            continue
        origins.append(o)

    # de-dup
    merged: List[str] = []
    for o in origins:
        o = (o or "").strip().rstrip("/")
        if o and o not in merged:
            merged.append(o)
    return merged


cors_origins = _build_cors_origins()
logger.info(f"CORS origins configured: {cors_origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=False,     # Authorization Bearer token, not cookies
    allow_methods=["*"],
    allow_headers=["*"],         # includes Authorization
)

# Optional: speed up preflight
@app.options("/{full_path:path}")
async def preflight(full_path: str, request: Request):
    return Response(status_code=204)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])
app.include_router(sunsynk.router, prefix="/api/sunsynk", tags=["sunsynk"])
app.include_router(assets_sunsynk_router, prefix="/api/assets", tags=["assets-sunsynk"])

# invoices had no prefix; keep as-is
app.include_router(invoices.router, tags=["invoices"])

app.include_router(files.router, prefix="/api/files", tags=["files"])
app.include_router(projects_router, prefix="/api/assets", tags=["assets"])
app.include_router(meters_router, prefix="/api/meters", tags=["meters"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["analytics"])
app.include_router(reports.router, prefix="/api/reports", tags=["reports"])

# ✅ IMPORTANT: gemini_ai.py already has prefix="/api/gemini" inside the router
app.include_router(gemini_ai.router)

# ai_agent is mounted at /api/ai
app.include_router(ai_agent.router, prefix="/api/ai", tags=["AI Agent"])

app.include_router(recent_activities_router, tags=["recent-activities"])

if HAS_EMAIL and email_router is not None:
    app.include_router(email_router.router, prefix="/api/email", tags=["email"])

# ---------------------------------------------------------------------------
# Startup / Shutdown
# ---------------------------------------------------------------------------
scheduler = None

@app.on_event("startup")
async def on_startup():
    global scheduler
    logger.info("Starting ESG Dashboard API...")

    try:
        await connect_to_mongo()
        logger.info("MongoDB connected")
    except Exception as e:
        logger.exception(f"MongoDB connection failed: {e}")

    try:
        scheduler = start_egauge_scheduler()
        logger.info("eGauge scheduler started")
    except Exception as e:
        logger.warning(f"eGauge scheduler not started: {e}")

    logger.info(f"Startup complete. ENV={getattr(settings, 'ENVIRONMENT', 'unknown')}")

@app.on_event("shutdown")
async def on_shutdown():
    global scheduler

    try:
        if scheduler:
            scheduler.shutdown(wait=False)
            logger.info("Scheduler stopped")
    except Exception as e:
        logger.warning(f"Error stopping scheduler: {e}")

    try:
        await close_mongo_connection()
        logger.info("MongoDB closed")
    except Exception as e:
        logger.warning(f"Mongo close failed: {e}")

    logger.info("Shutdown complete")

# ---------------------------------------------------------------------------
# Root / Health
# ---------------------------------------------------------------------------
@app.get("/")
async def root():
    return {
        "message": "ESG Dashboard API is running",
        "version": "1.0.0",
        "environment": getattr(settings, "ENVIRONMENT", "unknown"),
        "docs": "/docs" if getattr(settings, "DEBUG", False) else None,
    }

@app.get("/health")
async def health_check():
    db_status = "unknown"
    try:
        await db.command("ping")
        db_status = "healthy"
    except Exception as e:
        db_status = f"error: {str(e)}"
        logger.error(f"DB health check failed: {e}")

    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "environment": getattr(settings, "ENVIRONMENT", "unknown"),
        "services": {
            "database": db_status,
            "scheduler": "running" if scheduler else "stopped",
        },
    }
