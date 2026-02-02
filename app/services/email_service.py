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
    """
    Gmail SMTP sender:
      - SMTP_HOST=smtp.gmail.com
      - SMTP_PORT=587
      - STARTTLS
      - SMTP_PASS must be a Google App Password
    """
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
    password = settings.SMTP_PASS  # keep exactly as stored in Render

    if not host or not user or not password:
        raise EmailSendError("SMTP config missing (SMTP_HOST/SMTP_PORT/SMTP_USER/SMTP_PASS).")

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


# -------------------------------------------------------------------
# ✅ Function expected by your backend/app/api/auth.py
# -------------------------------------------------------------------
def send_activation_email(to_email: str, full_name: str, activation_link: str) -> None:
    safe_name = (full_name or "").strip() or "there"
    subject = "Activate your account"

    html = f"""
    <div style="font-family: Arial, sans-serif; line-height: 1.5;">
      <h2>Welcome, {safe_name} 👋</h2>
      <p>Your account was created successfully. Please activate it using the link below:</p>

      <p style="margin: 24px 0;">
        <a href="{activation_link}"
           style="display:inline-block;padding:12px 18px;background:#111;color:#fff;text-decoration:none;border-radius:6px">
          Activate Account
        </a>
      </p>

      <p>If the button doesn’t work, copy and paste this link into your browser:</p>
      <p><a href="{activation_link}">{activation_link}</a></p>

      <hr />
      <p style="color:#666;font-size:12px;">
        If you didn’t request this, you can ignore this email.
      </p>
    </div>
    """

    text = f"Hi {safe_name}, activate your account here: {activation_link}"

    send_email(
        to_email=to_email,
        subject=subject,
        html_body=html,
        text_body=text,
    )
