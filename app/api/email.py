# backend/app/api/email.py

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
import logging

from app.services.email_service import send_activation_email

logger = logging.getLogger(__name__)
router = APIRouter()

class TestEmailRequest(BaseModel):
    email: EmailStr
    full_name: str = "User"
    activation_link: str

@router.post("/test-activation")
async def test_activation_email(body: TestEmailRequest):
    """
    Test endpoint to verify SMTP configuration
    """
    try:
        send_activation_email(
            to_email=body.email,
            full_name=body.full_name,
            activation_link=body.activation_link,
        )
        return {"success": True, "message": "Activation email sent"}
    except Exception as e:
        logger.exception("Test email failed")
        raise HTTPException(status_code=500, detail=str(e))
