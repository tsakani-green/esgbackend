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

# ✅ Option A DB (global db proxy) + lifecycle
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

# ✅ Email router (if you have it)
from app.api import email as email_router

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

# -----------------------------------------------------------------------------
# Error handlers
# -----------------------------------------------------------------------------
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

# -----------------------------------------------------------------------------
# CORS
# -----------------------------------------------------------------------------
def _split_csv(value: str | None) -> List[str]:
    if not value:
        return []
    return [v.strip().rstrip("/") for v in value.split(",") if v and v.strip()]


def _build_cors_origins() -> List[str]:
    origins = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://esgfrontend-delta.vercel.app",
    ]

    # FRONTEND_URL
    if getattr(settings, "FRONTEND_URL", None):
        origins.append(str(settings.FRONTEND_URL).strip().rstrip("/"))

    # CORS_ORIGINS from settings (supports JSON list or CSV via your config.py)
    try:
        env_origins = settings.get_cors_origins()
    except Exception as e:
        logger.warning(f"Failed to parse CORS_ORIGINS from settings: {e}")
        env_origins = _split_csv(os.getenv("CORS_ORIGINS"))

    if env_origins:
        for o in env_origins:
            o = (o or "").strip()
            if not o:
                continue
            if o == "*":
                return ["*"]
            origins.append(o.rstrip("/"))

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
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Help preflight requests return quickly
@app.options("/{full_path:path}")
async def preflight(full_path: str, request: Request):
    return Response(status_code=204)

# -----------------------------------------------------------------------------
# Routers
# -----------------------------------------------------------------------------
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])
app.include_router(sunsynk.router, prefix="/api/sunsynk", tags=["sunsynk"])
app.include_router(assets_sunsynk_router, prefix="/api/assets", tags=["assets-sunsynk"])

# NOTE: invoices had no prefix in your code; keep it as-is
app.include_router(invoices.router, tags=["invoices"])

app.include_router(files.router, prefix="/api/files", tags=["files"])
app.include_router(projects_router, prefix="/api/assets", tags=["assets"])
app.include_router(meters_router, prefix="/api/meters", tags=["meters"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["analytics"])
app.include_router(reports.router, prefix="/api/reports", tags=["reports"])
app.include_router(gemini_ai.router, tags=["Gemini AI"])
app.include_router(ai_agent.router, prefix="/api/ai", tags=["AI Agent"])
app.include_router(recent_activities_router, tags=["recent-activities"])

# ✅ Email routes (only if your app/api/email.py exists)
app.include_router(email_router.router, prefix="/api/email", tags=["email"])

# -----------------------------------------------------------------------------
# Startup / Shutdown
# -----------------------------------------------------------------------------
scheduler = None

@app.on_event("startup")
async def on_startup():
    global scheduler
    logger.info("Starting ESG Dashboard API...")

    # ✅ CRITICAL: initialize _db so db.users works
    try:
        await connect_to_mongo()
        logger.info("MongoDB connected")
    except Exception as e:
        logger.exception(f"MongoDB connection failed: {e}")
        # Let app still start, but auth/login will fail until fixed

    # optional scheduler
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

    # ✅ close mongo properly
    try:
        await close_mongo_connection()
    except Exception as e:
        logger.warning(f"Mongo close failed: {e}")

    logger.info("Shutdown complete")

# -----------------------------------------------------------------------------
# Root / Health
# -----------------------------------------------------------------------------
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
        # your _DBProxy exposes _db methods via getattr once initialized
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
