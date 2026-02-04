# /app/app/api/assets.py
from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, List
from datetime import datetime, timedelta
import logging

from ..core.database import db
# FIX THIS LINE:
from ..services.sunsynk_service import SunsynkService  # ✅ Import class
from ..api.auth import get_current_user

logger = logging.getLogger(__name__)

# ✅ Create instance
sunsynk_service = SunsynkService()

router = APIRouter()

# ... rest of your code remains the same ...

@router.get("/")
async def list_assets():
    return {"message": "Assets router is live"}