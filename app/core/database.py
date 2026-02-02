# backend/app/core/database.py

from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import settings

# Create a single, shared Mongo client for the whole app
client = AsyncIOMotorClient(settings.get_mongo_uri())

# Select DB
db = client[settings.get_mongo_db()]

# FastAPI dependency
def get_db():
    return db


# Optional but recommended cleanup (call from app shutdown)
def close_mongo_client():
    try:
        client.close()
    except Exception:
        pass
