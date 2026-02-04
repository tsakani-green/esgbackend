from __future__ import annotations

import logging
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

genai = None
GEMINI_READY = False


def _init_gemini():
    global genai, GEMINI_READY

    try:
        import google.generativeai as _genai  # type: ignore
        genai = _genai

        api_key = getattr(settings, "GEMINI_API_KEY", None)
        if api_key:
            genai.configure(api_key=api_key)
            GEMINI_READY = True
            logger.info("Gemini AI enabled")
        else:
            GEMINI_READY = False
            logger.warning("GEMINI_API_KEY missing – Gemini disabled")

    except Exception as e:
        genai = None
        GEMINI_READY = False
        logger.warning(f"Gemini init failed: {e}")


_init_gemini()


def get_gemini_model(model_name: Optional[str] = None):
    """
    Returns a configured GenerativeModel instance.
    Uses settings.GEMINI_MODEL if model_name not provided.
    """
    if not GEMINI_READY or genai is None:
        raise RuntimeError("Gemini is not configured")

    chosen = model_name or getattr(settings, "GEMINI_MODEL", None) or "gemini-1.5-flash"
    return genai.GenerativeModel(chosen)
