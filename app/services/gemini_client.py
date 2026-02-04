# backend/app/services/gemini_client.py

import logging
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

GEMINI_READY = False
genai = None  # google.generativeai module if available


def init_gemini() -> bool:
    """
    Initializes Gemini safely. Never crash the app on import.
    Returns True if Gemini is ready.
    """
    global GEMINI_READY, genai

    try:
        import google.generativeai as _genai
        genai = _genai
    except Exception as e:
        logger.warning(f"Gemini import failed: {e}")
        GEMINI_READY = False
        genai = None
        return False

    if not getattr(settings, "GEMINI_API_KEY", None):
        logger.warning("GEMINI_API_KEY missing – Gemini disabled")
        GEMINI_READY = False
        return False

    try:
        genai.configure(api_key=settings.GEMINI_API_KEY)
        GEMINI_READY = True
        logger.info("Gemini AI enabled")
        return True
    except Exception as e:
        logger.warning(f"Gemini init failed: {e}")
        GEMINI_READY = False
        return False


def get_gemini_model(model_name: Optional[str] = None):
    """
    Returns a configured GenerativeModel, or raises RuntimeError if Gemini not ready.
    """
    if not GEMINI_READY or genai is None:
        raise RuntimeError("Gemini not configured")

    name = model_name or getattr(settings, "GEMINI_MODEL", None) or "gemini-1.5-flash"
    return genai.GenerativeModel(name)


# Initialize on import (safe)
init_gemini()
