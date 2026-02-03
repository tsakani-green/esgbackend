# backend/app/services/email_service.py

from __future__ import annotations

import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger(__name__)


class EmailSendError(Exception):
    pass


def _env(name: str, default: str | None = None) -> str | None:
    val = os.getenv(name)
    if val is None:
        return default
    val = val.strip()
    return val if val else default


def _get_smtp_config() -> dict:
    """
    Supports BOTH naming styles:
      - SMTP_PASSWORD (common)
      - SMTP_PASS (your config.py uses this)
    """
    smtp_host = _env("SMTP_HOST")
    smtp_port = int(_env("SMTP_PORT", "587") or "587")
    smtp_user = _env("SMTP_USER")

    # ✅ accept either env var
    smtp_pass = _env("SMTP_PASSWORD") or _env("SMTP_PASS")

    from_email = _env("FROM_EMAIL") or smtp_user

    missing = []
    if not smtp_host:
        missing.append("SMTP_HOST")
    if not smtp_user:
        missing.append("SMTP_USER")
    if not smtp_pass:
        missing.append("SMTP_PASSWORD or SMTP_PASS")
    if not from_email:
        missing.append("FROM_EMAIL")

    if missing:
        raise EmailSendError(f"Missing SMTP config: {', '.join(missing)}")

    return {
        "smtp_host": smtp_host,
        "smtp_port": smtp_port,
        "smtp_user": smtp_user,
        "smtp_pass": smtp_pass,
        "from_email": from_email,
    }


def send_email(
    to_email: str,
    subject: str,
    html_body: str,
    text_body: str | None = None,
) -> None:
    """
    Sends an email via SMTP using STARTTLS.
    """
    cfg = _get_smtp_config()

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = cfg["from_email"]
    msg["To"] = to_email

    # plain-text fallback
    if text_body:
        msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        with smtplib.SMTP(cfg["smtp_host"], cfg["smtp_port"], timeout=30) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(cfg["smtp_user"], cfg["smtp_pass"])
            server.sendmail(cfg["from_email"], [to_email], msg.as_string())

        logger.info(f"Email sent to {to_email} subject={subject!r}")

    except Exception as e:
        logger.exception(f"Email send failed to {to_email}: {e}")
        raise EmailSendError(str(e))


def send_activation_email(to_email: str, full_name: str, activation_link: str) -> None:
    """
    Called by auth.py during signup/resend-activation.
    """
    display_name = (full_name or "").strip() or "there"

    subject = "Activate your GreenBDG account"
    text_body = (
        f"Hi {display_name},\n\n"
        f"Please activate your account using this link:\n{activation_link}\n\n"
        "If you did not request this, you can ignore this email.\n"
    )

    html_body = f"""
    <div style="font-family: Arial, sans-serif; line-height: 1.6;">
      <h2>Activate your GreenBDG account</h2>
      <p>Hi <strong>{display_name}</strong>,</p>
      <p>Please activate your account by clicking the button below:</p>
      <p>
        <a href="{activation_link}"
           style="display:inline-block;padding:12px 18px;border-radius:8px;
                  background:#2e7d32;color:#fff;text-decoration:none;">
          Activate Account
        </a>
      </p>
      <p>If the button doesn't work, copy and paste this link into your browser:</p>
      <p><a href="{activation_link}">{activation_link}</a></p>
      <hr />
      <p style="color:#666;font-size:12px;">
        If you did not request this, you can ignore this email.
      </p>
    </div>
    """

    send_email(to_email=to_email, subject=subject, html_body=html_body, text_body=text_body)
