import logging
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

GEMINI_READY = False
genai = None

try:
    import google.generativeai as _genai

    if settings.GEMINI_API_KEY:
        _genai.configure(api_key=settings.GEMINI_API_KEY)
        genai = _genai
        GEMINI_READY = True
        logger.info("Gemini AI enabled")
    else:
        logger.warning("GEMINI_API_KEY missing – Gemini disabled")

except Exception as e:
    logger.warning(f"Gemini init failed: {e}")
    genai = None
    GEMINI_READY = False


def get_gemini_model(model_name: Optional[str] = None):
    """
    Backwards-compatible helper for any module importing get_gemini_model.
    Returns a configured GenerativeModel, or raises RuntimeError if Gemini isn't ready.
    """
    if not GEMINI_READY or genai is None:
        raise RuntimeError("Gemini not configured")

    name = model_name or getattr(settings, "GEMINI_MODEL", "gemini-1.5-flash")
    return genai.GenerativeModel(name)
