from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

class SunsynkService:
    def __init__(self):
        if not settings.SUNSYNK_API_URL:
            logger.warning("SUNSYNK_API_URL not set – Sunsynk disabled")
            self.enabled = False
            return

        self.enabled = True
        self.api_url = settings.SUNSYNK_API_URL
        self.api_key = settings.SUNSYNK_API_KEY
        self.api_secret = settings.SUNSYNK_API_SECRET
