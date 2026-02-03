# backend/app/core/config.py

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
import json


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DEBUG: bool = Field(default=False)
    ENVIRONMENT: str = Field(default="production")

    # Auth / JWT
    SECRET_KEY: str = Field(default="change-me")

    # ✅ Keep your existing hours setting
    ACCESS_TOKEN_EXPIRE_HOURS: int = Field(default=24)

    # ✅ Add minutes too (so auth.py doesn't crash)
    ACCESS_TOKEN_EXPIRE_MINUTES: int | None = None

    # ✅ Computed helper (use this everywhere)
    @property
    def access_token_expire_minutes(self) -> int:
        # If minutes explicitly set, use it
        if isinstance(self.ACCESS_TOKEN_EXPIRE_MINUTES, int) and self.ACCESS_TOKEN_EXPIRE_MINUTES > 0:
            return self.ACCESS_TOKEN_EXPIRE_MINUTES
        # Otherwise derive from hours
        return int(self.ACCESS_TOKEN_EXPIRE_HOURS) * 60

    # Frontend / CORS
    FRONTEND_URL: str | None = None
    CORS_ORIGINS: str | None = None

    def get_cors_origins(self) -> list[str]:
        if not self.CORS_ORIGINS:
            return []
        raw = (self.CORS_ORIGINS or "").strip()
        if not raw:
            return []
        if raw.startswith("["):
            try:
                items = json.loads(raw)
                return [str(x).strip().rstrip("/") for x in items if str(x).strip()]
            except Exception:
                return []
        return [x.strip().rstrip("/") for x in raw.split(",") if x.strip()]

    # Mongo (matches your Render key)
    MONGODB_URL: str | None = None

    def get_mongo_uri(self) -> str:
        if not self.MONGODB_URL:
            raise RuntimeError("MONGODB_URL is not set")
        return self.MONGODB_URL.strip()

    # eGauge
    EGAUGE_BASE_URL: str | None = None
    EGAUGE_USERNAME: str | None = None
    EGAUGE_PASSWORD: str | None = None

    # ----------------------------------------------------------------
    # ✅ Email (feature flag + compatibility fields)
    # ----------------------------------------------------------------
    EMAIL_ENABLED: bool = Field(default=False)

    # These are here so any old code referencing settings.EMAIL_* won't crash.
    EMAIL_HOST: str | None = None
    EMAIL_PORT: int = 587
    EMAIL_USERNAME: str | None = None
    EMAIL_PASSWORD: str | None = None
    EMAIL_FROM: str | None = None
    EMAIL_FROM_NAME: str | None = None

    # Also keep your SMTP names (some parts may use them)
    SMTP_HOST: str | None = None
    SMTP_PORT: int = 587
    SMTP_USER: str | None = None
    SMTP_PASS: str | None = None

    # Sunsynk
    SUNSYNK_API_URL: str | None = None
    SUNSYNK_API_KEY: str | None = None
    SUNSYNK_API_SECRET: str | None = None

    # ✅ Gemini (matches Render env key)
    GEMINI_API_KEY: str | None = None
    GEMINI_MODEL: str = Field(default="gemini-1.5-flash")


settings = Settings()
