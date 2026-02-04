# backend/app/services/gemini_client.py

import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

GEMINI_READY = False
genai = None

try:
    import google.generativeai as genai  # noqa

    if getattr(settings, "GEMINI_API_KEY", None):
        genai.configure(api_key=settings.GEMINI_API_KEY)
        GEMINI_READY = True
        logger.info("✅ Gemini AI enabled")
    else:
        logger.warning("⚠️ GEMINI_API_KEY missing – Gemini disabled")

except Exception as e:
    logger.warning(f"⚠️ Gemini init failed: {e}")
    genai = None
