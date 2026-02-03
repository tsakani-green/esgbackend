# backend/app/api/email.py

from __future__ import annotations

import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr, Field

from app.core.config import settings
from app.services.email_service import send_email, EmailSendError

logger = logging.getLogger(__name__)
router = APIRouter()


class SendEmailIn(BaseModel):
    to: EmailStr
    subject: str = Field(min_length=1, max_length=200)
    html: str = Field(min_length=1)
    text: str = ""


@router.get("/status")
async def email_status():
    """
    Quick sanity endpoint to confirm whether SMTP env vars exist.
    (Does NOT send an email.)
    """
    # We support both SMTP_PASSWORD and SMTP_PASS
    smtp_ok = bool(settings.SMTP_HOST and settings.SMTP_USER and (settings.SMTP_PASS or settings.SMTP_PASS is not None))
    # But your email_service reads env vars directly, so check env too:
    import os
    env_ok = bool(
        os.getenv("SMTP_HOST")
        and os.getenv("SMTP_USER")
        and (os.getenv("SMTP_PASSWORD") or os.getenv("SMTP_PASS"))
        and (os.getenv("FROM_EMAIL") or os.getenv("SMTP_USER"))
    )

    return JSONResponse(
        content={
            "service": "email",
            "configured": env_ok,
            "debug": bool(getattr(settings, "DEBUG", False)),
        }
    )


@router.post("/send")
async def send_email_endpoint(payload: SendEmailIn):
    """
    Send an email via SMTP.
    """
    try:
        to_email = payload.to.strip().lower()
        subject = payload.subject.strip()
        html = payload.html
        text = (payload.text or "").strip()

        send_email(to_email, subject, html, text if text else None)
        return JSONResponse(content={"success": True, "message": "Email sent"})

    except EmailSendError as e:
        # SMTP/provider-level errors
        raise HTTPException(status_code=503, detail=f"Email provider error: {str(e)}")

    except Exception as e:
        logger.exception(f"Email send failed: {e}")
        # show detail only in DEBUG
        if getattr(settings, "DEBUG", False):
            raise HTTPException(status_code=500, detail=f"Failed to send email: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to send email")
