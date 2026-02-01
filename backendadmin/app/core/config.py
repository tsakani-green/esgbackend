# backend/app/core/config.py

from __future__ import annotations

from typing import List, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Pydantic Settings v2

    Key points:
    - Loads env vars from the OS (Render Environment) first.
    - Also supports a local .env file for development.
    - extra="allow" prevents crashes if .env has keys not declared here.
    - case_sensitive=False makes env var matching forgiving.

    IMPORTANT:
    Do NOT hardcode secrets in this file.
    Put secrets in Render -> Environment (or .env.production locally).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="allow",
        case_sensitive=False,
    )

    # -------------------------
    # General
    # -------------------------
    DEBUG: bool = Field(default=True)
    ENVIRONMENT: str = Field(default="development")
    TIMEZONE: str = Field(default="Africa/Johannesburg")

    # -------------------------
    # CORS
    # -------------------------
    # Comma-separated list of allowed origins
    CORS_ORIGINS: str = Field(
        default=(
            "http://localhost:3001,http://localhost:3002,http://localhost:3008,http://localhost:5173,"
            "http://127.0.0.1:3001,http://127.0.0.1:3002,http://127.0.0.1:3008,http://127.0.0.1:5173"
        )
    )

    # -------------------------
    # Uploads
    # -------------------------
    MAX_UPLOAD_SIZE_MB: int = Field(default=50)
    UPLOAD_DIR: str = Field(default="./uploads")

    # -------------------------
    # Sunsynk API (set these in env)
    # -------------------------
    SUNSYNK_API_URL: str = Field(default="https://openapi.sunsynk.net")
    SUNSYNK_API_KEY: Optional[str] = Field(default=None)
    SUNSYNK_API_SECRET: Optional[str] = Field(default=None)

    # -------------------------
    # Mongo (support many historic names)
    # -------------------------
    MONGODB_URL: Optional[str] = Field(default=None)
    MONGODB_URI: Optional[str] = Field(default=None)
    MONGO_URI: Optional[str] = Field(default=None)

    MONGO_DB_NAME: Optional[str] = Field(default=None)
    MONGODB_DB: Optional[str] = Field(default=None)

    # -------------------------
    # Redis
    # -------------------------
    REDIS_URL: Optional[str] = Field(default=None)

    # -------------------------
    # Gemini AI (set in env)
    # -------------------------
    GEMINI_API_KEY: Optional[str] = Field(default=None)
    GEMINI_MODEL_ESG: str = Field(default="gemini-1.5-flash")

    # -------------------------
    # JWT Authentication
    # -------------------------
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30)
    SECRET_KEY: str = Field(default="your-secret-key-change-in-production")
    ALGORITHM: str = Field(default="HS256")
    AUTH_ENABLED: bool = Field(default=True)

    # -------------------------
    # Email Configuration (set in env for prod)
    # -------------------------
    EMAIL_HOST: str = Field(default="smtp.gmail.com")
    EMAIL_PORT: int = Field(default=587)
    EMAIL_USERNAME: Optional[str] = Field(default=None)
    EMAIL_PASSWORD: Optional[str] = Field(default=None)
    EMAIL_FROM: str = Field(default="noreply@africaesg.ai")
    EMAIL_FROM_NAME: str = Field(default="AfricaESG.AI")
    FRONTEND_URL: str = Field(default="http://localhost:5173")

    # -------------------------
    # Carbon Emissions Calculation
    # -------------------------
    CARBON_FACTOR_KG_PER_KWH: float = Field(default=0.93)

    # -------------------------
    # Portfolio / Asset naming
    # -------------------------
    DUBE_TRADE_PORT_PORTFOLIO_NAME: str = Field(default="Dube Trade Port")
    BERTHA_HOUSE_ASSET_NAME: str = Field(default="Bertha House")
    BERTHA_HOUSE_METER_NAME: str = Field(default="Local Mains")

    # -------------------------
    # eGauge (set creds in env)
    # -------------------------
    EGAUGE_BASE_URL: str = Field(default="https://egauge65730.egaug.es/63C1A1")
    EGAUGE_USERNAME: Optional[str] = Field(default=None)
    EGAUGE_PASSWORD: Optional[str] = Field(default=None)
    EGAUGE_POLL_INTERVAL_SECONDS: int = Field(default=60)
    BERTHA_HOUSE_COST_PER_KWH: float = Field(default=2.00)

    # -------------------------
    # Helpers
    # -------------------------
    def get_cors_origins(self) -> List[str]:
        return [o.strip() for o in (self.CORS_ORIGINS or "").split(",") if o.strip()]

    def get_mongo_uri(self) -> str:
        # Prefer explicit values, fall back to localhost if nothing set
        return (
            self.MONGODB_URL
            or self.MONGODB_URI
            or self.MONGO_URI
            or "mongodb://localhost:27017"
        )

    def get_mongo_db(self) -> str:
        return self.MONGO_DB_NAME or self.MONGODB_DB or "esg_dashboard"


settings = Settings()
