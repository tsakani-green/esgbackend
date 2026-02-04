# backend/app/core/config.py

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


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
    # -------------------------
    SECRET_KEY: str = "change-me"

    # Keep your old one if you still want it
    ACCESS_TOKEN_EXPIRE_HOURS: int = 24

    # ✅ REQUIRED by auth.py (it uses settings.access_token_expire_minutes)
    access_token_expire_minutes: int = 60 * 24

    # -------------------------
    # Frontend / CORS
    # -------------------------
    FRONTEND_URL: Optional[str] = None
    CORS_ORIGINS: Optional[str] = None

    def get_cors_origins(self) -> list[str]:
        if not self.CORS_ORIGINS:
            return []
        raw = self.CORS_ORIGINS.strip()

        # JSON list: ["https://a.com","https://b.com"]
        if raw.startswith("["):
            try:
                return [o.rstrip("/") for o in json.loads(raw)]
            except Exception:
                return []

        # CSV: https://a.com,https://b.com
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

    # --------------------------------------------------
    # Sunsynk Integration
    # --------------------------------------------------
    SUNSYNK_API_URL: str | None = None
    SUNSYNK_API_KEY: str | None = None
    SUNSYNK_API_SECRET: str | None = None


settings = Settings()

print(f"[config] ENV={settings.ENVIRONMENT} DEBUG={settings.DEBUG}")
