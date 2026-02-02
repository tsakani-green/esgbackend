# backend/app/services/email_service.py

import smtplib
import socket
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from app.core.config import settings


class EmailSendError(Exception):
    pass


def send_email(
    to_email: str,
    subject: str,
    html_body: str,
    text_body: Optional[str] = None,
) -> None:
    msg = MIMEMultipart("alternative")
    msg["From"] = settings.SMTP_USER
    msg["To"] = to_email
    msg["Subject"] = subject

    if text_body:
        msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    host = (settings.SMTP_HOST or "").strip()
    port = int(getattr(settings, "SMTP_PORT", 587))
    user = (settings.SMTP_USER or "").strip()
    password = settings.SMTP_PASS

    if not host or not user or not password:
        raise EmailSendError("SMTP configuration missing (check SMTP_HOST/SMTP_PORT/SMTP_USER/SMTP_PASS).")

    try:
        with smtplib.SMTP(host, port, timeout=25) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(user, password)
            server.sendmail(user, [to_email], msg.as_string())

    except smtplib.SMTPAuthenticationError as e:
        raise EmailSendError(f"SMTP auth failed (Gmail): {e}") from e
    except smtplib.SMTPConnectError as e:
        raise EmailSendError(f"SMTP connect error: {e}") from e
    except smtplib.SMTPServerDisconnected as e:
        raise EmailSendError(f"SMTP disconnected: {e}") from e
    except socket.gaierror as e:
        raise EmailSendError(f"SMTP DNS error (check SMTP_HOST): {e}") from e
    except Exception as e:
        raise EmailSendError(f"Email send failed: {type(e).__name__}: {e}") from e
