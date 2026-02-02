# backend/app/services/email_service.py

import os
import smtplib
import ssl
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)

def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()

def send_activation_email(to_email: str, full_name: str, activation_link: str) -> None:
    """
    Sends activation email via SMTP.
    Raises exception on failure (caller will return 503).
    """

    smtp_host = _env("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(_env("SMTP_PORT", "587") or "587")
    smtp_user = _env("SMTP_USER")
    smtp_pass = _env("SMTP_PASS")

    # Important: Gmail often requires FROM to match the authenticated account
    from_email = _env("FROM_EMAIL") or smtp_user

    if not smtp_user or not smtp_pass:
        raise RuntimeError("SMTP_USER/SMTP_PASS not set in environment")

    if not to_email:
        raise ValueError("to_email is required")
    if not activation_link:
        raise ValueError("activation_link is required")

    subject = "Activate your ESG Dashboard account"

    # Plain + HTML (better deliverability)
    text_body = f"""Hi {full_name or ''},

Welcome! Please activate your account using this link:

{activation_link}

If you didn’t request this, ignore this email.
"""

    html_body = f"""
    <html>
      <body style="font-family: Arial, sans-serif;">
        <p>Hi {full_name or ''},</p>
        <p>Welcome! Please activate your account by clicking the button below:</p>
        <p>
          <a href="{activation_link}"
             style="display:inline-block;padding:10px 16px;background:#2e7d32;color:#fff;
                    text-decoration:none;border-radius:6px;">
            Activate Account
          </a>
        </p>
        <p>If the button doesn't work, copy/paste this link:</p>
        <p><a href="{activation_link}">{activation_link}</a></p>
        <p>If you didn’t request this, ignore this email.</p>
      </body>
    </html>
    """

    msg = MIMEMultipart("alternative")
    msg["From"] = from_email
    msg["To"] = to_email
    msg["Subject"] = subject

    msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    logger.info(f"Sending activation email via SMTP {smtp_host}:{smtp_port} as {smtp_user} to {to_email}")

    # STARTTLS for 587
    context = ssl.create_default_context()
    server = None
    try:
        server = smtplib.SMTP(smtp_host, smtp_port, timeout=30)
        server.ehlo()
        server.starttls(context=context)
        server.ehlo()

        server.login(smtp_user, smtp_pass)
        server.sendmail(from_email, [to_email], msg.as_string())

        logger.info(f"Activation email sent to {to_email}")
    except smtplib.SMTPAuthenticationError as e:
        logger.exception("SMTP AUTH FAILED (wrong app password / 2FA not set / wrong user)")
        raise
    except smtplib.SMTPException as e:
        logger.exception(f"SMTP ERROR: {e}")
        raise
    except Exception as e:
        logger.exception(f"EMAIL SEND ERROR: {e}")
        raise
    finally:
        try:
            if server:
                server.quit()
        except Exception:
            pass
