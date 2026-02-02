# backend/app/api/email.py

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
from fastapi.responses import JSONResponse
import logging

from app.services.email_service import send_email, EmailSendError

logger = logging.getLogger(__name__)
router = APIRouter()


class SendEmailIn(BaseModel):
    to: EmailStr
    subject: str
    html: str
    text: str = ""


@router.post("/send")
async def send_email_endpoint(payload: SendEmailIn):
    try:
        send_email(payload.to, payload.subject, payload.html, payload.text)
        return JSONResponse(content={"success": True})
    except EmailSendError as e:
        raise HTTPException(status_code=503, detail=f"Email provider error: {str(e)}")
    except Exception as e:
        logger.exception(f"Email send failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to send email")
