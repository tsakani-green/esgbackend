# backend/app/core/database.py

import logging
from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import settings

logger = logging.getLogger(__name__)

_client: AsyncIOMotorClient | None = None
_db = None

def _get_db_name_from_uri(uri: str) -> str:
    # If you include /dbname in MONGODB_URL, use it.
    # Otherwise fallback to settings.MONGODB_DB or "esg_dashboard".
    try:
        after_slash = uri.rsplit("/", 1)[-1]
        if after_slash and "?" in after_slash:
            after_slash = after_slash.split("?", 1)[0]
        if after_slash and after_slash != uri and after_slash.strip():
            return after_slash.strip()
    except Exception:
        pass
    return getattr(settings, "MONGODB_DB", None) or "esg_dashboard"

async def connect_to_mongo():
    global _client, _db

    if _client is not None and _db is not None:
        return _db

    if not settings.MONGODB_URL:
        raise RuntimeError("MONGODB_URL is not set")

    db_name = _get_db_name_from_uri(settings.MONGODB_URL)
    logger.info(f"Connecting to MongoDB (db={db_name})")

    _client = AsyncIOMotorClient(settings.MONGODB_URL)
    _db = _client[db_name]

    # quick ping
    await _db.command("ping")
    logger.info("MongoDB connection OK")

    return _db

async def close_mongo_connection():
    global _client, _db
    if _client:
        _client.close()
    _client = None
    _db = None
    logger.info("MongoDB connection closed")

class _DBProxy:
    """Lets you keep using: from app.core.database import db; await db.users.find_one(...)"""
    def __getattr__(self, item):
        if _db is None:
            raise RuntimeError("Database not initialized. Call connect_to_mongo() at startup.")
        return getattr(_db, item)

db = _DBProxy()
