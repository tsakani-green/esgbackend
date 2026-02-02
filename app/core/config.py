# backend/app/core/config.py

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
import json


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DEBUG: bool = Field(default=False)
    ENVIRONMENT: str = Field(default="production")
    FRONTEND_URL: str | None = Field(default=None)
    CORS_ORIGINS: str | None = Field(default=None)

    EGAUGE_BASE_URL: str | None = Field(default=None)

    # SMTP
    SMTP_HOST: str | None = Field(default=None)
    SMTP_PORT: int = Field(default=587)
    SMTP_USER: str | None = Field(default=None)
    SMTP_PASS: str | None = Field(default=None)

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
