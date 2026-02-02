# backend/app/api/email.py

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr, Field
import logging

from app.services.email_service import send_email, EmailSendError
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


class SendEmailRequest(BaseModel):
    to: EmailStr
    subject: str = Field(..., min_length=1, max_length=200)
    html: str = Field(..., min_length=1)
    text: str | None = None


@router.get("/health")
def email_health():
    missing = []
    if not getattr(settings, "SMTP_HOST", None):
        missing.append("SMTP_HOST")
    if not getattr(settings, "SMTP_PORT", None):
        missing.append("SMTP_PORT")
    if not getattr(settings, "SMTP_USER", None):
        missing.append("SMTP_USER")
    if not getattr(settings, "SMTP_PASS", None):
        missing.append("SMTP_PASS")

    if missing:
        return {"status": "error", "missing": missing}

    return {
        "status": "ok",
        "smtp": {
            "host": settings.SMTP_HOST,
            "port": settings.SMTP_PORT,
            "user": settings.SMTP_USER,
        },
    }


@router.post("/send")
def email_send(payload: SendEmailRequest):
    try:
        send_email(
            to_email=str(payload.to),
            subject=payload.subject,
            html_body=payload.html,
            text_body=payload.text,
        )
        return {"status": "sent"}
    except EmailSendError as e:
        logger.warning(f"Email send failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.exception("Unhandled email error")
        raise HTTPException(status_code=500, detail=f"Unhandled error: {type(e).__name__}: {e}")
