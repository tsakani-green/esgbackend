# backend/app/core/config.py

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
ENV_PATH = BASE_DIR / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ENV_PATH),
        extra="ignore",
    )

    DEBUG: bool = False
    ENVIRONMENT: str = "production"

    # -------------------------
    # Security / Auth
    #וב
    # -------------------------
    SECRET_KEY: str = "change-me"
    ACCESS_TOKEN_EXPIRE_HOURS: int = 24

    # -------------------------
    # Frontend / CORS
    # -------------------------
    FRONTEND_URL: Optional[str] = None
    CORS_ORIGINS: Optional[str] = None

    def get_cors_origins(self) -> list[str]:
        if not self.CORS_ORIGINS:
            return []
        raw = self.CORS_ORIGINS.strip()
        if raw.startswith("["):
            try:
                return [o.rstrip("/") for o in json.loads(raw)]
            except Exception:
                return []
        return [o.strip().rstrip("/") for o in raw.split(",") if o.strip()]

    # -------------------------
    # MongoDB
    # -------------------------
    MONGODB_URL: Optional[str] = None
    MONGO_URI: Optional[str] = None
    MONGODB_URI: Optional[str] = None

    def get_mongo_uri(self) -> str:
        uri = self.MONGODB_URL or self.MONGO_URI or self.MONGODB_URI
        if not uri:
            raise RuntimeError("MongoDB URI not set")
        return uri

    # -------------------------
    # Gemini AI
    # -------------------------
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-1.5-flash"

    # -------------------------
    # Sunsynk Integration ✅ FIX
    # -------------------------
    SUNSYNK_API_URL: Optional[str] = None
    SUNSYNK_API_KEY: Optional[str] = None
    SUNSYNK_API_SECRET: Optional[str] = None


settings = Settings()

print(f"[config] ENV={settings.ENVIRONMENT} DEBUG={settings.DEBUG}")
