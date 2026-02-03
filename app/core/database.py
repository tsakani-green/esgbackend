# backend/app/core/database.py

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from app.core.config import settings

# Lazily create client + default database to avoid hard failure at import time
_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None


def _fallback_db_name() -> str:
    # fallback if URI doesn’t include a db name
    return "esg"


def _init_client_if_needed() -> None:
    """Initialize Motor client lazily. This avoids raising during import when
    MONGODB_URL isn't set (useful for tests and CI where DB may be mocked).
    """
    global _client, _db
    if _client is not None:
        return

    mongodb_url = getattr(settings, "MONGODB_URL", None)
    if not mongodb_url:
        # Leave _client/_db as None; code that needs the DB should handle this
        return

    client = AsyncIOMotorClient(mongodb_url.strip())

    # If your MONGODB_URL includes a db name, get_default_database() will use it.
    # Otherwise it may return None. We handle both cases.
    default_db = client.get_default_database()
    _client = client
    _db = default_db if default_db is not None else client[_fallback_db_name()]


# db may be None if MONGODB_URL is not set; callers should call get_db() or
# check for None and raise informative errors at runtime instead of on import.
db: AsyncIOMotorDatabase | None = None


# ✅ REQUIRED BY OTHER ROUTERS (e.g. files.py)
async def get_db() -> AsyncIOMotorDatabase:
    """
    FastAPI dependency for injecting the database.

    Usage:
        from fastapi import Depends
        from app.core.database import get_db

        @router.get("/something")
        async def handler(db=Depends(get_db)):
            ...
    """
    _init_client_if_needed()
    if _db is None:
        raise RuntimeError("MONGODB_URL is not set")
    return _db
