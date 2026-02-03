# backend/app/core/database.py

import logging
from typing import Optional, Any

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from app.core.config import settings

logger = logging.getLogger(__name__)

_client: Optional[AsyncIOMotorClient] = None
_db: Optional[AsyncIOMotorDatabase] = None


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


async def connect_to_mongo() -> AsyncIOMotorDatabase:
    global _client, _db

    if _client is not None and _db is not None:
        return _db

    mongo_url = getattr(settings, "MONGODB_URL", None)
    if not mongo_url:
        raise RuntimeError("MONGODB_URL is not set")

    db_name = _get_db_name_from_uri(mongo_url)
    logger.info(f"Connecting to MongoDB (db={db_name})")

    _client = AsyncIOMotorClient(mongo_url)
    _db = _client[db_name]

    # quick ping
    await _db.command("ping")
    logger.info("MongoDB connection OK")

    return _db


async def close_mongo_connection() -> None:
    global _client, _db
    if _client:
        _client.close()
    _client = None
    _db = None
    logger.info("MongoDB connection closed")


# ✅ Compatibility dependency (prevents ImportError in routers that still do Depends(get_db))
# You can keep it even if you don't use it anywhere.
async def get_db() -> AsyncIOMotorDatabase:
    return await connect_to_mongo()


class _DBProxy:
    """Lets you keep using: from app.core.database import db; await db.users.find_one(...)"""

    def __getattr__(self, item: str) -> Any:
        if _db is None:
            raise RuntimeError("Database not initialized. Call connect_to_mongo() at startup.")
        return getattr(_db, item)


db = _DBProxy()
