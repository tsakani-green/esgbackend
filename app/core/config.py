# backend/app/core/config.py

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
import json
from typing import Optional
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]  # backend/
ENV_PATH = BASE_DIR / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ENV_PATH),  # ✅ absolute .env path
        extra="ignore",
    )

    DEBUG: bool = Field(default=False)
    ENVIRONMENT: str = Field(default="production")

    # Auth / JWT
    SECRET_KEY: str = Field(default="change-me")
    ACCESS_TOKEN_EXPIRE_HOURS: int = Field(default=24)
    ACCESS_TOKEN_EXPIRE_MINUTES: Optional[int] = None

    @property
    def access_token_expire_minutes(self) -> int:
        if isinstance(self.ACCESS_TOKEN_EXPIRE_MINUTES, int) and self.ACCESS_TOKEN_EXPIRE_MINUTES > 0:
            return int(self.ACCESS_TOKEN_EXPIRE_MINUTES)
        return int(self.ACCESS_TOKEN_EXPIRE_HOURS) * 60

    # Frontend / CORS
    FRONTEND_URL: Optional[str] = None
    CORS_ORIGINS: Optional[str] = None

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

    # Mongo (support your existing keys)
    MONGODB_URL: Optional[str] = None
    MONGO_URI: Optional[str] = None
    MONGODB_URI: Optional[str] = None

    def get_mongo_uri(self) -> str:
        uri = (self.MONGODB_URL or self.MONGO_URI or self.MONGODB_URI or "").strip()
        if not uri:
            raise RuntimeError("Mongo URI is not set (set MONGODB_URL or MONGO_URI or MONGODB_URI)")
        return uri


settings = Settings()

print(f"[config] Loaded env from: {ENV_PATH}")
print(f"[config] DEBUG={settings.DEBUG} ENVIRONMENT={settings.ENVIRONMENT}")
