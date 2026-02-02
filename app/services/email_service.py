# backend/app/services/email_service.py
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


def can_send_email() -> bool:
    required = ["SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASS", "FROM_EMAIL"]
    return all(_env(k) for k in required)


def send_activation_email(to_email: str, to_name: str, activation_link: str) -> None:
    """
    Sends an activation email using SMTP.

    REQUIRED ENV VARS:
      SMTP_HOST
      SMTP_PORT  (587 for STARTTLS, 465 for SSL)
      SMTP_USER
      SMTP_PASS
      FROM_EMAIL

    OPTIONAL:
      FROM_NAME
      SMTP_USE_SSL=true/false   (if true, uses SMTP_SSL)
    """
    if not can_send_email():
        raise RuntimeError("SMTP not configured (missing SMTP_* or FROM_EMAIL env vars)")

    smtp_host = _env("SMTP_HOST")
    smtp_port = int(_env("SMTP_PORT", "587"))
    smtp_user = _env("SMTP_USER")
    smtp_pass = _env("SMTP_PASS")
    from_email = _env("FROM_EMAIL")
    from_name = _env("FROM_NAME", "AfricaESG.AI")
    smtp_use_ssl = _env("SMTP_USE_SSL", "false").lower() in ("1", "true", "yes", "on")

    subject = "Activate your AfricaESG.AI account"

    html = f"""
    <div style="font-family: Arial, sans-serif; line-height: 1.5;">
      <h2>Hi {to_name or "there"},</h2>
      <p>Thanks for signing up for AfricaESG.AI.</p>
      <p>Please activate your account by clicking the link below:</p>
      <p><a href="{activation_link}">Activate my account</a></p>
      <p>If you didn’t request this, you can ignore this email.</p>
      <p><small>This link expires in 24 hours.</small></p>
    </div>
    """

    msg = MIMEMultipart("alternative")
    msg["From"] = f"{from_name} <{from_email}>" if from_name else from_email
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(html, "html"))

    # Reasonable network timeout
    timeout_seconds = 20

    if smtp_use_ssl or smtp_port == 465:
        with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=timeout_seconds) as server:
            server.login(smtp_user, smtp_pass)
            server.sendmail(from_email, [to_email], msg.as_string())
    else:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=timeout_seconds) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(smtp_user, smtp_pass)
            server.sendmail(from_email, [to_email], msg.as_string())
