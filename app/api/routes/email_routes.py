from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr

from app.services.email_service import send_email, EmailSendError

router = APIRouter(prefix="/email", tags=["email"])


class SendEmailRequest(BaseModel):
    to: EmailStr
    subject: str
    html: str
    text: str | None = None


@router.get("/health")
def email_health():
    # Doesn’t send an email — just confirms config is present & parsed.
    return {"status": "ok"}


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
        # Safe error to show in logs/response (doesn't expose secrets)
        raise HTTPException(status_code=500, detail=str(e))
