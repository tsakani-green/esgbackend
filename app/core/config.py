# backend/app/core/config.py

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
import json


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # -------------------------------------------------
    # App
    # -------------------------------------------------
    DEBUG: bool = Field(default=False)
    ENVIRONMENT: str = Field(default="production")

    FRONTEND_URL: str | None = None
    CORS_ORIGINS: str | None = None

    # -------------------------------------------------
    # MongoDB
    # -------------------------------------------------
    MONGODB_URL: str | None = None

    def get_mongo_uri(self) -> str:
        """
        REQUIRED by app.core.database
        """
        if not self.MONGODB_URL:
            raise RuntimeError("MONGODB_URL is not set")
        return self.MONGODB_URL.strip()

    # -------------------------------------------------
    # eGauge
    # -------------------------------------------------
    EGAUGE_BASE_URL: str | None = None

    # -------------------------------------------------
    # SMTP (Email)
    # -------------------------------------------------
    SMTP_HOST: str | None = None
    SMTP_PORT: int = 587
    SMTP_USER: str | None = None
    SMTP_PASS: str | None = None

    # -------------------------------------------------
    # Helpers
    # -------------------------------------------------
    def get_cors_origins(self) -> list[str]:
        if not self.CORS_ORIGINS:
            return []
        raw = self.CORS_ORIGINS.strip()
        if not raw:
            return []
        if raw.startswith("["):
            try:
                items = json.loads(raw)
                return [str(x).strip().rstrip("/") for x in items if str(x).strip()]
            except Exception:
                return []
        return [x.strip().rstrip("/") for x in raw.split(",") if x.strip()]


settings = Settings()
