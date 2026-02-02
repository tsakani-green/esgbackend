# backend/app/core/database.py

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from app.core.config import settings

# Create client + default database
client = AsyncIOMotorClient(settings.get_mongo_uri())

# If your MONGODB_URL includes a db name, get_default_database() will use it.
# Otherwise it may return None. We handle both cases.
_db = client.get_default_database()


def _fallback_db_name() -> str:
    # fallback if URI doesn’t include a db name
    return "esg"


db: AsyncIOMotorDatabase = _db if _db is not None else client[_fallback_db_name()]


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
    return db
