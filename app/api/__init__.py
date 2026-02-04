# backend/app/api/__init__.py

from app.api import auth
from app.api import admin
from app.api import analytics
from app.api import invoices
from app.api import reports
from app.api import files
from app.api import sunsynk
from app.api import ai_agent
from app.api import gemini_ai

# Optional: if you have email router
try:
    from app.api import email  # noqa: F401
except Exception:
    email = None  # type: ignore

__all__ = [
    "auth",
    "admin",
    "analytics",
    "invoices",
    "reports",
    "files",
    "sunsynk",
    "ai_agent",
    "gemini_ai",
    "email",
]
