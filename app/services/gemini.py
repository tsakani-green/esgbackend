# backend/app/services/gemini.py

import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

GEMINI_READY = False
genai = None

try:
    import google.generativeai as genai  # type: ignore

    if settings.GEMINI_API_KEY:
        genai.configure(api_key=settings.GEMINI_API_KEY)
        GEMINI_READY = True
        logger.info("✅ Gemini AI enabled")
    else:
        logger.warning("⚠️ GEMINI_API_KEY missing – Gemini disabled")

except Exception as e:
    logger.warning(f"⚠️ Gemini init failed: {e}")
